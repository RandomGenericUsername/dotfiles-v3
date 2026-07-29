from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from color_scheme_generator.domain.enums import Backend, RuntimeMode
from color_scheme_generator.domain.exceptions import ConfigResolutionError
from color_scheme_generator.domain.models import (
    AppliedOverride,
    AppSettings,
    ConfigResolverResult,
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
    mock = MagicMock()
    mock.resolve.return_value = AppSettings(
        output=OutputSettings(directory=Path("/tmp"), default_formats=(), overwrite=False),
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
    mock.last_result = ConfigResolverResult(
        resolved_path=Path("/home/user/.config/color-scheme-generator/settings.toml"),
        applied_overrides=(
            AppliedOverride(
                field_path="runtime.mode",
                raw_value="local",
                coerced_value="local",
                source="cli",
            ),
        ),
    )
    return mock


@pytest.fixture
def mock_template_resolver() -> MagicMock:
    mock = MagicMock()
    mock.resolve.return_value = Path("/home/user/.config/color-scheme/templates")
    return mock


@pytest.fixture
def mock_backend_catalog() -> MagicMock:
    mock = MagicMock()
    mock.load.return_value = {}
    return mock


@pytest.fixture
def mock_backend_registry() -> dict[Backend, MagicMock]:
    m = MagicMock()
    m.is_available.return_value = True
    return {Backend.CUSTOM: m, Backend.PYWAL: m, Backend.WALLUST: m}


@pytest.fixture
def mock_output() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_deps(
    mock_config_resolver: MagicMock,
    mock_template_resolver: MagicMock,
    mock_backend_catalog: MagicMock,
    mock_backend_registry: dict[Backend, MagicMock],
    mock_output: MagicMock,
) -> CliDependencies:
    return CliDependencies(
        backend_registry=mock_backend_registry,
        backend_catalog_loader=mock_backend_catalog,
        config_resolver=mock_config_resolver,
        output_adapter=mock_output,
        template_dir_resolver=mock_template_resolver,
    )


class TestInfoCommand:
    def test_info_outputs_json(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--output-format", "json", "info"])
        assert result.exit_code == 0, f"stderr={result.stderr}"

        import json
        payload = json.loads(result.stdout)
        assert "config_path" in payload
        assert "config_source" in payload
        assert "runtime_mode" in payload
        assert "container_engine" in payload
        assert "templates_directory" in payload
        assert "backends" in payload

    def test_info_shows_config_path(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        mock_config_resolver: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--output-format", "json", "info"])
        assert result.exit_code == 0

        import json
        payload = json.loads(result.stdout)
        assert "settings.toml" in payload["config_path"]

    def test_info_shows_applied_overrides(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--output-format", "json", "info"])
        assert result.exit_code == 0

        import json
        payload = json.loads(result.stdout)
        assert len(payload["applied_overrides"]) > 0
        assert payload["applied_overrides"][0]["field_path"] == "runtime.mode"

    def test_info_shows_runtime_mode(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--output-format", "json", "info"])
        assert result.exit_code == 0

        import json
        payload = json.loads(result.stdout)
        assert payload["runtime_mode"] == "local"
        assert payload["container_engine"] == "docker"

    def test_info_shows_templates_directory(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--output-format", "json", "info"])
        assert result.exit_code == 0

        import json
        payload = json.loads(result.stdout)
        assert "templates" in payload["templates_directory"]

    def test_info_shows_backend_availability(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--output-format", "json", "info"])
        assert result.exit_code == 0

        import json
        payload = json.loads(result.stdout)
        backends = payload["backends"]
        assert "custom" in backends
        assert "pywal" in backends
        assert "wallust" in backends

    def test_info_handles_config_resolution_error(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        mock_config_resolver: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_config_resolver.resolve.side_effect = ConfigResolutionError(
            key="settings.toml", reason="not found"
        )
        mock_config_resolver.last_result = None
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--output-format", "json", "info"])
        assert result.exit_code == 0

        import json
        payload = json.loads(result.stdout)
        assert "not resolved" in payload["config_path"]

    def test_info_supports_rich_output(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--output-format", "rich", "info"])
        assert result.exit_code == 0

    def test_info_supports_plain_output(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--output-format", "plain", "info"])
        assert result.exit_code == 0
        assert "Config path:" in result.stdout
