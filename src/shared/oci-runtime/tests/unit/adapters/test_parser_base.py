from oci_runtime.adapters.parser.base import BaseCliParser, parse_size_to_bytes


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

    def test_returns_zero_for_empty_string(self):
        assert parse_size_to_bytes("") == 0

    def test_returns_zero_for_no_unit(self):
        assert parse_size_to_bytes("9999") == 0

    def test_parses_with_spaces(self):
        assert parse_size_to_bytes("2 KB") == 2048


class TestBaseCliParser:
    def setup_method(self):
        self.parser = BaseCliParser()

    def test_parse_prune_counts_deleted(self):
        result = self.parser.parse_prune(DOCKER_PRUNE_OUTPUT)
        assert result["deleted"] == 2

    def test_parse_prune_parses_reclaimed_space(self):
        result = self.parser.parse_prune(DOCKER_PRUNE_OUTPUT)
        assert result["reclaimed_bytes"] == int(1.5 * 1024**3)

    def test_parse_prune_empty(self):
        result = self.parser.parse_prune("")
        assert result["deleted"] == 0
        assert result["reclaimed_bytes"] == 0
