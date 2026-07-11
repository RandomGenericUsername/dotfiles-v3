from __future__ import annotations

import os
import pty
import subprocess

from oci_runtime.domain.exceptions import (
    OciError,
    OperationTimeoutError,
)
from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.binary_resolver import BinaryResolver
from oci_runtime.adapters.transport.cancel import _CancelContext
from oci_runtime.adapters.transport.cancellation import (
    DeadlineCancellationToken,
    compose_tokens,
)
from oci_runtime.adapters.transport.stream import _AsyncStreamReader
from oci_runtime.ports.cancellation import CancellationToken
from oci_runtime.ports.output_stream import OutputStream
from oci_runtime.ports.pty_transport import PtyTransport


class CliPtyTransport(PtyTransport):
    def __init__(self, binary_resolver: BinaryResolver):
        self._resolver = binary_resolver

    def execute_pty(
        self,
        command: list[str],
        *,
        output_stream: OutputStream,
        timeout: float | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> RawExecResult:
        if not command:
            raise OciError("Empty command list", command=command)
        self._resolver.resolve(command[0])

        deadline_token = None
        if timeout is not None:
            deadline_token = DeadlineCancellationToken(timeout)
        effective_token = compose_tokens(cancel_token, deadline_token)

        master_fd, slave_fd = pty.openpty()
        process = None
        try:
            process = subprocess.Popen(
                command,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=subprocess.PIPE,
            )
            os.close(slave_fd)
            slave_fd = -1

            if process.stderr is None:
                process.kill()
                raise OciError(
                    "CliPtyTransport.execute_pty: subprocess.Popen returned "
                    "stderr=None despite stderr=PIPE — internal invariant violated"
                )

            cancel_ctx = _CancelContext(effective_token)
            reader = _AsyncStreamReader(master_fd, process.stderr.fileno())

            def _on_stdout(data: bytes) -> None:
                output_stream.write(data)
                output_stream.flush()

            stdout_acc, stderr_acc = reader.read(
                on_stdout=_on_stdout,
                cancel_ctx=cancel_ctx,
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
            return RawExecResult(
                returncode=returncode,
                stdout=b"".join(stdout_acc),
                stderr=b"".join(stderr_acc),
            )
        finally:
            if deadline_token is not None:
                deadline_token.cancel()
            if slave_fd != -1:
                try:
                    os.close(slave_fd)
                except OSError:
                    pass
            try:
                os.close(master_fd)
            except OSError:
                pass
            if process:
                for pipe in (process.stdout, process.stderr, process.stdin):
                    if pipe:
                        pipe.close()
