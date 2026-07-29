from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from color_scheme_generator.domain.enums import Backend, RuntimeMode
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
        assert mock_container_engine.build_image.call_count == 4
        images = [call[0][1] for call in mock_container_engine.build_image.call_args_list]
        assert "csg-base-docker:latest" in images
        assert "csg-custom-docker:latest" in images
        assert "csg-pywal-docker:latest" in images
        assert "csg-wallust-docker:latest" in images

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
        assert mock_container_engine.build_image.call_count == 2

    def test_install_engine_docker(
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
            "--output-format", "json", "install", "--container-engine", "docker"
        ])
        assert result.exit_code == 0, f"stderr={result.stderr}"
        calls = mock_container_engine.build_image.call_args_list
        assert len(calls) == 4
        images = [call[0][1] for call in calls]
        assert "csg-base-docker:latest" in images
        assert "csg-custom-docker:latest" in images

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
            "--output-format", "json", "install", "--container-engine", "podman"
        ])
        assert result.exit_code == 0, f"stderr={result.stderr}"
        calls = mock_container_engine.build_image.call_args_list
        assert len(calls) == 4
        images = [call[0][1] for call in calls]
        assert "csg-base-podman:latest" in images
        assert "csg-custom-podman:latest" in images
        assert "csg-pywal-podman:latest" in images
        assert "csg-wallust-podman:latest" in images
        backend_calls = [call for call in calls if call[0][1] != "csg-base-podman:latest"]
        for call in backend_calls:
            context = call[0][0]
            build_args = getattr(context, "build_args", None)
            assert build_args is not None, f"Missing build_args in call: {call}"
            assert build_args.get("BASE_IMAGE") == "csg-base-podman:latest"

    def test_install_build_failure_outputs_error(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        mock_container_engine: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_container_engine.build_image.side_effect = ImageBuildError(
            image="csg-custom-docker:latest",
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
