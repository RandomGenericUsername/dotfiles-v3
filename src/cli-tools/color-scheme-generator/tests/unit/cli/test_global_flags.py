from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from color_scheme_generator.domain.enums import Verbosity
from color_scheme_generator.domain.models import AppSettings
from color_scheme_generator.factory import CliDependencies
from tests.conftest import FakeProcessor


def _invoke(
    runner: CliRunner,
    deps: CliDependencies,
    args: list[str],
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: deps)
    from color_scheme_generator.cli.main import app

    return runner.invoke(app, args)


class TestOutputFormatFlag:
    def test_json_output_parses(self, runner, cli_deps_with_processor, monkeypatch) -> None:
        result = _invoke(
            runner,
            cli_deps_with_processor,
            ["--output-format", "json", "generate", "/tmp/test.png", "-o", "/tmp/out"],
            monkeypatch,
        )
        assert result.exit_code == 0, f"stderr={result.stderr}"
        assert json.loads(result.stdout)["success"] is True

    def test_rich_output_renders_table(self, runner, cli_deps_with_processor, monkeypatch) -> None:
        result = _invoke(
            runner,
            cli_deps_with_processor,
            ["--output-format", "rich", "generate", "/tmp/test.png", "-o", "/tmp/out"],
            monkeypatch,
        )
        assert result.exit_code == 0, f"stderr={result.stderr}"
        assert "Success" in result.stdout
        assert "Backend" in result.stdout

    def test_plain_output_has_no_ansi(self, runner, cli_deps_with_processor, monkeypatch) -> None:
        result = _invoke(
            runner,
            cli_deps_with_processor,
            ["--output-format", "plain", "generate", "/tmp/test.png", "-o", "/tmp/out"],
            monkeypatch,
        )
        assert result.exit_code == 0, f"stderr={result.stderr}"
        assert "\x1b[" not in result.stdout
        assert "Backend: custom" in result.stdout


class TestQuietFlag:
    def test_quiet_suppresses_result_output(
        self, runner, cli_deps_with_processor, monkeypatch
    ) -> None:
        result = _invoke(
            runner,
            cli_deps_with_processor,
            ["--quiet", "generate", "/tmp/test.png", "-o", "/tmp/out"],
            monkeypatch,
        )
        assert result.exit_code == 0, f"stderr={result.stderr}"
        assert result.stdout == ""


class TestVerboseFlag:
    def _deps_with_resolver(self, fake_processor: FakeProcessor) -> CliDependencies:
        from pathlib import Path

        from color_scheme_generator.domain.enums import Backend
        from color_scheme_generator.domain.models import (
            ContainerSettings,
            GenerationSettings,
            OutputSettings,
            RuntimeSettings,
        )

        resolver = MagicMock()
        resolver.resolve.return_value = AppSettings(
            output=OutputSettings(directory=Path("/tmp/out"), default_formats=(), overwrite=False),
            generation=GenerationSettings(backend=Backend.CUSTOM, default_params={}),
            runtime=RuntimeSettings(mode="local"),
            container=ContainerSettings(
                engine="docker",
                image_prefix="csg",
                image_tag="latest",
                timeout_seconds=60,
                memory_limit="512m",
                mount_timeout_seconds=30,
            ),
        )
        return CliDependencies(
            backend_registry={},
            backend_catalog_loader=MagicMock(),
            config_resolver=resolver,
            processor=fake_processor,
        ), resolver

    def test_verbose_propagates_to_settings(self, runner, fake_processor, monkeypatch) -> None:
        deps, resolver = self._deps_with_resolver(fake_processor)
        result = _invoke(
            runner, deps, ["-v", "generate", "/tmp/test.png", "-o", "/tmp/out"], monkeypatch
        )
        assert result.exit_code == 0, f"stderr={result.stderr}"
        cli_overrides = resolver.resolve.call_args[1]["cli_overrides"]
        assert cli_overrides["output.verbosity"] == str(Verbosity.VERBOSE.value)

    def test_debug_verbose_propagates_to_settings(
        self, runner, fake_processor, monkeypatch
    ) -> None:
        deps, resolver = self._deps_with_resolver(fake_processor)
        result = _invoke(
            runner, deps, ["-vv", "generate", "/tmp/test.png", "-o", "/tmp/out"], monkeypatch
        )
        assert result.exit_code == 0, f"stderr={result.stderr}"
        cli_overrides = resolver.resolve.call_args[1]["cli_overrides"]
        assert cli_overrides["output.verbosity"] == str(Verbosity.DEBUG.value)
