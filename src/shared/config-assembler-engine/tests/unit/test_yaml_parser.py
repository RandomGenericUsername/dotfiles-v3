from pathlib import Path

import pytest

from config_assembler_engine.adapters.parsers.yaml_parser import YamlConfigParser
from config_assembler_engine.errors import ConfigParseError

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestYamlConfigParser:
    def test_parse_valid(self):
        parser = YamlConfigParser()
        result = parser.parse(FIXTURES / "valid.yaml")
        assert result == {"engine": "docker", "timeout": 30, "mounts": ["/data", "/config"]}

    def test_parse_empty_yaml(self):
        parser = YamlConfigParser()
        result = parser.parse(FIXTURES / "empty.yaml")
        assert result == {}

    def test_parse_file_not_found(self):
        parser = YamlConfigParser()
        with pytest.raises(ConfigParseError):
            parser.parse(FIXTURES / "nonexistent.yaml")
