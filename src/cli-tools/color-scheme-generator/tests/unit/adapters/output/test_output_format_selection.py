from __future__ import annotations

from color_scheme_generator.domain.enums import OutputFormat
from color_scheme_generator.ports.output import OutputPort


class TestOutputFormatSelection:
    def test_create_output_adapter_returns_json_output(self):
        from color_scheme_generator.factory import create_output_adapter

        adapter = create_output_adapter(OutputFormat.JSON)
        from color_scheme_generator.adapters.output.json_output import JsonOutput

        assert isinstance(adapter, JsonOutput)
        assert isinstance(adapter, OutputPort)

    def test_create_output_adapter_returns_rich_output(self):
        from color_scheme_generator.factory import create_output_adapter

        adapter = create_output_adapter(OutputFormat.RICH)
        from color_scheme_generator.adapters.output.rich_output import RichOutput

        assert isinstance(adapter, RichOutput)
        assert isinstance(adapter, OutputPort)

    def test_create_output_adapter_returns_plain_output(self):
        from color_scheme_generator.factory import create_output_adapter

        adapter = create_output_adapter(OutputFormat.PLAIN)
        from color_scheme_generator.adapters.output.plain_output import PlainOutput

        assert isinstance(adapter, PlainOutput)
        assert isinstance(adapter, OutputPort)

    def test_create_output_adapter_json_default(self):
        from color_scheme_generator.factory import create_output_adapter

        adapter = create_output_adapter(OutputFormat.JSON)
        from color_scheme_generator.adapters.output.json_output import JsonOutput

        assert isinstance(adapter, JsonOutput)

    def test_all_adapters_satisfy_output_port_protocol(self):
        from color_scheme_generator.factory import create_output_adapter

        for fmt in OutputFormat:
            adapter = create_output_adapter(fmt)
            assert isinstance(adapter, OutputPort), f"{fmt} does not satisfy OutputPort"
