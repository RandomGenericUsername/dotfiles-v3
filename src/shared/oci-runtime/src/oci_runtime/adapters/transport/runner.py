import subprocess
import threading


class _SubprocessRunner:
    """Manages a subprocess with optional stdin writing and timeout."""

    def __init__(self, cmd: list[str], input_data: bytes | None = None):
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE if input_data is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._input_data = input_data
        self._stdin_thread: threading.Thread | None = None

    def start_stdin_writer(self) -> None:
        if self._input_data is not None:

            def _write():
                try:
                    self._process.stdin.write(self._input_data)
                    self._process.stdin.flush()
                except OSError:
                    pass
                finally:
                    try:
                        self._process.stdin.close()
                    except OSError:
                        pass

            self._stdin_thread = threading.Thread(target=_write, daemon=True)
            self._stdin_thread.start()

    def wait(self, timeout: float | None = None) -> subprocess.CompletedProcess:
        try:
            stdout, stderr = self._process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._process.kill()
            stdout, stderr = self._process.communicate()
            raise subprocess.TimeoutExpired(self._process.args, timeout, stdout, stderr)
        return subprocess.CompletedProcess(
            args=self._process.args,
            returncode=self._process.returncode,
            stdout=stdout,
            stderr=stderr,
        )

    @property
    def process(self):
        return self._process
