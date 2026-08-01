import json
from io import StringIO

from rich.console import Console

from cli_output.adapters.output.json_renderer import JsonRenderer
from cli_output.adapters.output.plain_renderer import PlainRenderer
from cli_output.adapters.output.rich_renderer import RichRenderer
from cli_output.domain.views import CustomView


def test_plain_emits_custom_plain_form(capsys):
    PlainRenderer().custom(CustomView(plain="a\nb", object={}, rich=""))
    assert capsys.readouterr().out == "a\nb\n"


def test_plain_emits_verbatim_multiline(capsys):
    PlainRenderer().custom(CustomView(plain="line1\nline2\n", object={}, rich=""))
    assert capsys.readouterr().out == "line1\nline2\n\n"


def test_json_serializes_custom_object_form(capsys):
    JsonRenderer().custom(CustomView(plain="", object={"palette": ["#111111"]}, rich=""))
    data = json.loads(capsys.readouterr().out)
    assert data["palette"] == ["#111111"]


def test_rich_invokes_rich_callable():
    buffer = StringIO()
    renderer = RichRenderer(console=Console(file=buffer))
    renderer.custom(CustomView(plain="", object={}, rich=lambda c: c.print("swatch")))
    assert "swatch" in buffer.getvalue()


def test_rich_prints_markup_string():
    buffer = StringIO()
    renderer = RichRenderer(console=Console(file=buffer))
    renderer.custom(CustomView(plain="", object={}, rich="[bold]label[/bold]"))
    assert "label" in buffer.getvalue()
