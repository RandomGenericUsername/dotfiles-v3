from pathlib import Path
from typing import Any

import yaml

from config_assembler_engine.errors import ConfigParseError
from config_assembler_engine.ports.config_parser import ConfigParserPort


class YamlConfigParser(ConfigParserPort):
    def parse(self, path: Path) -> dict[str, Any]:
        try:
            with path.open(encoding="utf-8") as f:
                result = yaml.safe_load(f)
                return result if result is not None else {}
        except Exception as e:
            raise ConfigParseError(f"Failed to parse YAML {path}: {e}") from e
