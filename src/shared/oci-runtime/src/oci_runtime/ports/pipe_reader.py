import errno
import io
import os
import selectors
from abc import ABC, abstractmethod
from collections.abc import Callable

from oci_runtime.ports.cancellation import CancellationToken


class PipeReader(ABC):
    @abstractmethod
    def read(
        self,
        on_stdout: Callable[[bytes], None] | None = None,
        on_stderr: Callable[[bytes], None] | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> tuple[list[bytes], list[bytes]]: ...


class ProcessPipeReader(PipeReader):
    """Read from two file descriptors until both deliver EOF or cancellation.

    Works with subprocess pipes AND PTY master fds. Uses os.read(fd, n)
    which returns available data immediately (non-blocking after select).
    Handles PTY EIO (OSError) as EOF on Linux.
    """

    def __init__(self, primary_fd: int, secondary_fd: int):
        self._primary_fd = primary_fd
        self._secondary_fd = secondary_fd

    @classmethod
    def from_process(cls, process):
        if not hasattr(process.stdout, "fileno"):
            raise TypeError(
                f"Expected process with stdout.fileno(), got {type(process).__name__}"
            )
        if process.stderr is None or not hasattr(process.stderr, "fileno"):
            raise TypeError(
                f"Expected process with stderr.fileno(), got "
                f"{type(process.stderr).__name__ if process.stderr is not None else 'None'}"
            )
        try:
            return cls(process.stdout.fileno(), process.stderr.fileno())
        except (io.UnsupportedOperation, OSError) as e:
            raise TypeError(
                f"Expected process with stdout.fileno(), got {type(process).__name__}: {e}"
            ) from e

    @classmethod
    def from_fds(cls, primary_fd: int, secondary_fd: int) -> "ProcessPipeReader":
        """Create from raw file descriptors (e.g., PTY master + stderr pipe)."""
        return cls(primary_fd, secondary_fd)

    def _read_fd(self, fd: int, size: int = 4096) -> bytes:
        try:
            return os.read(fd, size)
        except OSError as e:
            if e.errno == errno.EIO:
                return b""
            raise

    def read(
        self,
        on_stdout: Callable[[bytes], None] | None = None,
        on_stderr: Callable[[bytes], None] | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> tuple[list[bytes], list[bytes]]:
        primary_acc: list[bytes] = []
        secondary_acc: list[bytes] = []
        selector = selectors.DefaultSelector()
        try:
            selector.register(self._primary_fd, selectors.EVENT_READ)
            selector.register(self._secondary_fd, selectors.EVENT_READ)
            while selector.get_map():
                if cancel_token and cancel_token.is_cancelled:
                    break
                events = selector.select(timeout=0.1)
                if not events:
                    continue
                for key, _ in events:
                    data = self._read_fd(key.fd)
                    if not data:
                        try:
                            selector.unregister(key.fd)
                        except KeyError:
                            pass
                        continue
                    if key.fd == self._primary_fd:
                        primary_acc.append(data)
                        if on_stdout:
                            on_stdout(data)
                    else:
                        secondary_acc.append(data)
                        if on_stderr:
                            on_stderr(data)
        finally:
            selector.close()
        return primary_acc, secondary_acc
