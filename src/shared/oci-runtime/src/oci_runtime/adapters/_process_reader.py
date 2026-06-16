import selectors
import subprocess
from typing import Callable


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
        on_output: Callable[[bytes, str], None] | None = None,
    ) -> tuple[list[bytes], list[bytes]]:
        """Read all output until both pipes reach EOF.

        Returns (stdout_chunks, stderr_chunks).
        """
        stdout_acc: list[bytes] = []
        stderr_acc: list[bytes] = []
        selector = selectors.DefaultSelector()
        try:
            selector.register(self._process.stdout, selectors.EVENT_READ)
            selector.register(self._process.stderr, selectors.EVENT_READ)
            while selector.get_map():
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
                        if on_output:
                            on_output(data, "stdout")
                    else:
                        stderr_acc.append(data)
                        if on_output:
                            on_output(data, "stderr")
        finally:
            selector.close()
        return stdout_acc, stderr_acc