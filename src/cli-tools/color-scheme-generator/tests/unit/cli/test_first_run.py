from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.factory import CliDependencies


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestShellCompletion:
    def test_install_completion_option_present_in_help(self, runner: CliRunner) -> None:
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--install-completion" in result.stdout

    def test_show_completion_option_present_in_help(self, runner: CliRunner) -> None:
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--show-completion" in result.stdout


class TestFirstRunDefaults:
    def test_default_settings_toml_exists(self) -> None:
        from importlib.resources import files as resource_files
        from pathlib import Path

        path = Path(resource_files("color_scheme_generator") / "defaults" / "settings.toml")
        assert path.exists(), f"Bundled defaults/settings.toml not found at {path}"

    def test_default_settings_toml_has_valid_backend(self) -> None:
        import tomllib
        from importlib.resources import files as resource_files
        from pathlib import Path

        path = Path(resource_files("color_scheme_generator") / "defaults" / "settings.toml")
        with open(path, "rb") as f:
            data = tomllib.load(f)
        backend = data["generation"]["backend"]
        assert backend in ("custom", "pywal", "wallust"), f"Invalid backend: {backend}"

    def test_default_file_strategy_points_to_bundled_path(self) -> None:
        from color_scheme_generator.adapters.settings.config_resolver import (
            AssembledConfigResolver,
        )

        resolver = AssembledConfigResolver()
        strategy = resolver._assembler._path_resolver._strategies[-1]
        assert str(strategy._path).endswith(
            "defaults/settings.toml"
        ), f"DefaultFileStrategy points to {strategy._path}"


class TestFirstRunFallback:
    @pytest.fixture
    def mock_deps(self) -> CliDependencies:
        mock_processor = MagicMock()
        mock_output = MagicMock()
        mock_config_resolver = MagicMock()
        from pathlib import Path

        from color_scheme_generator.domain.models import (
            AppSettings,
            ContainerSettings,
            GenerationSettings,
            OutputSettings,
            RuntimeSettings,
        )

        mock_config_resolver.resolve.return_value = AppSettings(
            output=OutputSettings(
                directory=Path("/tmp/color-scheme"),
                default_formats=(),
                overwrite=False,
            ),
            generation=GenerationSettings(
                backend=Backend.CUSTOM,
                default_params={},
            ),
            runtime=RuntimeSettings(
                mode="local",
            ),
            container=ContainerSettings(
                image_prefix="csg",
                image_tag="latest",
                timeout_seconds=60,
                memory_limit="512m",
                mount_timeout_seconds=30,
            ),
        )
        return CliDependencies(
            backend_registry=MagicMock(),
            config_resolver=mock_config_resolver,
            output_adapter=mock_output,
            processor=mock_processor,
        )

    def test_generate_succeeds_with_default_settings(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["generate", "/tmp/test.jpg"])
        assert result.exit_code == 0, f"Unexpected exit: {result.stdout}"

    def test_config_resolver_uses_default_file_strategy_on_fresh_install(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from color_scheme_generator.adapters.settings.config_resolver import (
            AssembledConfigResolver,
        )

        resolver = AssembledConfigResolver()
        strategy = resolver._assembler._path_resolver._strategies[-1]
        assert strategy._path.exists(), "DefaultFileStrategy path does not exist"


class TestNoBackendsHint:
    @pytest.fixture
    def all_unavailable_registry(self) -> dict[Backend, MagicMock]:
        unavailable = MagicMock()
        unavailable.is_available.return_value = False
        return {
            Backend.CUSTOM: unavailable,
            Backend.PYWAL: unavailable,
            Backend.WALLUST: unavailable,
        }

    @pytest.fixture
    def deps_with_hint(
        self, all_unavailable_registry: dict[Backend, MagicMock]
    ) -> CliDependencies:
        return CliDependencies(
            backend_registry=all_unavailable_registry,
            backend_catalog_loader=MagicMock(),
            output_adapter=MagicMock(),
        )

    def test_list_backends_shows_hint_in_json_when_all_unavailable(
        self,
        runner: CliRunner,
        deps_with_hint: CliDependencies,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: deps_with_hint)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--output-format", "json", "list-backends"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert "hint" in payload
        assert "csg install" in payload["hint"]

    def test_list_backends_shows_hint_in_rich_when_all_unavailable(
        self,
        runner: CliRunner,
        deps_with_hint: CliDependencies,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: deps_with_hint)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--output-format", "rich", "list-backends"])
        assert result.exit_code == 0
        assert "No backends" in result.stdout

    def test_list_backends_shows_hint_in_plain_when_all_unavailable(
        self,
        runner: CliRunner,
        deps_with_hint: CliDependencies,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: deps_with_hint)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--output-format", "plain", "list-backends"])
        assert result.exit_code == 0
        assert "No backends" in result.stdout

    def test_no_hint_when_some_backends_available(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        available = MagicMock()
        available.is_available.return_value = True
        unavailable = MagicMock()
        unavailable.is_available.return_value = False
        deps = CliDependencies(
            backend_registry={
                Backend.CUSTOM: available,
                Backend.PYWAL: unavailable,
                Backend.WALLUST: unavailable,
            },
            backend_catalog_loader=MagicMock(),
            output_adapter=MagicMock(),
        )
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: deps)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--output-format", "json", "list-backends"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert "hint" not in payload
