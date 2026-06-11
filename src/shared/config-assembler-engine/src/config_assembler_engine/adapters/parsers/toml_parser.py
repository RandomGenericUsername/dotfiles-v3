import tomllib
from pathlib import Path
from typing import Any

from config_assembler_engine.errors import ConfigParseError
from config_assembler_engine.ports.config_parser import ConfigParserPort


class TomlConfigParser(ConfigParserPort):
    def parse(self, path: Path) -> dict[str, Any]:
        try:
            with path.open("rb") as f:
                return tomllib.load(f)
        except Exception as e:
            raise ConfigParseError(f"Failed to parse TOML {path}: {e}") from e
