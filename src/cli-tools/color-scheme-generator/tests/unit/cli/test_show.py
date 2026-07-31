from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from color_scheme_generator.domain.exceptions import InvalidImageError
from color_scheme_generator.factory import CliDependencies
from tests.conftest import FakeProcessor


def _invoke(
    runner: CliRunner,
    deps: CliDependencies,
    args: list[str],
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: deps)
    from color_scheme_generator.cli.main import app

    return runner.invoke(app, args)


class TestCliShow:
    def test_show_smoke_outputs_json_scheme(
        self,
        runner: CliRunner,
        cli_deps_with_processor: CliDependencies,
        fake_processor: FakeProcessor,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        result = _invoke(
            runner,
            cli_deps_with_processor,
            ["show", "/tmp/test.png", "--backend", "custom"],
            monkeypatch,
        )
        assert result.exit_code == 0, f"stderr={result.stderr}"
        assert len(fake_processor.calls) == 1
        assert fake_processor.calls[0]["command"] == "process_show"
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["color_scheme"]["backend"] == "custom"

    def test_invalid_image_path_exits_with_code_1(
        self,
        runner: CliRunner,
        cli_deps_with_processor: CliDependencies,
        fake_processor: FakeProcessor,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fake_processor.error = InvalidImageError(
            image_path=Path("/nonexistent.jpg"), reason="file not found"
        )
        result = _invoke(
            runner,
            cli_deps_with_processor,
            ["show", "/nonexistent.jpg"],
            monkeypatch,
        )
        assert result.exit_code == 1
        error_payload = json.loads(result.stderr)
        assert error_payload["error"]["type"] == "InvalidImageError"
        assert "nonexistent.jpg" in error_payload["error"]["message"]

    def test_show_renders_via_process_result(
        self,
        runner: CliRunner,
        cli_deps_with_processor: CliDependencies,
        fake_processor: FakeProcessor,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        result = _invoke(
            runner,
            cli_deps_with_processor,
            ["show", "/tmp/test.png"],
            monkeypatch,
        )
        assert result.exit_code == 0, f"stderr={result.stderr}"
        payload = json.loads(result.stdout)
        assert "color_scheme" in payload
        assert payload["color_scheme"]["colors"] is not None

    def test_help_output_shows_expected_usage(self, runner: CliRunner) -> None:
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["show", "--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.stdout
        assert "image_path" in result.stdout or "IMAGE_PATH" in result.stdout

    def test_help_shows_new_flags(self, runner: CliRunner) -> None:
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["show", "--help"])
        assert "--backend" in result.stdout
        assert "--param" in result.stdout
        assert "--format" not in result.stdout
        assert "--output-dir" not in result.stdout
        assert "--dry-run" not in result.stdout
