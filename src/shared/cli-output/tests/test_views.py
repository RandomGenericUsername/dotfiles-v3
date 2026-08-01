from dataclasses import FrozenInstanceError

import pytest
from rich.console import Console

from cli_output.domain.views import (
    ConfigInfoView,
    CustomView,
    ErrorView,
    ListView,
    MessageView,
    RawView,
    ResultView,
)


class TestFrozenImmutability:
    def test_message_view_is_frozen(self):
        view = MessageView(text="hello")
        with pytest.raises(FrozenInstanceError):
            view.text = "changed"  # type: ignore[misc]

    def test_result_view_is_frozen(self):
        view = ResultView(success=True, fields={"a": 1})
        with pytest.raises(FrozenInstanceError):
            view.success = False  # type: ignore[misc]

    def test_custom_view_is_frozen(self):
        view = CustomView(plain="p", object={}, rich="r")
        with pytest.raises(FrozenInstanceError):
            view.plain = "other"  # type: ignore[misc]


class TestErrorView:
    def test_kind_accepts_arbitrary_strings(self):
        for kind in ["invalid_image", "boom", "any-old-kind", "path.with.dots"]:
            view = ErrorView(kind=kind, message="boom")
            assert view.kind == kind

    def test_details_defaults_to_empty(self):
        view = ErrorView(kind="x", message="boom")
        assert view.details == {}

    def test_details_carried(self):
        view = ErrorView(kind="x", message="boom", details={"path": "/x"})
        assert view.details == {"path": "/x"}


class TestCustomView:
    def test_carries_all_three_forms(self):
        view = CustomView(plain="line", object={"a": 1}, rich="[red]x[/red]")
        assert view.plain == "line"
        assert view.object == {"a": 1}
        assert view.rich == "[red]x[/red]"

    def test_rich_accepts_callable(self):
        def draw(console: Console) -> None:
            console.print("drawn")

        view = CustomView(plain="line", object={}, rich=draw)
        assert callable(view.rich)


class TestViewDefaults:
    def test_result_title_defaults(self):
        view = ResultView(success=True, fields={})
        assert view.title is None

    def test_list_defaults(self):
        view = ListView(columns=("a",), rows=(("1",),))
        assert view.title is None
        assert view.summary is None

    def test_config_defaults(self):
        view = ConfigInfoView(resolved_path="/x", sources=("a",), sections=())
        assert view.applied_overrides == ()

    def test_raw_defaults(self):
        view = RawView(content="x")
        assert view.content_type is None

    def test_progress_event_defaults(self):
        from cli_output.domain.views import ProgressEvent

        event = ProgressEvent(phase="p", message="m")
        assert event.done is None
        assert event.total is None
