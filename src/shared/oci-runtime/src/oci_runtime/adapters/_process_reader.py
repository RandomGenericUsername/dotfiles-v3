import selectors
import subprocess
from typing import Callable

from oci_runtime.domain.types import CancellationToken


class ProcessPipeReader:
    """Read stdout/stderr from a subprocess until both pipes deliver EOF.

    Exits purely on pipe EOF, not on process exit. The OS guarantees
    that EOF is delivered on a pipe only after the writer has closed
    its end *and* all buffered data has been consumed. This ensures
    no data is lost even if the process exits before the reader
    finishes draining the pipes.
    """

    def __init__(
        self,
        process: subprocess.Popen,
    ):
        self._process = process

    def read(
        self,
        on_stdout: Callable[[bytes], None] | None = None,
        on_stderr: Callable[[bytes], None] | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> tuple[list[bytes], list[bytes]]:
        """Read all output until both pipes reach EOF or cancellation.

        When cancelled, returns partial data accumulated so far.
        """
        stdout_acc: list[bytes] = []
        stderr_acc: list[bytes] = []
        selector = selectors.DefaultSelector()
        try:
            selector.register(self._process.stdout, selectors.EVENT_READ)
            selector.register(self._process.stderr, selectors.EVENT_READ)
            while selector.get_map():
                if cancel_token and cancel_token.is_cancelled:
                    break
                events = selector.select(timeout=0.1)
                if not events:
                    continue
                for key, _ in events:
                    data = key.fileobj.read(1024)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    if key.fileobj is self._process.stdout:
                        stdout_acc.append(data)
                        if on_stdout:
                            on_stdout(data)
                    else:
                        stderr_acc.append(data)
                        if on_stderr:
                            on_stderr(data)
        finally:
            selector.close()
        return stdout_acc, stderr_acc