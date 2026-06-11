from pathlib import Path

import pytest

from config_assembler_engine.adapters.parsers.json_parser import JsonConfigParser
from config_assembler_engine.errors import ConfigParseError

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestJsonConfigParser:
    def test_parse_valid(self):
        parser = JsonConfigParser()
        result = parser.parse(FIXTURES / "valid.json")
        assert result == {"engine": "docker", "timeout": 30, "mounts": ["/data", "/config"]}

    def test_parse_file_not_found(self):
        parser = JsonConfigParser()
        with pytest.raises(ConfigParseError):
            parser.parse(FIXTURES / "nonexistent.json")
