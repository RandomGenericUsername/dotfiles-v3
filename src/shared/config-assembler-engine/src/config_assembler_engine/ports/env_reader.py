from typing import Protocol


class EnvironmentReaderPort(Protocol):
    def read(self, prefix: str) -> dict[str, str]: ...
