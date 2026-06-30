import pytest

from oci_runtime.domain.size_parsing import parse_size_to_bytes
from oci_runtime.domain.json_parsing import parse_json_item, parse_json_list
from oci_runtime.domain.error_matching import matches_any_pattern
from oci_runtime.domain.prune_parsing import parse_prune_result
from oci_runtime.domain.exceptions import ParsingError
from oci_runtime.domain.types import PruneResult


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

    def test_accepts_unitless_value(self):
        assert parse_size_to_bytes("9999") == 9999

    def test_raises_for_gibberish(self):
        with pytest.raises(ValueError, match="Cannot parse size"):
            parse_size_to_bytes("abcxyz")

    def test_parses_with_spaces(self):
        assert parse_size_to_bytes("2 KB") == 2048


class TestParseJsonItem:
    def test_dict(self):
        result = parse_json_item('{"key": "val"}')
        assert result == {"key": "val"}

    def test_list(self):
        result = parse_json_item('[{"key": "val"}]')
        assert result == {"key": "val"}

    def test_empty_list_raises(self):
        with pytest.raises(ParsingError, match="0 items"):
            parse_json_item("[]")

    def test_malformed_raises(self):
        with pytest.raises(ParsingError, match="Invalid JSON"):
            parse_json_item("not json")

    def test_scalar_raises(self):
        with pytest.raises(ParsingError):
            parse_json_item('"a string"')

    def test_int_raises(self):
        with pytest.raises(ParsingError):
            parse_json_item("42")


class TestParseJsonList:
    def test_list(self):
        result = parse_json_list('[{"a": 1}, {"b": 2}]')
        assert result == [{"a": 1}, {"b": 2}]

    def test_dict(self):
        result = parse_json_list('{"a": 1}')
        assert result == [{"a": 1}]

    def test_malformed_raises(self):
        with pytest.raises(ParsingError, match="Invalid JSON on line"):
            parse_json_list("not json")

    def test_json_array(self):
        result = parse_json_list('[{"id": "abc"}]')
        assert len(result) == 1
        assert result[0]["id"] == "abc"

    def test_single_object(self):
        result = parse_json_list('{"id": "abc"}')
        assert len(result) == 1
        assert result[0]["id"] == "abc"

    def test_ndjson_two_objects(self):
        ndjson = '{"id": "abc"}\n{"id": "def"}'
        result = parse_json_list(ndjson)
        assert len(result) == 2
        assert result[0]["id"] == "abc"
        assert result[1]["id"] == "def"

    def test_ndjson_with_blank_lines(self):
        ndjson = '{"id": "abc"}\n\n{"id": "def"}\n'
        result = parse_json_list(ndjson)
        assert len(result) == 2

    def test_empty_string_returns_empty_list(self):
        result = parse_json_list("")
        assert result == []

    def test_empty_list_returns_empty(self):
        result = parse_json_list("[]")
        assert result == []

    def test_garbage_raises(self):
        with pytest.raises(ParsingError):
            parse_json_list("not json at all")

    def test_partial_ndjson_raises_on_bad_line(self):
        ndjson = '{"id": "abc"}\nnot json\n{"id": "def"}'
        with pytest.raises(ParsingError, match="Invalid JSON on line 2"):
            parse_json_list(ndjson)

    def test_table_format_raises(self):
        table = "REPOSITORY    TAG       IMAGE ID\nalpine         latest    abc123"
        with pytest.raises(ParsingError):
            parse_json_list(table)


class TestMatchesAnyPattern:
    def test_default_false(self):
        assert matches_any_pattern("anything", ()) is False

    def test_with_patterns(self):
        assert matches_any_pattern("Not Found", ("not found", "no such")) is True
        assert matches_any_pattern("no such thing", ("not found", "no such")) is True
        assert matches_any_pattern("something else", ("not found", "no such")) is False


class TestParsePruneResult:
    def test_counts_deleted(self):
        result = parse_prune_result(DOCKER_PRUNE_OUTPUT)
        assert result.deleted == 2

    def test_parses_reclaimed_space(self):
        result = parse_prune_result(DOCKER_PRUNE_OUTPUT)
        assert result.reclaimed_bytes == int(1.5 * 1024**3)

    def test_empty(self):
        result = parse_prune_result("")
        assert result.deleted == 0
        assert result.reclaimed_bytes == 0

    def test_all_counts_deleted_sha256_lines(self):
        output = "deleted: sha256:abc123def456\ndeleted: sha256:789012abcdef\nTotal reclaimed space: 1.2GB\n"
        result = parse_prune_result(output)
        assert result == PruneResult(deleted=2, reclaimed_bytes=1288490188)
