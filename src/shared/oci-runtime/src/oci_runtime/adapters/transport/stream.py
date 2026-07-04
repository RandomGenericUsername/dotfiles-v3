import errno
import os
import selectors
from collections.abc import Callable

from oci_runtime.adapters.transport.cancel import _CancelContext

_READ_CHUNK = 4096


class _AsyncStreamReader:
    """Async-aware stream reader that reads from file descriptors
    with timeout and cancellation support.
    """

    def __init__(self, primary_fd: int, secondary_fd: int):
        self._primary_fd = primary_fd
        self._secondary_fd = secondary_fd

    def _read_fd(self, fd: int, size: int = _READ_CHUNK) -> bytes:
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
        cancel_ctx: _CancelContext | None = None,
        timeout: float | None = None,
    ) -> tuple[list[bytes], list[bytes]]:
        primary_acc: list[bytes] = []
        secondary_acc: list[bytes] = []
        sel_timeout = timeout if timeout is not None else 0.1
        selector = selectors.DefaultSelector()
        try:
            selector.register(self._primary_fd, selectors.EVENT_READ)
            selector.register(self._secondary_fd, selectors.EVENT_READ)
            while selector.get_map():
                if cancel_ctx and cancel_ctx.is_cancelled:
                    break
                events = selector.select(timeout=sel_timeout)
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
