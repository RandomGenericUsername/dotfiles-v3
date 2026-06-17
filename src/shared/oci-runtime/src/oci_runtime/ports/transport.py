from abc import ABC, abstractmethod
from typing import Callable

from oci_runtime.domain.types import CancellationToken, ExecResult


class Transport(ABC):
    @abstractmethod
    def execute(
        self,
        command: list[str],
        *,
        timeout: int | None = None,
        input_data: bytes | None = None,
        stream: bool = False,
        on_output: Callable[[bytes, str], None] | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> ExecResult: ...

    @abstractmethod
    def get_runtime_binary(self) -> str: ...

    @abstractmethod
    def probe(self) -> bool: ...
