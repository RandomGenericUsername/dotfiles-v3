from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.models import (
    BackendDefinition,
    BackendParameterDefinition,
)
from color_scheme_generator.factory import CliDependencies


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_backend_registry() -> dict[Backend, MagicMock]:
    available = MagicMock()
    available.is_available.return_value = True
    unavailable = MagicMock()
    unavailable.is_available.return_value = False
    return {
        Backend.CUSTOM: available,
        Backend.PYWAL: unavailable,
        Backend.WALLUST: unavailable,
    }


@pytest.fixture
def mock_backend_catalog() -> MagicMock:
    mock = MagicMock()
    mock.load.return_value = {
        Backend.CUSTOM: BackendDefinition(
            backend=Backend.CUSTOM,
            display_name="Custom",
            description="PIL + KMeans extraction",
            parameters=(
                BackendParameterDefinition(
                    name="saturation",
                    type_="float",
                    description="Saturation factor",
                    required=False,
                    choices=None,
                    default=1.0,
                ),
                BackendParameterDefinition(
                    name="n_clusters",
                    type_="int",
                    description="Number of clusters",
                    required=False,
                    choices=None,
                    default=16,
                ),
            ),
            min_version="0.0.0",
        ),
    }
    return mock


@pytest.fixture
def mock_output() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_deps(
    mock_backend_registry: dict[Backend, MagicMock],
    mock_backend_catalog: MagicMock,
    mock_output: MagicMock,
) -> CliDependencies:
    return CliDependencies(
        backend_registry=mock_backend_registry,
        backend_catalog_loader=mock_backend_catalog,
        output_adapter=mock_output,
    )


class TestListBackendsCommand:
    def test_list_backends_shows_all_three_backends(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--output-format", "json", "list-backends"])
        assert result.exit_code == 0

        import json
        payload = json.loads(result.stdout)
        assert "backends" in payload
        assert len(payload["backends"]) == 3

    def test_list_backends_shows_availability(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--output-format", "json", "list-backends"])
        assert result.exit_code == 0

        import json
        payload = json.loads(result.stdout)
        backends = {b["name"]: b for b in payload["backends"]}
        assert backends["custom"]["available"] is True
        assert backends["pywal"]["available"] is False

    def test_list_backends_shows_parameters(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--output-format", "json", "list-backends"])
        assert result.exit_code == 0

        import json
        payload = json.loads(result.stdout)
        custom = [b for b in payload["backends"] if b["name"] == "custom"][0]
        assert len(custom["parameters"]) > 0
        param_names = [p["name"] for p in custom["parameters"]]
        assert "saturation" in param_names
        assert "n_clusters" in param_names

    def test_list_backends_supports_rich_output(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--output-format", "rich", "list-backends"])
        assert result.exit_code == 0

    def test_list_backends_supports_plain_output(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--output-format", "plain", "list-backends"])
        assert result.exit_code == 0

    def test_list_backends_handles_missing_catalog(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        deps = CliDependencies(
            backend_registry={
                Backend.CUSTOM: MagicMock(is_available=MagicMock(return_value=True)),
                Backend.PYWAL: MagicMock(is_available=MagicMock(return_value=False)),
                Backend.WALLUST: MagicMock(is_available=MagicMock(return_value=False)),
            },
        )
        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: deps)
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["--output-format", "json", "list-backends"])
        assert result.exit_code == 0

    def test_list_backends_help_shows_expected_usage(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["list-backends", "--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.stdout
