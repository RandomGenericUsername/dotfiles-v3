from cli_output.domain.enums import OutputFormat


class TestOutputFormat:
    def test_members(self):
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.RICH.value == "rich"
        assert OutputFormat.PLAIN.value == "plain"

    def test_str_returns_value(self):
        assert str(OutputFormat.JSON) == "json"
        assert str(OutputFormat.RICH) == "rich"
        assert str(OutputFormat.PLAIN) == "plain"

    def test_lowercase_construction(self):
        assert OutputFormat("json") is OutputFormat.JSON
        assert OutputFormat("rich") is OutputFormat.RICH
        assert OutputFormat("plain") is OutputFormat.PLAIN
