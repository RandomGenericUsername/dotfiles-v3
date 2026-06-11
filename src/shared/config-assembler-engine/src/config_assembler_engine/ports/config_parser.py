from pathlib import Path
from typing import Any, Protocol


class ConfigParserPort(Protocol):
    def parse(self, path: Path) -> dict[str, Any]:
        ...
