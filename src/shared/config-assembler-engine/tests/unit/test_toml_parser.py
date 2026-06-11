from pathlib import Path

import pytest

from config_assembler_engine.adapters.parsers.toml_parser import TomlConfigParser
from config_assembler_engine.errors import ConfigParseError

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestTomlConfigParser:
    def test_parse_valid(self):
        parser = TomlConfigParser()
        result = parser.parse(FIXTURES / "valid.toml")
        assert result == {"engine": "docker", "timeout": 30, "mounts": ["/data", "/config"]}

    def test_parse_file_not_found(self):
        parser = TomlConfigParser()
        with pytest.raises(ConfigParseError):
            parser.parse(FIXTURES / "nonexistent.toml")

    def test_parse_malformed(self):
        parser = TomlConfigParser()
        with pytest.raises(ConfigParseError):
            parser.parse(FIXTURES / "malformed.toml")
