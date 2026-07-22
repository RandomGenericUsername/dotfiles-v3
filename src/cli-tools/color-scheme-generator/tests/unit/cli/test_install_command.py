from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from color_scheme_generator.domain.enums import Backend, ContainerEngine, RuntimeMode
from color_scheme_generator.domain.exceptions import ImageBuildError
from color_scheme_generator.domain.models import (
    AppSettings,
    ContainerSettings,
    GenerationSettings,
    OutputSettings,
    RuntimeSettings,
    TemplateSettings,
)
from color_scheme_generator.factory import CliDependencies


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_config_resolver() -> MagicMock:
    resolver = MagicMock()
    resolver.resolve.return_value = AppSettings(
        output=OutputSettings(directory="/tmp/out", default_formats=(), overwrite=False),
        generation=GenerationSettings(backend=Backend.CUSTOM, default_params={}),
        template=TemplateSettings(templates_dir=None, custom_templates_dir=None),
        runtime=RuntimeSettings(mode=RuntimeMode.LOCAL, engine=ContainerEngine.DOCKER),
        container=ContainerSettings(
            image_prefix="csg",
            image_tag="latest",
            timeout_seconds=60,
            memory_limit="512m",
            mount_timeout_seconds=30,
        ),
    )
    return resolver


@pytest.fixture
def mock_container_engine() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_deps(
    mock_config_resolver: MagicMock,
    mock_container_engine: MagicMock,
) -> CliDependencies:
    return CliDependencies(
        backend_registry={},
        config_resolver=mock_config_resolver,
    )


class TestInstallCommand:
    def test_install_builds_all_three_images(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        mock_container_engine: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        monkeypatch.setattr(
            "color_scheme_generator.cli.install_cmd.create_container_engine",
            lambda engine: mock_container_engine,
        )
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--output-format", "json", "install"])
        assert result.exit_code == 0, f"stderr={result.stderr}"
        assert mock_container_engine.build_image.call_count == 3

    def test_install_backend_custom_builds_only_custom(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        mock_container_engine: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        monkeypatch.setattr(
            "color_scheme_generator.cli.install_cmd.create_container_engine",
            lambda engine: mock_container_engine,
        )
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--output-format", "json", "install", "--backend", "custom"])
        assert result.exit_code == 0, f"stderr={result.stderr}"
        assert mock_container_engine.build_image.call_count == 1

    def test_install_dry_run_logs_without_building(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        mock_container_engine: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        monkeypatch.setattr(
            "color_scheme_generator.cli.install_cmd.create_container_engine",
            lambda engine: mock_container_engine,
        )
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--output-format", "json", "install", "--dry-run"])
        assert result.exit_code == 0, f"stderr={result.stderr}"
        mock_container_engine.build_image.assert_not_called()

    def test_install_engine_podman(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        mock_container_engine: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        monkeypatch.setattr(
            "color_scheme_generator.cli.install_cmd.create_container_engine",
            lambda engine: mock_container_engine,
        )
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, [
            "--output-format", "json", "install", "--engine", "podman"
        ])
        assert result.exit_code == 0, f"stderr={result.stderr}"
        assert mock_container_engine.build_image.call_count == 3

    def test_install_build_failure_outputs_error(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        mock_container_engine: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_container_engine.build_image.side_effect = ImageBuildError(
            image="csg-color-scheme-custom:latest",
            reason="build failed",
        )
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        monkeypatch.setattr(
            "color_scheme_generator.cli.install_cmd.create_container_engine",
            lambda engine: mock_container_engine,
        )
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, [
            "--output-format", "json", "install", "--backend", "custom"
        ])
        assert result.exit_code == 1

    def test_install_help_shows_expected_usage(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["install", "--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.stdout
