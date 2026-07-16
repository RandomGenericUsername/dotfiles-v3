from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestCliVersion:
    def test_version_outputs_json(self, runner: CliRunner) -> None:
        from color_scheme_generator.cli.main import app

        with patch("color_scheme_generator.cli.version_cmd._pkg_version", return_value="0.1.0"):
            result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["version"] == "0.1.0"

    def test_version_matches_metadata(self, runner: CliRunner) -> None:
        from color_scheme_generator.cli.main import app

        with patch("color_scheme_generator.cli.version_cmd._pkg_version", return_value="0.1.0"):
            result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["version"] == "0.1.0"

    def test_help_output_shows_expected_usage(self, runner: CliRunner) -> None:
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["version", "--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.stdout
