from io import StringIO

import pytest
from rich.console import Console

from cli_output.adapters.output.json_renderer import JsonRenderer
from cli_output.adapters.output.plain_renderer import PlainRenderer
from cli_output.adapters.output.rich_renderer import RichRenderer


class TestRichStatus:
    def test_status_is_live(self):
        buffer = StringIO()
        renderer = RichRenderer(
            console=Console(file=buffer, force_terminal=True, color_system=None)
        )
        with renderer.status("working"):
            pass
        assert buffer.getvalue() != ""

    def test_status_returns_context_manager(self):
        renderer = RichRenderer(console=Console(file=StringIO()))
        assert hasattr(renderer.status("working"), "__enter__")


class TestRichProgress:
    def test_advance_advances_bar(self):
        buffer = StringIO()
        renderer = RichRenderer(console=Console(file=buffer, force_terminal=False))
        with renderer.progress(total=3, message="batch") as bar:
            assert bar is not None
            assert hasattr(bar, "advance")
            bar.advance()
        assert buffer.getvalue() != ""

    def test_advance_by_amount(self):
        buffer = StringIO()
        renderer = RichRenderer(console=Console(file=buffer, force_terminal=False))
        with renderer.progress(total=3, message="batch") as bar:
            bar.advance(2)
        assert buffer.getvalue() != ""


class TestJsonSilent:
    def test_status_is_silent(self, capsys):
        renderer = JsonRenderer()
        with renderer.status("working"):
            pass
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_progress_is_silent(self, capsys):
        renderer = JsonRenderer()
        with renderer.progress(total=3, message="batch") as bar:
            bar.advance()
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""


class TestPlainSilent:
    def test_status_is_silent(self, capsys):
        renderer = PlainRenderer()
        with renderer.status("working"):
            pass
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_progress_is_silent(self, capsys):
        renderer = PlainRenderer()
        with renderer.progress(total=3, message="batch") as bar:
            bar.advance()
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""


@pytest.mark.parametrize(
    "renderer",
    [JsonRenderer(), PlainRenderer()],
    ids=["json", "plain"],
)
def test_noop_managers_are_valid(renderer):
    with renderer.status("working"):
        pass
    with renderer.progress(total=1, message="m") as bar:
        bar.advance()
