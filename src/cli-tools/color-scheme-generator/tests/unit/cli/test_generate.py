from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from color_scheme_generator.domain.enums import Backend
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


class TestCliGenerate:
    def test_generate_smoke_writes_dummy_files(
        self,
        runner: CliRunner,
        cli_deps_with_processor: CliDependencies,
        fake_processor: FakeProcessor,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        output_dir = tmp_path / "out"
        result = _invoke(
            runner,
            cli_deps_with_processor,
            [
                "generate",
                "/tmp/test.png",
                "--backend",
                "custom",
                "--param",
                "saturation=0.5",
                "--format",
                "json",
                "-o",
                str(output_dir),
            ],
            monkeypatch,
        )
        assert result.exit_code == 0, f"stderr={result.stderr}"
        assert len(fake_processor.calls) == 1
        call = fake_processor.calls[0]
        assert call["command"] == "process_generate"
        request = call["request"]
        config = request.config
        assert config.backend is Backend.CUSTOM
        assert config.params.get("saturation") == "0.5"
        assert config.output_dir == output_dir
        assert (output_dir / "colors.json").exists()
        assert (output_dir / "colors.json").read_text() == "dummy"

    def test_generate_outputs_valid_json(
        self,
        runner: CliRunner,
        cli_deps_with_processor: CliDependencies,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        result = _invoke(
            runner,
            cli_deps_with_processor,
            [
                "generate",
                "/tmp/test.png",
                "-f",
                "json",
                "-o",
                str(tmp_path),
            ],
            monkeypatch,
        )
        assert result.exit_code == 0, f"stderr={result.stderr}"
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["backend"] == "custom"
        assert payload["color_scheme"]["colors"] is not None

    def test_generate_invalid_image_exits_with_code_1(
        self,
        runner: CliRunner,
        cli_deps_with_processor: CliDependencies,
        fake_processor: FakeProcessor,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fake_processor.error = InvalidImageError(
            image_path=Path("/nonexistent.jpg"), reason="file not found"
        )
        result = _invoke(
            runner,
            cli_deps_with_processor,
            ["generate", "/nonexistent.jpg", "-o", str(tmp_path)],
            monkeypatch,
        )
        assert result.exit_code == 1
        error_payload = json.loads(result.stderr)
        assert error_payload["success"] is False
        assert error_payload["error"]["type"] == "InvalidImageError"
        assert "nonexistent.jpg" in error_payload["error"]["message"]

    def test_help_output_shows_expected_usage(self, runner: CliRunner) -> None:
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["generate", "--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.stdout
        assert "image_path" in result.stdout or "IMAGE_PATH" in result.stdout

    def test_help_shows_new_flags(self, runner: CliRunner) -> None:
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["generate", "--help"])
        assert "--backend" in result.stdout
        assert "--param" in result.stdout
        assert "--format" in result.stdout or "-f" in result.stdout
        assert "--output-dir" in result.stdout or "-o" in result.stdout

    def test_build_deps_returns_proper_cli_dependencies(self) -> None:
        from color_scheme_generator.cli.main import build_deps
        from color_scheme_generator.factory import CliDependencies

        deps = build_deps()
        assert isinstance(deps, CliDependencies)
        assert deps.backend_registry is not None
        assert deps.output_adapter is None
        # processor is now built lazily (not a deps-level concern)
        assert deps.template_dir_resolver is not None
        assert deps.template_renderer is not None


class TestCliPackage:
    def test_cli_package_importable(self) -> None:
        from color_scheme_generator.cli import main  # noqa: F401

        assert main is not None

    def test_console_scripts_entry_point(self) -> None:
        from color_scheme_generator.cli.main import app

        assert app is not None
        assert callable(app)
