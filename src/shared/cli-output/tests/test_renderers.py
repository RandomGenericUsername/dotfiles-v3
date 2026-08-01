import json
from io import StringIO

import pytest
from rich.console import Console

from cli_output.adapters.output.json_renderer import JsonRenderer
from cli_output.adapters.output.plain_renderer import PlainRenderer
from cli_output.adapters.output.rich_renderer import RichRenderer
from cli_output.domain.views import (
    ConfigInfoView,
    ErrorView,
    ListView,
    MessageView,
    RawView,
    ResultView,
)

MESSAGE = MessageView(text="hello")
RESULT = ResultView(success=True, fields={"output_path": "/x.png"}, title="Done")
LIST = ListView(
    columns=("name", "size"),
    rows=(("a", 1), ("b", 2)),
    title="Files",
    summary={"count": 2},
)
ERROR = ErrorView(kind="boom", message="bad", details={"path": "/x"})
CONFIG = ConfigInfoView(
    resolved_path="/cfg.yaml",
    sources=("env", "cli"),
    sections=(("main", {"enabled": True}),),
    applied_overrides=({"a": 1},),
)
RAW = RawView(content="raw\ncontent", content_type="text/plain")


@pytest.fixture(params=["json", "plain", "rich"])
def renderer(request, capsys):
    if request.param == "json":
        return JsonRenderer(), "json", lambda: capsys.readouterr().out
    if request.param == "plain":
        return PlainRenderer(), "plain", lambda: capsys.readouterr().out
    buffer = StringIO()
    rich = RichRenderer(console=Console(file=buffer))
    return rich, "rich", lambda: buffer.getvalue()


def test_message(renderer):
    r, kind, out = renderer
    r.message(MESSAGE)
    if kind == "json":
        assert json.loads(out())["message"] == "hello"
    elif kind == "plain":
        assert out() == "hello\n"
    else:
        assert "hello" in out()


def test_result(renderer):
    r, kind, out = renderer
    r.result(RESULT)
    if kind == "json":
        data = json.loads(out())
        assert data["success"] is True
        assert data["output_path"] == "/x.png"
    elif kind == "plain":
        text = out()
        assert "success: true" in text
        assert "output_path: /x.png" in text
    else:
        assert "Done" in out()


def test_list(renderer):
    r, kind, out = renderer
    r.list(LIST)
    if kind == "json":
        data = json.loads(out())
        assert data["columns"] == ["name", "size"]
        assert data["rows"] == [["a", 1], ["b", 2]]
        assert data["summary"]["count"] == 2
    elif kind == "plain":
        text = out()
        assert "name" in text
        assert "size" in text
    else:
        assert "name" in out()


def test_config(renderer):
    r, kind, out = renderer
    r.config(CONFIG)
    if kind == "json":
        data = json.loads(out())
        assert data["resolved_path"] == "/cfg.yaml"
        assert data["sources"] == ["env", "cli"]
        assert data["sections"]["main"]["enabled"] is True
    elif kind == "plain":
        text = out()
        assert "/cfg.yaml" in text
        assert "env, cli" in text
    else:
        assert "/cfg.yaml" in out()


def test_raw(renderer):
    r, kind, out = renderer
    r.raw(RAW)
    if kind == "json":
        assert json.loads(out())["content"] == "raw\ncontent"
    elif kind == "plain":
        assert out() == "raw\ncontent"
    else:
        assert "raw" in out()


def test_error_shape(renderer, capsys):
    r, kind, _ = renderer
    r.error(ERROR)
    captured = capsys.readouterr()
    assert "boom" in captured.err
    if kind != "rich":
        assert captured.out == ""
