import json
from pathlib import Path
from typing import Any

from config_assembler_engine.errors import ConfigParseError
from config_assembler_engine.ports.config_parser import ConfigParserPort


class JsonConfigParser(ConfigParserPort):
    def parse(self, path: Path) -> dict[str, Any]:
        try:
            with path.open(encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise ConfigParseError(f"Failed to parse JSON {path}: {e}") from e
