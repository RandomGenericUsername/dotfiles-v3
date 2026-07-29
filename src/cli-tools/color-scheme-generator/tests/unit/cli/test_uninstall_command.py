from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from color_scheme_generator.domain.enums import Backend, RuntimeMode
from color_scheme_generator.domain.exceptions import ImageRemoveError
from color_scheme_generator.domain.models import (
    AppSettings,
    ContainerSettings,
    GenerationSettings,
    OutputSettings,
    RuntimeSettings,
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
        runtime=RuntimeSettings(mode=RuntimeMode.LOCAL),
        container=ContainerSettings(
            engine="docker",
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
) -> CliDependencies:
    return CliDependencies(
        backend_registry={},
        config_resolver=mock_config_resolver,
    )


class TestUninstallCommand:
    def test_uninstall_removes_all_images_with_confirmation(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        mock_container_engine: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        monkeypatch.setattr(
            "color_scheme_generator.cli.uninstall_cmd.create_container_engine",
            lambda engine: mock_container_engine,
        )
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, [
            "--output-format", "json", "uninstall", "--yes"
        ])
        assert result.exit_code == 0, f"stderr={result.stderr}"
        assert mock_container_engine.remove_image.call_count == 3

    def test_uninstall_yes_skips_prompt(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        mock_container_engine: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        monkeypatch.setattr(
            "color_scheme_generator.cli.uninstall_cmd.create_container_engine",
            lambda engine: mock_container_engine,
        )
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, [
            "--output-format", "json", "uninstall", "--yes"
        ])
        assert result.exit_code == 0, f"stderr={result.stderr}"
        assert mock_container_engine.remove_image.call_count == 3

    def test_uninstall_backend_wallust_removes_only_wallust(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        mock_container_engine: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        monkeypatch.setattr(
            "color_scheme_generator.cli.uninstall_cmd.create_container_engine",
            lambda engine: mock_container_engine,
        )
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, [
            "--output-format", "json", "uninstall", "--backend", "wallust", "--yes"
        ])
        assert result.exit_code == 0, f"stderr={result.stderr}"
        assert mock_container_engine.remove_image.call_count == 1

    def test_uninstall_dry_run_logs_without_removing(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        mock_container_engine: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        monkeypatch.setattr(
            "color_scheme_generator.cli.uninstall_cmd.create_container_engine",
            lambda engine: mock_container_engine,
        )
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, [
            "--output-format", "json", "uninstall", "--dry-run", "--yes"
        ])
        assert result.exit_code == 0, f"stderr={result.stderr}"
        mock_container_engine.remove_image.assert_not_called()

    def test_uninstall_removal_failure_outputs_error(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        mock_container_engine: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_container_engine.remove_image.side_effect = ImageRemoveError(
            image="csg-custom-docker:latest",
            reason="remove failed",
        )
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        monkeypatch.setattr(
            "color_scheme_generator.cli.uninstall_cmd.create_container_engine",
            lambda engine: mock_container_engine,
        )
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, [
            "--output-format", "json", "uninstall", "--backend", "custom", "--yes"
        ])
        assert result.exit_code == 1

    def test_uninstall_help_shows_expected_usage(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["uninstall", "--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.stdout
