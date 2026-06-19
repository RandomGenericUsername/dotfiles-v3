import shutil
import subprocess
import threading
from typing import Callable

from oci_runtime.adapters._process_reader import ProcessPipeReader
from oci_runtime.domain.exceptions import RuntimeNotAvailableError
from oci_runtime.domain.types import CancellationToken, ExecResult
from oci_runtime.ports.streaming import StreamingTransport


class CliStreamingTransport(StreamingTransport):
    def __init__(self, binary: str):
        self.binary = binary

    def stream(
        self,
        command: list[str],
        *,
        timeout: int | None = None,
        input_data: bytes | None = None,
        on_stdout: Callable[[bytes], None] | None = None,
        on_stderr: Callable[[bytes], None] | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> ExecResult:
        if shutil.which(self.binary) is None:
            raise RuntimeNotAvailableError(self.binary)

        process: subprocess.Popen | None = None
        _stdin_thread: threading.Thread | None = None
        _process_reaped = False
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE if input_data is not None else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )

            if input_data is not None:
                def _write_stdin() -> None:
                    process.stdin.write(input_data)
                    process.stdin.close()
                _stdin_thread = threading.Thread(target=_write_stdin, daemon=True)
                _stdin_thread.start()

            reader = ProcessPipeReader(process)
            stdout_acc, stderr_acc = reader.read(on_stdout, on_stderr, cancel_token)

            if _stdin_thread:
                _stdin_thread.join(timeout=5)

            if cancel_token and cancel_token.is_cancelled:
                process.kill()
                process.wait()
                _process_reaped = True
                return ExecResult(
                    returncode=-1,
                    stdout=b"".join(stdout_acc),
                    stderr=b"".join(stderr_acc),
                )

            returncode = process.wait(timeout=timeout)
            _process_reaped = True
            return ExecResult(
                returncode=returncode,
                stdout=b"".join(stdout_acc),
                stderr=b"".join(stderr_acc),
            )

        except subprocess.TimeoutExpired:
            if process and process.poll() is None:
                process.kill()
                process.wait()
            _process_reaped = True
            raise
        finally:
            if process and not _process_reaped:
                process.kill()
                process.wait()
            if process:
                for pipe in (process.stdout, process.stderr, process.stdin):
                    if pipe:
                        pipe.close()