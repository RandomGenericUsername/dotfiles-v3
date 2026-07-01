import subprocess
import threading

from oci_runtime.domain.exceptions import (
    OperationTimeoutError,
)
from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.binary_resolver import BinaryResolver
from oci_runtime.ports.cancellation import (
    CancellationToken,
    DeadlineCancellationToken,
    compose_tokens,
)
from oci_runtime.ports.pipe_reader import ProcessPipeReader
from oci_runtime.ports.transport import Transport


class CliTransport(Transport):
    def __init__(self, binary: str, binary_resolver: BinaryResolver):
        self.binary = binary
        self._resolver = binary_resolver

    def execute(
        self,
        command: list[str],
        *,
        timeout: float | None = None,
        input_data: bytes | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> RawExecResult:
        self._resolver.resolve(self.binary)

        deadline_token: DeadlineCancellationToken | None = None
        if timeout is not None:
            deadline_token = DeadlineCancellationToken(timeout)
        effective_token = compose_tokens(cancel_token, deadline_token)

        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE if input_data is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _process_reaped = False

        stdin_thread: threading.Thread | None = None
        if input_data is not None:

            def _write_stdin() -> None:
                stdin = process.stdin
                if stdin is None:
                    return
                try:
                    stdin.write(input_data)
                    stdin.close()
                except (OSError, ValueError):
                    pass

            stdin_thread = threading.Thread(target=_write_stdin, daemon=True)
            stdin_thread.start()

        try:
            reader = ProcessPipeReader.from_process(process)
            stdout_acc, stderr_acc = reader.read(
                cancel_token=effective_token,
            )

            if effective_token is not None and effective_token.is_cancelled:
                if isinstance(process.poll(), int):
                    return RawExecResult(
                        returncode=process.returncode,
                        stdout=b"".join(stdout_acc),
                        stderr=b"".join(stderr_acc),
                    )
                process.kill()
                process.wait()
                if deadline_token is not None and deadline_token.is_cancelled:
                    raise OperationTimeoutError(command=command, timeout=timeout)
                return RawExecResult(
                    returncode=-1,
                    stdout=b"".join(stdout_acc),
                    stderr=b"".join(stderr_acc),
                )

            while True:
                if effective_token is not None and effective_token.is_cancelled:
                    if isinstance(process.poll(), int):
                        return RawExecResult(
                            returncode=process.returncode,
                            stdout=b"".join(stdout_acc),
                            stderr=b"".join(stderr_acc),
                        )
                    process.kill()
                    process.wait()
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
            if not _process_reaped and process:
                process.kill()
                try:
                    process.wait()
                except Exception:
                    pass
            if process.stdout:
                process.stdout.close()
            if process.stderr:
                process.stderr.close()
            if process.stdin:
                process.stdin.close()
            if stdin_thread:
                stdin_thread.join(timeout=5)

    def probe(self) -> bool:
        return self._resolver.is_available(self.binary)

    def get_runtime_binary(self) -> str:
        return self._resolver.resolve(self.binary)
