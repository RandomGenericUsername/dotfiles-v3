from __future__ import annotations

from icon_templates_renderer.domain.enums import OutputFormat, Verbosity


def test_output_format_values() -> None:
    assert OutputFormat.JSON.value == "json"
    assert OutputFormat.RICH.value == "rich"
    assert OutputFormat.PLAIN.value == "plain"
    assert str(OutputFormat.PLAIN) == "plain"


def test_verbosity_values() -> None:
    assert Verbosity.QUIET.value == 0
    assert Verbosity.NORMAL.value == 1
    assert Verbosity.VERBOSE.value == 2
    assert Verbosity.DEBUG.value == 3
