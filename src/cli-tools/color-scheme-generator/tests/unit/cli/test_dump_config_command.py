from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from color_scheme_generator.domain.enums import Backend, ContainerEngine, RuntimeMode
from color_scheme_generator.domain.exceptions import ConfigResolutionError
from color_scheme_generator.domain.models import (
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
        output=OutputSettings(directory=Path("/tmp/out"), default_formats=(), overwrite=True),
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
    mock.last_result = ConfigResolverResult(
        resolved_path=Path("/tmp/settings.toml"),
        applied_overrides=(),
    )
    return mock


@pytest.fixture
def mock_output() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_deps(
    mock_config_resolver: MagicMock,
    mock_output: MagicMock,
) -> CliDependencies:
    return CliDependencies(
        backend_registry={},
        config_resolver=mock_config_resolver,
        output_adapter=mock_output,
    )


class TestDumpConfigCommand:
    def test_dump_config_outputs_toml_to_stdout(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["dump-config"])
        assert result.exit_code == 0

        assert "[output]" in result.stdout
        assert "[runtime]" in result.stdout
        assert "[container]" in result.stdout

    def test_dump_config_output_is_valid_toml(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["dump-config"])
        assert result.exit_code == 0

        lines = result.stdout.strip().split("\n")
        assert any(line.startswith("[") for line in lines)

    def test_dump_config_writes_to_file(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        output_file = tmp_path / "config.toml"
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(
            app,
            ["dump-config", "--output", str(output_file)],
        )
        assert result.exit_code == 0
        assert output_file.exists()
        content = output_file.read_text()
        assert "[output]" in content

    def test_dump_config_overwrites_existing_file(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        output_file = tmp_path / "config.toml"
        output_file.write_text("old content")

        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(
            app,
            ["dump-config", "--output", str(output_file)],
        )
        assert result.exit_code == 0
        content = output_file.read_text()
        assert "[output]" in content

    def test_dump_config_handles_config_resolution_failure(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        mock_config_resolver: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_config_resolver.resolve.side_effect = ConfigResolutionError(
            key="settings.toml", reason="not found"
        )
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["dump-config"])
        assert result.exit_code == 1

    def test_dump_config_help_shows_expected_usage(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["dump-config", "--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.stdout
