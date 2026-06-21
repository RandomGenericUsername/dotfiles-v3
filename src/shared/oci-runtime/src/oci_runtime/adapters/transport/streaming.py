import shutil
import subprocess
import threading
from typing import Callable

from oci_runtime.adapters._cancellation import (
    CompositeCancellationToken,
    DeadlineCancellationToken,
)
from oci_runtime.adapters._process_reader import ProcessPipeReader
from oci_runtime.domain.exceptions import RuntimeNotAvailableError
from oci_runtime.domain.types import CancellationToken, RawExecResult
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
    ) -> RawExecResult:
        if shutil.which(self.binary) is None:
            raise RuntimeNotAvailableError(self.binary)

        deadline_token: DeadlineCancellationToken | None = None
        if timeout is not None:
            deadline_token = DeadlineCancellationToken(timeout)
        if deadline_token is not None and cancel_token is not None:
            effective_token: CancellationToken | None = CompositeCancellationToken(cancel_token, deadline_token)
        elif deadline_token is not None:
            effective_token = deadline_token
        else:
            effective_token = cancel_token

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
            stdout_acc, stderr_acc = reader.read(on_stdout, on_stderr, effective_token)

            if _stdin_thread:
                _stdin_thread.join(timeout=5)

            if effective_token is not None and effective_token.is_cancelled:
                process.kill()
                process.wait()
                _process_reaped = True
                if deadline_token is not None and deadline_token.is_cancelled:
                    raise subprocess.TimeoutExpired(
                        " ".join(command) if isinstance(command, list) else command,
                        timeout,
                    )
                return RawExecResult(
                    returncode=-1,
                    stdout=b"".join(stdout_acc),
                    stderr=b"".join(stderr_acc),
                )

            returncode = process.wait(timeout=timeout)
            _process_reaped = True
            return RawExecResult(
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
            if deadline_token is not None:
                deadline_token.cancel()
            if process and not _process_reaped:
                process.kill()
                process.wait()
            if process:
                for pipe in (process.stdout, process.stderr, process.stdin):
                    if pipe:
                        pipe.close()