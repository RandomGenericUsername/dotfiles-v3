from __future__ import annotations

from typing import Any

import pytest
from typer.testing import CliRunner

from color_scheme_generator.cli.main import app
from color_scheme_generator.domain.exceptions import ColorSchemeError


class _RecordingOutputAdapter:
    """OutputPort-conforming adapter that records calls instead of printing."""

    def __init__(self) -> None:
        self.messages: list[str] = []
        self.process_result_calls: list[object] = []
        self.errors: list[ColorSchemeError] = []
        self.config_info_calls: list[Any] = []

    def process_result(self, result: object) -> None:
        self.process_result_calls.append(result)

    def error(self, exc: ColorSchemeError) -> None:
        self.errors.append(exc)

    def palette_display(self, scheme: object) -> None:
        self.messages.append("palette_display")

    def message(self, msg: str) -> None:
        self.messages.append(msg)

    def config_info(
        self,
        settings: object,
        backends: dict,
        sources: list[str],
        templates: object = None,
    ) -> None:
        self.config_info_calls.append((settings, backends, sources, templates))


@pytest.fixture
def recording_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> _RecordingOutputAdapter:
    adapter = _RecordingOutputAdapter()
    monkeypatch.setattr(
        "color_scheme_generator.cli.main.create_output_adapter",
        lambda *a, **kw: adapter,
    )
    return adapter


class TestHelpConfigStrategyXfail:
    @pytest.mark.xfail(
        reason=(
            "--help text omits the CLI --config priority step (lists 4 strategies, resolver has 5)"
        ),
        strict=False,
    )
    def test_help_reflects_all_five_config_strategies(self) -> None:
        result = CliRunner().invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "1. --config" in result.output


class TestCommandsRouteThroughOutputPortXfail:
    @pytest.mark.xfail(
        reason="install uses isinstance dispatch on concrete adapters, bypassing OutputPort",
        strict=False,
    )
    def test_install_routes_through_output_port(
        self, recording_adapter: _RecordingOutputAdapter
    ) -> None:
        result = CliRunner().invoke(app, ["install", "--dry-run", "--backend", "custom"])
        assert result.exit_code == 0
        assert recording_adapter.messages or recording_adapter.process_result_calls

    @pytest.mark.xfail(
        reason="uninstall uses isinstance dispatch on concrete adapters, bypassing OutputPort",
        strict=False,
    )
    def test_uninstall_routes_through_output_port(
        self, recording_adapter: _RecordingOutputAdapter
    ) -> None:
        result = CliRunner().invoke(
            app,
            ["uninstall", "--dry-run", "--backend", "custom", "--yes"],
        )
        assert result.exit_code == 0
        assert recording_adapter.messages or recording_adapter.process_result_calls

    @pytest.mark.xfail(
        reason="version uses isinstance dispatch on concrete adapters, bypassing OutputPort",
        strict=False,
    )
    def test_version_routes_through_output_port(
        self, recording_adapter: _RecordingOutputAdapter
    ) -> None:
        result = CliRunner().invoke(app, ["version"])
        assert result.exit_code == 0
        assert recording_adapter.messages or recording_adapter.process_result_calls

    @pytest.mark.xfail(
        reason="list-backends uses isinstance dispatch on concrete adapters, bypassing OutputPort",
        strict=False,
    )
    def test_list_backends_routes_through_output_port(
        self, recording_adapter: _RecordingOutputAdapter
    ) -> None:
        result = CliRunner().invoke(app, ["list-backends"])
        assert result.exit_code == 0
        assert recording_adapter.messages or recording_adapter.process_result_calls
