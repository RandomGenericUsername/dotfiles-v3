from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import (
    ContainerImageNotFoundError,
    ContainerRuntimeUnavailableError,
    ContainerTimeoutError,
    ImagePullAccessError,
)
from color_scheme_generator.factory import (
    CliDependencies,
    create_container_processor,
    create_dry_run_processor,
    create_local_processor,
)
from color_scheme_generator.ports.processor import ColorSchemeProcessorPort


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_deps() -> CliDependencies:
    return CliDependencies(
        backend_registry={Backend.CUSTOM: MagicMock()},
        backend_catalog_loader=MagicMock(),
        config_resolver=MagicMock(),
        output_adapter=MagicMock(),
        template_dir_resolver=MagicMock(),
        template_renderer=MagicMock(),
    )


def test_cli_dependencies_accepts_container_engine() -> None:
    deps = CliDependencies(
        backend_registry={},
        container_engine=MagicMock(),
    )
    assert deps.container_engine is not None


def test_cli_dependencies_accepts_color_scheme_processor_port() -> None:
    deps = CliDependencies(
        backend_registry={},
        processor=MagicMock(spec=ColorSchemeProcessorPort),
    )
    assert deps.processor is not None
    assert isinstance(deps.processor, MagicMock)


def test_cli_dependencies_processor_defaults_to_none() -> None:
    deps = CliDependencies(backend_registry={})
    assert deps.processor is None


def test_cli_dependencies_container_engine_defaults_to_none() -> None:
    deps = CliDependencies(backend_registry={})
    assert deps.container_engine is None


class TestRuntimeFlags:
    def test_runtime_local_flag_accepted(
        self, runner: CliRunner, mock_deps: CliDependencies, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "color_scheme_generator.cli.main.build_deps", lambda: mock_deps
        )
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--runtime", "local", "version"])
        assert result.exit_code == 0, f"stderr={result.stderr}"

    def test_runtime_container_flag_accepted(
        self, runner: CliRunner, mock_deps: CliDependencies, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "color_scheme_generator.cli.main.build_deps", lambda: mock_deps
        )
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--runtime", "container", "version"])
        assert result.exit_code == 0, f"stderr={result.stderr}"

    def test_container_engine_docker_flag_accepted(
        self, runner: CliRunner, mock_deps: CliDependencies, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "color_scheme_generator.cli.main.build_deps", lambda: mock_deps
        )
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--container-engine", "docker", "version"])
        assert result.exit_code == 0, f"stderr={result.stderr}"

    def test_container_engine_podman_flag_accepted(
        self, runner: CliRunner, mock_deps: CliDependencies, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "color_scheme_generator.cli.main.build_deps", lambda: mock_deps
        )
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--container-engine", "podman", "version"])
        assert result.exit_code == 0, f"stderr={result.stderr}"

    def test_runtime_and_container_engine_flags_together(
        self, runner: CliRunner, mock_deps: CliDependencies, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "color_scheme_generator.cli.main.build_deps", lambda: mock_deps
        )
        from color_scheme_generator.cli.main import app

        result = runner.invoke(
            app, ["--runtime", "container", "--container-engine", "podman", "version"]
        )
        assert result.exit_code == 0, f"stderr={result.stderr}"

    def test_runtime_defaults_to_local(
        self, runner: CliRunner, mock_deps: CliDependencies, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "color_scheme_generator.cli.main.build_deps", lambda: mock_deps
        )
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0, f"stderr={result.stderr}"


class TestFactoryHelpers:
    def test_create_local_processor_returns_port(self) -> None:
        registry = {Backend.CUSTOM: MagicMock()}
        processor = create_local_processor(registry)
        assert isinstance(processor, ColorSchemeProcessorPort)

    def test_create_container_processor_returns_port(self) -> None:
        mock_runtime = MagicMock()
        processor = create_container_processor(mock_runtime)
        assert isinstance(processor, ColorSchemeProcessorPort)

    def test_create_dry_run_processor_returns_port(self) -> None:
        processor = create_dry_run_processor()
        assert isinstance(processor, ColorSchemeProcessorPort)


class TestContainerExceptions:
    def test_container_image_not_found_error(self) -> None:
        exc = ContainerImageNotFoundError("test-image:latest", Backend.CUSTOM)
        assert exc.image == "test-image:latest"
        assert exc.backend is Backend.CUSTOM
        assert "test-image:latest" in str(exc)

    def test_container_runtime_unavailable_error(self) -> None:
        exc = ContainerRuntimeUnavailableError("docker")
        assert exc.runtime == "docker"
        assert "docker" in str(exc)

    def test_image_pull_access_error(self) -> None:
        exc = ImagePullAccessError("my-image:latest", "ghcr.io")
        assert exc.image == "my-image:latest"
        assert exc.registry == "ghcr.io"

    def test_container_timeout_error(self) -> None:
        exc = ContainerTimeoutError()
        assert isinstance(exc, Exception)
