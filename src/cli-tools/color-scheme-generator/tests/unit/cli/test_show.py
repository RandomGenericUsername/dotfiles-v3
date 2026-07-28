from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import InvalidImageError
from color_scheme_generator.domain.models import (
    AppSettings,
    Color,
    ColorScheme,
    ContainerSettings,
    GenerationResult,
    GenerationSettings,
    OutputSettings,
    RuntimeSettings,
    TemplateSettings,
)
from color_scheme_generator.factory import CliDependencies


def _make_color_scheme() -> ColorScheme:
    return ColorScheme(
        background=Color(hex="#000000", rgb=(0, 0, 0)),
        foreground=Color(hex="#ffffff", rgb=(255, 255, 255)),
        cursor=Color(hex="#ffffff", rgb=(255, 255, 255)),
        colors=tuple(Color(hex="#000000", rgb=(0, 0, 0)) for _ in range(16)),
        source_image=Path("/tmp/test.jpg"),
        backend=Backend.CUSTOM,
        generated_at=datetime.now(),
    )


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
            engine=overrides.get("container_engine", "docker"),  # type: ignore[arg-type]
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
    mock = MagicMock()
    mock.process_show.return_value = GenerationResult(
        success=True,
        color_scheme=_make_color_scheme(),
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


@pytest.fixture
def mock_deps(
    mock_processor, mock_output, mock_config_resolver, mock_backend_catalog_loader
) -> CliDependencies:
    return CliDependencies(
        backend_registry=MagicMock(),
        backend_catalog_loader=mock_backend_catalog_loader,
        config_resolver=mock_config_resolver,
        output_adapter=mock_output,
        processor=mock_processor,
    )


class TestCliShow:
    def test_successful_show_exit_code_0(
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

        result = runner.invoke(app, ["show", "/tmp/test.jpg"])
        assert result.exit_code == 0
        mock_processor.process_show.assert_called_once()
        mock_output.process_result.assert_called_once()

    def test_invalid_image_path_exits_with_code_1(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        mock_processor: MagicMock,
        mock_output: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_processor.process_show.side_effect = InvalidImageError(
            image_path=Path("/nonexistent.jpg"), reason="file not found"
        )
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        monkeypatch.setattr(
            "color_scheme_generator.cli.main.create_output_adapter",
            lambda _fmt, **kwargs: mock_output,
        )
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["show", "/nonexistent.jpg"])
        assert result.exit_code == 1
        mock_output.error.assert_called_once()
        call_arg = mock_output.error.call_args[0][0]
        assert isinstance(call_arg, InvalidImageError)
        assert "nonexistent.jpg" in str(call_arg)

    def test_calls_palette_display_not_process_result(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        mock_output: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        monkeypatch.setattr(
            "color_scheme_generator.cli.main.create_output_adapter",
            lambda _fmt, **kwargs: mock_output,
        )
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["show", "/tmp/test.jpg"])
        assert result.exit_code == 0
        mock_output.process_result.assert_called_once()
        mock_output.palette_display.assert_not_called()

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
