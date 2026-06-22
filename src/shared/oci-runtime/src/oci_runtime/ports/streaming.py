from abc import ABC, abstractmethod
from collections.abc import Callable

from oci_runtime.ports.cancellation import CancellationToken
from oci_runtime.domain.types import RawExecResult


class StreamingTransport(ABC):
    """Execute a command and stream its output in real-time.

    Unlike Transport.execute() which is batch (subprocess.run),
    StreamingTransport uses Popen + selector-based reading to
    deliver output as it arrives via callbacks.
    """

    @abstractmethod
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
        """Execute command, call callbacks as output arrives.

        Returns RawExecResult with accumulated output and exit code.
        When cancelled, returns partial data with returncode=-1.
        """
