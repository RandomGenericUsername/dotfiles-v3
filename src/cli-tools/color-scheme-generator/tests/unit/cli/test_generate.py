from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from color_scheme_generator.adapters.local_processor import LocalProcessor
from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import InvalidImageError
from color_scheme_generator.domain.models import GenerationResult
from color_scheme_generator.factory import CliDependencies


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_processor() -> MagicMock:
    mock = MagicMock(spec=LocalProcessor)
    mock.process_generate.return_value = GenerationResult(
        success=True,
        color_scheme=None,
        output_files=(),
        backend=Backend.CUSTOM,
        stderr="",
        return_code=0,
        duration=0.5,
    )
    return mock


@pytest.fixture
def mock_output() -> MagicMock:
    return MagicMock()


class TestCliGenerate:
    @pytest.fixture
    def mock_deps(self, mock_processor, mock_output) -> CliDependencies:
        from color_scheme_generator.factory import CliDependencies
        return CliDependencies(
            backend_registry=MagicMock(),
            output_adapter=mock_output,
            processor=mock_processor,
        )

    def test_successful_generate_exit_code_0(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        mock_processor: MagicMock,
        mock_output: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        monkeypatch.setattr(
            "color_scheme_generator.cli.main.create_output_adapter",
            lambda _fmt: mock_output,
        )
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["generate", "/tmp/test.jpg"])
        assert result.exit_code == 0
        mock_processor.process_generate.assert_called_once()
        mock_output.process_result.assert_called_once()

    def test_invalid_image_path_exits_with_code_1(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        mock_processor: MagicMock,
        mock_output: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_processor.process_generate.side_effect = InvalidImageError(
            image_path=Path("/nonexistent.jpg"), reason="file not found"
        )
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        monkeypatch.setattr(
            "color_scheme_generator.cli.main.create_output_adapter",
            lambda _fmt: mock_output,
        )
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["generate", "/nonexistent.jpg"])
        assert result.exit_code == 1
        mock_output.error.assert_called_once()

    def test_help_output_shows_expected_usage(self, runner: CliRunner) -> None:
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["generate", "--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.stdout
        assert "IMAGE_PATH" in result.stdout

    def test_help_has_no_out_of_scope_flags(self, runner: CliRunner) -> None:
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["generate", "--help"])
        assert "--backend" not in result.stdout
        assert "--output-dir" not in result.stdout
        assert "--param" not in result.stdout
        assert "-f" not in result.stdout

    def test_build_deps_returns_proper_cli_dependencies(self) -> None:
        from color_scheme_generator.cli.main import build_deps
        from color_scheme_generator.factory import CliDependencies

        deps = build_deps()
        assert isinstance(deps, CliDependencies)
        assert deps.backend_registry is not None
        assert deps.output_adapter is None
        assert isinstance(deps.processor, LocalProcessor)


class TestCliPackage:
    def test_cli_package_importable(self) -> None:
        from color_scheme_generator.cli import main  # noqa: F401

        assert main is not None

    def test_console_scripts_entry_point(self) -> None:
        from color_scheme_generator.cli.main import app

        assert app is not None
        assert callable(app)
