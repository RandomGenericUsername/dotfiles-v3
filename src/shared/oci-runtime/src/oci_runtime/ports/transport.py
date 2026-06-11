from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable


@dataclass
class ExecResult:
    returncode: int
    stdout: bytes
    stderr: bytes


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
    ) -> ExecResult: ...

    @abstractmethod
    def get_runtime_binary(self) -> str: ...

    @abstractmethod
    def probe(self) -> bool: ...
