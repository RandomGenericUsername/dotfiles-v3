import os
from typing import ClassVar

from config_assembler_engine.ports.env_reader import EnvironmentReaderPort


class OsEnvironmentReader(EnvironmentReaderPort):
    SEPARATOR: ClassVar[str] = "__"

    def read(self, prefix: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for key, value in os.environ.items():
            if not key.startswith(prefix + self.SEPARATOR):
                continue
            config_key = key[len(prefix) + len(self.SEPARATOR):].lower()
            result[config_key] = value
        return result
