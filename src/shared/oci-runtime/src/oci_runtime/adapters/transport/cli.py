from __future__ import annotations

import subprocess

from oci_runtime.domain.exceptions import (
    OperationTimeoutError,
)
from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.binary_resolver import BinaryResolver
from oci_runtime.adapters.transport.cancel import _CancelContext
from oci_runtime.adapters.transport.cancellation import (
    DeadlineCancellationToken,
    compose_tokens,
)
from oci_runtime.adapters.transport.runner import _SubprocessRunner
from oci_runtime.adapters.transport.stream import _AsyncStreamReader
from oci_runtime.ports.cancellation import CancellationToken
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

        runner = _SubprocessRunner(command, input_data)
        runner.start_stdin_writer()

        cancel_ctx = _CancelContext(effective_token)

        reader = _AsyncStreamReader(
            runner.process.stdout.fileno(),
            runner.process.stderr.fileno(),
        )

        _process_reaped = False
        try:
            stdout_acc, stderr_acc = reader.read(cancel_ctx=cancel_ctx)

            if effective_token is not None and effective_token.is_cancelled:
                if isinstance(runner.process.poll(), int):
                    return RawExecResult(
                        returncode=runner.process.returncode,
                        stdout=b"".join(stdout_acc),
                        stderr=b"".join(stderr_acc),
                    )
                runner.process.kill()
                runner.process.wait()
                _process_reaped = True
                if deadline_token is not None and deadline_token.is_cancelled:
                    raise OperationTimeoutError(command=command, timeout=timeout)
                return RawExecResult(
                    returncode=-1,
                    stdout=b"".join(stdout_acc),
                    stderr=b"".join(stderr_acc),
                )

            while True:
                if effective_token is not None and effective_token.is_cancelled:
                    if isinstance(runner.process.poll(), int):
                        return RawExecResult(
                            returncode=runner.process.returncode,
                            stdout=b"".join(stdout_acc),
                            stderr=b"".join(stderr_acc),
                        )
                    runner.process.kill()
                    runner.process.wait()
                    _process_reaped = True
                    if deadline_token is not None and deadline_token.is_cancelled:
                        raise OperationTimeoutError(command=command, timeout=timeout)
                    return RawExecResult(
                        returncode=-1,
                        stdout=b"".join(stdout_acc),
                        stderr=b"".join(stderr_acc),
                    )
                try:
                    returncode = runner.process.wait(timeout=0.5)
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
            if not _process_reaped and runner.process:
                runner.process.kill()
                try:
                    runner.process.wait()
                except Exception:
                    pass
            if runner.process.stdout:
                runner.process.stdout.close()
            if runner.process.stderr:
                runner.process.stderr.close()
            if runner.process.stdin:
                runner.process.stdin.close()

    def probe(self) -> bool:
        return self._resolver.is_available(self.binary)

    def get_runtime_binary(self) -> str:
        return self._resolver.resolve(self.binary)
