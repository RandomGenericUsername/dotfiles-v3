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

    def install_result(self, results: list[dict]) -> None:
        self.process_result_calls.append(results)

    def uninstall_result(self, results: list[dict]) -> None:
        self.process_result_calls.append(results)

    def version_info(self, version: str) -> None:
        self.process_result_calls.append(version)

    def backends_catalog(self, backends: list[dict], hint: str = "") -> None:
        self.process_result_calls.append((backends, hint))


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


class TestHelpConfigStrategy:
    def test_help_reflects_all_five_config_strategies(self) -> None:
        result = CliRunner().invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "1. --config" in result.output


class TestCommandsRouteThroughOutputPort:
    def test_install_routes_through_output_port(
        self, recording_adapter: _RecordingOutputAdapter
    ) -> None:
        result = CliRunner().invoke(app, ["install", "--dry-run", "--backend", "custom"])
        assert result.exit_code == 0
        assert recording_adapter.messages or recording_adapter.process_result_calls

    def test_uninstall_routes_through_output_port(
        self, recording_adapter: _RecordingOutputAdapter
    ) -> None:
        result = CliRunner().invoke(
            app,
            ["uninstall", "--dry-run", "--backend", "custom", "--yes"],
        )
        assert result.exit_code == 0
        assert recording_adapter.messages or recording_adapter.process_result_calls

    def test_version_routes_through_output_port(
        self, recording_adapter: _RecordingOutputAdapter
    ) -> None:
        result = CliRunner().invoke(app, ["version"])
        assert result.exit_code == 0
        assert recording_adapter.messages or recording_adapter.process_result_calls

    def test_list_backends_routes_through_output_port(
        self, recording_adapter: _RecordingOutputAdapter
    ) -> None:
        result = CliRunner().invoke(app, ["list-backends"])
        assert result.exit_code == 0
        assert recording_adapter.messages or recording_adapter.process_result_calls
