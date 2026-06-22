import subprocess
import threading
from collections.abc import Callable

from oci_runtime.adapters._cancellation import (
    DeadlineCancellationToken,
    compose_tokens,
)
from oci_runtime.adapters import _process_reader
from oci_runtime.adapters.binary import CliBinaryResolver
from oci_runtime.domain.exceptions import OperationTimeoutError
from oci_runtime.ports.binary_resolver import BinaryResolver
from oci_runtime.ports.cancellation import CancellationToken
from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.streaming import StreamingTransport


class CliStreamingTransport(StreamingTransport):
    def __init__(self, binary: str, binary_resolver: BinaryResolver | None = None):
        self.binary = binary
        self._resolver = binary_resolver or CliBinaryResolver()

    def stream(
        self,
        command: list[str],
        *,
        timeout: float | None = None,
        input_data: bytes | None = None,
        on_stdout: Callable[[bytes], None] | None = None,
        on_stderr: Callable[[bytes], None] | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> RawExecResult:
        self._resolver.resolve(self.binary)

        deadline_token: DeadlineCancellationToken | None = None
        if timeout is not None:
            deadline_token = DeadlineCancellationToken(timeout)
        effective_token = compose_tokens(cancel_token, deadline_token)

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
                    try:
                        process.stdin.write(input_data)
                        process.stdin.close()
                    except OSError:
                        pass

                _stdin_thread = threading.Thread(target=_write_stdin, daemon=True)
                _stdin_thread.start()

            reader = _process_reader.ProcessPipeReader.from_process(process)
            stdout_acc, stderr_acc = reader.read(
                on_stdout,
                on_stderr,
                cancel_token=effective_token,
            )

            if effective_token is not None and effective_token.is_cancelled:
                process.kill()
                process.wait()
                _process_reaped = True
                if _stdin_thread:
                    _stdin_thread.join(timeout=5)
                if deadline_token is not None and deadline_token.is_cancelled:
                    raise OperationTimeoutError(command=command, timeout=timeout)
                return RawExecResult(
                    returncode=-1,
                    stdout=b"".join(stdout_acc),
                    stderr=b"".join(stderr_acc),
                )

            if _stdin_thread:
                _stdin_thread.join(timeout=5)
            while True:
                if effective_token is not None and effective_token.is_cancelled:
                    process.kill()
                    process.wait()
                    _process_reaped = True
                    if deadline_token is not None and deadline_token.is_cancelled:
                        raise OperationTimeoutError(command=command, timeout=timeout)
                    return RawExecResult(
                        returncode=-1,
                        stdout=b"".join(stdout_acc),
                        stderr=b"".join(stderr_acc),
                    )
                try:
                    returncode = process.wait(timeout=0.5)
                    break
                except subprocess.TimeoutExpired:
                    continue
            _process_reaped = True
            return RawExecResult(
                returncode=returncode,
                stdout=b"".join(stdout_acc),
                stderr=b"".join(stderr_acc),
            )

        finally:
            if deadline_token is not None:
                deadline_token.cancel()
            if process and not _process_reaped:
                process.kill()
                try:
                    process.wait()
                except Exception:
                    pass
            if process:
                for pipe in (process.stdout, process.stderr, process.stdin):
                    if pipe:
                        pipe.close()
