from abc import ABC, abstractmethod

from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.cancellation import CancellationToken
from oci_runtime.ports.output_stream import OutputStream


class PtyTransport(ABC):
    """Port: executes a command in a pseudo-terminal.

    Uses PTY for stdout (terminal rendering) and a separate pipe for
    stderr (error classification). This decouples output rendering
    from error detection — _check_result can inspect stderr for
    not-found patterns in both TTY and non-TTY modes.
    """

    @abstractmethod
    def execute_pty(
        self,
        command: list[str],
        *,
        output_stream: OutputStream,
        timeout: float | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> RawExecResult: ...
