from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from color_scheme_generator.adapters.local_processor import LocalProcessor
from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import InvalidImageError
from color_scheme_generator.domain.models import (
    AppSettings,
    ContainerSettings,
    GenerationResult,
    GenerationSettings,
    OutputSettings,
    RuntimeSettings,
    TemplateSettings,
)
from color_scheme_generator.factory import CliDependencies


def _default_app_settings(**overrides: object) -> AppSettings:
    return AppSettings(
        output=OutputSettings(
            directory=Path("/tmp/color-scheme"),
            default_formats=(),
            overwrite=False,
        ),
        generation=GenerationSettings(
            backend=Backend.CUSTOM,
            default_params={},
        ),
        template=TemplateSettings(
            templates_dir=None,
            custom_templates_dir=None,
        ),
        runtime=RuntimeSettings(
            mode=overrides.get("runtime_mode", "local"),  # type: ignore[arg-type]
        ),
        container=ContainerSettings(
            image_prefix="csg",
            image_tag="latest",
            timeout_seconds=60,
            memory_limit="512m",
            mount_timeout_seconds=30,
        ),
    )


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


@pytest.fixture
def mock_config_resolver() -> MagicMock:
    mock = MagicMock()
    mock.resolve.return_value = _default_app_settings()
    return mock


@pytest.fixture
def mock_backend_catalog_loader() -> MagicMock:
    return MagicMock()


class TestCliGenerate:
    @pytest.fixture
    def mock_deps(
        self, mock_processor, mock_output, mock_config_resolver, mock_backend_catalog_loader
    ) -> CliDependencies:
        return CliDependencies(
            backend_registry=MagicMock(),
            backend_catalog_loader=mock_backend_catalog_loader,
            config_resolver=mock_config_resolver,
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
            lambda _fmt, **kwargs: mock_output,
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
            lambda _fmt, **kwargs: mock_output,
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
        assert "image_path" in result.stdout or "IMAGE_PATH" in result.stdout

    def test_help_shows_new_flags(self, runner: CliRunner) -> None:
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["generate", "--help"])
        assert "--backend" in result.stdout
        assert "--param" in result.stdout
        assert "--format" in result.stdout or "-f" in result.stdout
        assert "--output-dir" in result.stdout or "-o" in result.stdout

    def test_build_deps_returns_proper_cli_dependencies(self) -> None:
        from color_scheme_generator.adapters.local_processor import LocalProcessor
        from color_scheme_generator.cli.main import build_deps
        from color_scheme_generator.factory import CliDependencies

        deps = build_deps()
        assert isinstance(deps, CliDependencies)
        assert deps.backend_registry is not None
        assert deps.output_adapter is None
        assert isinstance(deps.processor, LocalProcessor)
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
