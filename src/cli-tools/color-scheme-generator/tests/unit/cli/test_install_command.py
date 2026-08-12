from __future__ import annotations

from pathlib import Path
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

    def test_install_passes_config_path_to_resolver(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        mock_config_resolver: MagicMock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        config_file = tmp_path / "settings.toml"
        config_file.write_text("")
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, [
            "install", "--config", str(config_file), "--dry-run",
        ])
        assert result.exit_code == 0, f"stderr={result.stderr}"
        mock_config_resolver.resolve.assert_called_once()
        call_kwargs = mock_config_resolver.resolve.call_args[1]
        assert call_kwargs.get("explicit_path") is not None
        assert "settings.toml" in str(call_kwargs["explicit_path"])

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

    def test_install_rejects_templates_dir_flag(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["install", "--templates-dir", "/x"])
        assert result.exit_code != 0
        assert "no such option" in (result.stdout + result.stderr).lower()

    def test_install_help_shows_expected_usage(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["install", "--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.stdout
        assert "--source-root" in result.stdout

    def test_install_fails_loudly_when_no_source_root(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The core regression test for the defect: when the source repo build
        context cannot be located, `csg install` must exit non-zero with a
        clear message — it must NOT report `{"status": "built"}` and silently
        no-op (the pre-fix behavior that produced stale images)."""
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        monkeypatch.setattr(
            "color_scheme_generator.cli.install_cmd.resolve_source_root",
            lambda **_: (_ for _ in ()).throw(
                __import__("oci_runtime").SourceRootNotFoundError(package="color_scheme_generator")
            ),
        )
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--output-format", "json", "install"])
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert '"status": "built"' not in output
        assert "source repo" in output

    def test_install_uses_source_root_override(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        mock_container_engine: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        root = tmp_path / "repo"
        (root / "src" / "cli-tools").mkdir(parents=True)
        (root / "src" / "shared").mkdir(parents=True)
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        monkeypatch.setattr(
            "color_scheme_generator.cli.install_cmd.create_container_engine",
            lambda engine: mock_container_engine,
        )
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, [
            "--output-format", "json", "install",
            "--container-engine", "podman",
            "--source-root", str(root),
        ])
        assert result.exit_code == 0, f"stderr={result.stderr}"
        assert mock_container_engine.build_image.call_count == 4
        for call in mock_container_engine.build_image.call_args_list:
            context = call[0][0]
            assert context.context_path == root

    def test_install_uses_source_root_env_var(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        mock_container_engine: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        root = tmp_path / "repo"
        (root / "src" / "cli-tools").mkdir(parents=True)
        (root / "src" / "shared").mkdir(parents=True)
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        monkeypatch.setattr(
            "color_scheme_generator.cli.install_cmd.create_container_engine",
            lambda engine: mock_container_engine,
        )
        monkeypatch.setenv("CSG_SOURCE_ROOT", str(root))
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, [
            "--output-format", "json", "install", "--container-engine", "podman",
        ])
        assert result.exit_code == 0, f"stderr={result.stderr}"
        assert mock_container_engine.build_image.call_count == 4
        for call in mock_container_engine.build_image.call_args_list:
            context = call[0][0]
            assert context.context_path == root
