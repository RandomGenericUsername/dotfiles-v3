import pytest

from oci_runtime.adapters._utils import parse_size_to_bytes
from oci_runtime.adapters.parser.base import BaseCliParser
from oci_runtime.ports.parsers import ParsingError


DOCKER_PRUNE_OUTPUT = """abc123def4567890abc123def4567890
abcdefabcdefabcdefabcdefabcdefabcd
Total reclaimed space: 1.5GB
"""


class TestParseSizeToBytes:
    def test_parses_gb(self):
        assert parse_size_to_bytes("1.5GB") == int(1.5 * 1024**3)

    def test_parses_mb(self):
        assert parse_size_to_bytes("512MB") == 512 * 1024**2

    def test_parses_kb(self):
        assert parse_size_to_bytes("2KB") == 2 * 1024

    def test_raises_for_empty_string(self):
        with pytest.raises(ValueError, match="Cannot parse size"):
            parse_size_to_bytes("")

    def test_raises_for_no_unit(self):
        with pytest.raises(ValueError, match="Cannot parse size"):
            parse_size_to_bytes("9999")

    def test_raises_for_gibberish(self):
        with pytest.raises(ValueError, match="Cannot parse size"):
            parse_size_to_bytes("abcxyz")

    def test_parses_with_spaces(self):
        assert parse_size_to_bytes("2 KB") == 2048


class TestBaseCliParser:
    def setup_method(self):
        self.parser = BaseCliParser()

    def test_parse_json_item_dict(self):
        result = self.parser._parse_json_item('{"key": "val"}')
        assert result == {"key": "val"}

    def test_parse_json_item_list(self):
        result = self.parser._parse_json_item('[{"key": "val"}]')
        assert result == {"key": "val"}

    def test_parse_json_item_empty_raises(self):
        with pytest.raises(ParsingError, match="Empty response"):
            self.parser._parse_json_item("[]")

    def test_parse_json_item_malformed_raises(self):
        with pytest.raises(ParsingError, match="Invalid JSON"):
            self.parser._parse_json_item("not json")

    def test_parse_json_list_list(self):
        result = self.parser._parse_json_list('[{"a": 1}, {"b": 2}]')
        assert result == [{"a": 1}, {"b": 2}]

    def test_parse_json_list_dict(self):
        result = self.parser._parse_json_list('{"a": 1}')
        assert result == [{"a": 1}]

    def test_parse_json_list_malformed_raises(self):
        with pytest.raises(ParsingError, match="Invalid JSON on line"):
            self.parser._parse_json_list("not json")

    def test_is_not_found_error_default_false(self):
        assert self.parser.is_not_found_error("anything") is False

    def test_is_not_found_error_with_patterns(self):
        class ParserWithPatterns(BaseCliParser):
            _not_found_patterns = ("not found", "no such")
        p = ParserWithPatterns()
        assert p.is_not_found_error("Not Found") is True
        assert p.is_not_found_error("no such thing") is True
        assert p.is_not_found_error("something else") is False

    def test_parse_prune_counts_deleted(self):
        result = self.parser.parse_prune(DOCKER_PRUNE_OUTPUT)
        assert result.deleted == 2

    def test_parse_prune_parses_reclaimed_space(self):
        result = self.parser.parse_prune(DOCKER_PRUNE_OUTPUT)
        assert result.reclaimed_bytes == int(1.5 * 1024**3)

    def test_parse_prune_empty(self):
        result = self.parser.parse_prune("")
        assert result.deleted == 0
        assert result.reclaimed_bytes == 0

    def test_prune_all_counts_deleted_sha256_lines(self):
        from oci_runtime.domain.types import PruneResult
        output = "deleted: sha256:abc123def456\ndeleted: sha256:789012abcdef\nTotal reclaimed space: 1.2GB\n"
        result = self.parser.parse_prune(output)
        assert result == PruneResult(deleted=2, reclaimed_bytes=1288490188)


class TestParseJsonListNDJSON:
    def setup_method(self):
        self.parser = BaseCliParser()

    def test_json_array(self):
        result = self.parser._parse_json_list('[{"id": "abc"}]')
        assert len(result) == 1
        assert result[0]["id"] == "abc"

    def test_single_object(self):
        result = self.parser._parse_json_list('{"id": "abc"}')
        assert len(result) == 1
        assert result[0]["id"] == "abc"

    def test_ndjson_two_objects(self):
        ndjson = '{"id": "abc"}\n{"id": "def"}'
        result = self.parser._parse_json_list(ndjson)
        assert len(result) == 2
        assert result[0]["id"] == "abc"
        assert result[1]["id"] == "def"

    def test_ndjson_with_blank_lines(self):
        ndjson = '{"id": "abc"}\n\n{"id": "def"}\n'
        result = self.parser._parse_json_list(ndjson)
        assert len(result) == 2

    def test_empty_string_returns_empty_list(self):
        result = self.parser._parse_json_list("")
        assert result == []

    def test_empty_list_returns_empty(self):
        result = self.parser._parse_json_list("[]")
        assert result == []

    def test_garbage_raises(self):
        with pytest.raises(ParsingError):
            self.parser._parse_json_list("not json at all")

    def test_partial_ndjson_raises_on_bad_line(self):
        ndjson = '{"id": "abc"}\nnot json\n{"id": "def"}'
        with pytest.raises(ParsingError, match="Invalid JSON on line 2"):
            self.parser._parse_json_list(ndjson)

    def test_table_format_raises(self):
        table = "REPOSITORY    TAG       IMAGE ID\nalpine         latest    abc123"
        with pytest.raises(ParsingError):
            self.parser._parse_json_list(table)
