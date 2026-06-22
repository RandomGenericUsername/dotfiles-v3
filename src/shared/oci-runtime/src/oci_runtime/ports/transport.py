from abc import ABC, abstractmethod

from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.cancellation import CancellationToken


class Transport(ABC):
    @abstractmethod
    def execute(
        self,
        command: list[str],
        *,
        timeout: float | None = None,
        input_data: bytes | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> RawExecResult: ...

    @abstractmethod
    def get_runtime_binary(self) -> str: ...

    @abstractmethod
    def probe(self) -> bool: ...
