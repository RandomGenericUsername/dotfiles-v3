from cli_output.adapters.output.json_renderer import JsonRenderer
from cli_output.adapters.output.plain_renderer import PlainRenderer
from cli_output.adapters.output.rich_renderer import RichRenderer
from cli_output.ports.renderer import Renderer


def test_json_renderer_conforms_to_protocol():
    assert isinstance(JsonRenderer(), Renderer)


def test_plain_renderer_conforms_to_protocol():
    assert isinstance(PlainRenderer(), Renderer)


def test_rich_renderer_conforms_to_protocol():
    assert isinstance(RichRenderer(), Renderer)


def test_structural_class_conforms():
    from contextlib import contextmanager

    from cli_output.domain.views import (
        ConfigInfoView,
        CustomView,
        ErrorView,
        ListView,
        MessageView,
        RawView,
        ResultView,
    )

    class Dummy:
        def message(self, view: MessageView) -> None:
            pass

        def result(self, view: ResultView) -> None:
            pass

        def list(self, view: ListView) -> None:
            pass

        def error(self, view: ErrorView) -> None:
            pass

        def config(self, view: ConfigInfoView) -> None:
            pass

        def raw(self, view: RawView) -> None:
            pass

        def custom(self, view: CustomView) -> None:
            pass

        @contextmanager
        def status(self, message: str):
            yield

        @contextmanager
        def progress(self, total: int, message: str):
            yield

    assert isinstance(Dummy(), Renderer)
