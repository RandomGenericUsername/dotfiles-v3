from io import StringIO

import pytest
from rich.console import Console

from cli_output.adapters.output.json_renderer import JsonRenderer
from cli_output.adapters.output.plain_renderer import PlainRenderer
from cli_output.adapters.output.rich_renderer import RichRenderer
from cli_output.domain.views import ErrorView

ERROR = ErrorView(kind="x", message="boom")


@pytest.mark.parametrize("renderer", [JsonRenderer(), PlainRenderer()], ids=["json", "plain"])
def test_errors_route_to_stderr_capture(renderer, capsys):
    renderer.error(ERROR)
    captured = capsys.readouterr()
    assert captured.err != ""
    assert captured.out == ""


def test_rich_error_routes_to_stderr(capsys):
    renderer = RichRenderer(console=Console(file=StringIO()))
    renderer.error(ERROR)
    captured = capsys.readouterr()
    assert "boom" in captured.err
    assert captured.out == ""


def test_plain_error_prefix(capsys):
    PlainRenderer().error(ErrorView(kind="boom", message="bad"))
    captured = capsys.readouterr()
    assert "error: boom: bad" in captured.err


def test_json_error_is_valid_json(capsys):
    JsonRenderer().error(ErrorView(kind="boom", message="bad", details={"path": "/x"}))
    import json

    data = json.loads(capsys.readouterr().err)
    assert data["kind"] == "boom"
    assert data["message"] == "bad"
    assert data["details"] == {"path": "/x"}
