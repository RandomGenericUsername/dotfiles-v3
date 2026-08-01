from io import StringIO

import pytest
from rich.console import Console

from cli_output.adapters.factory import create_renderer
from cli_output.adapters.output.json_renderer import JsonRenderer
from cli_output.adapters.output.plain_renderer import PlainRenderer
from cli_output.adapters.output.rich_renderer import RichRenderer
from cli_output.domain.enums import OutputFormat
from cli_output.domain.views import MessageView


def test_factory_dispatches_on_format():
    assert isinstance(create_renderer(OutputFormat.JSON), JsonRenderer)
    assert isinstance(create_renderer(OutputFormat.PLAIN), PlainRenderer)
    assert isinstance(create_renderer(OutputFormat.RICH), RichRenderer)


def test_factory_forwards_console_to_rich():
    buffer = StringIO()
    renderer = create_renderer(OutputFormat.RICH, console=Console(file=buffer))
    assert isinstance(renderer, RichRenderer)
    renderer.message(MessageView(text="hi"))
    assert "hi" in buffer.getvalue()


def test_factory_creates_default_console_for_rich():
    renderer = create_renderer(OutputFormat.RICH)
    assert isinstance(renderer, RichRenderer)


def test_factory_rejects_unknown_format():
    with pytest.raises(ValueError):
        create_renderer("bogus")  # type: ignore[arg-type]
