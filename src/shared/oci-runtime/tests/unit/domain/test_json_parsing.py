import pytest

from oci_runtime.domain.json_parsing import parse_json_list
from oci_runtime.ports.parsers import ParsingError


class TestParseJsonList:
    def test_parse_json_list_pretty_printed_raises_informative(self):
        with pytest.raises(ParsingError) as exc:
            parse_json_list('{"id": "abc",\n}')
        msg = str(exc.value)
        assert "pretty-printed" in msg
        assert "--format" in msg

    def test_parse_json_list_ndjson_still_works(self):
        result = parse_json_list('{"id":"a"}\n{"id":"b"}')
        assert len(result) == 2
