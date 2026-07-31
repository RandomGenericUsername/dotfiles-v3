from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from color_scheme_generator.domain.enums import Backend, ColorFormat, RuntimeMode
from color_scheme_generator.domain.models import (
    AppSettings,
    ContainerSettings,
    GenerationSettings,
    OutputSettings,
    RuntimeSettings,
)
from color_scheme_generator.factory import CliDependencies
from tests.conftest import FakeProcessor


def _default_app_settings(**overrides: object) -> AppSettings:
    return AppSettings(
        output=OutputSettings(
            directory=overrides.get("output_directory", Path("/tmp/color-scheme")),
            default_formats=overrides.get("default_formats", ()),  # type: ignore[arg-type]
            overwrite=False,
        ),
        generation=GenerationSettings(
            backend=overrides.get("backend", Backend.CUSTOM),
            default_params={},
        ),
        runtime=RuntimeSettings(
            mode=RuntimeMode(overrides.get("runtime_mode", "local")),
        ),
        container=ContainerSettings(
            engine=overrides.get("container_engine", "docker"),  # type: ignore[arg-type]
            image_prefix="csg",
            image_tag="latest",
            timeout_seconds=60,
            memory_limit="512m",
            mount_timeout_seconds=30,
        ),
    )


def _deps_with_settings(fake_processor: FakeProcessor, settings: AppSettings) -> CliDependencies:
    resolver = MagicMock()
    resolver.resolve.return_value = settings
    return CliDependencies(
        backend_registry={},
        backend_catalog_loader=MagicMock(),
        config_resolver=resolver,
        processor=fake_processor,
    )


def _invoke(
    runner: CliRunner,
    deps: CliDependencies,
    args: list[str],
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: deps)
    from color_scheme_generator.cli.main import app

    return runner.invoke(app, args)


def _recorded_config(fake_processor: FakeProcessor):
    assert fake_processor.calls, "processor was not called"
    request = fake_processor.calls[0]["request"]
    return request.config


class TestGenerateBackendFlag:
    def test_backend_flag_overrides_default(
        self, runner, cli_deps_with_processor, fake_processor, monkeypatch
    ) -> None:
        result = _invoke(
            runner,
            cli_deps_with_processor,
            ["generate", "--backend", "pywal", "/tmp/test.jpg"],
            monkeypatch,
        )
        assert result.exit_code == 0, f"stderr={result.stderr}"
        assert _recorded_config(fake_processor).backend is Backend.PYWAL

    def test_backend_invalid_rejected(self, runner, cli_deps_with_processor, monkeypatch) -> None:
        result = _invoke(
            runner,
            cli_deps_with_processor,
            ["generate", "--backend", "invalid", "/tmp/test.jpg"],
            monkeypatch,
        )
        assert result.exit_code == 2

    def test_backend_omitted_uses_settings_default(
        self, runner, fake_processor, monkeypatch
    ) -> None:
        deps = _deps_with_settings(fake_processor, _default_app_settings(backend=Backend.PYWAL))
        result = _invoke(runner, deps, ["generate", "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 0, f"stderr={result.stderr}"
        assert _recorded_config(fake_processor).backend is Backend.PYWAL


class TestGenerateParamFlag:
    def test_param_key_value_overrides(
        self, runner, cli_deps_with_processor, fake_processor, monkeypatch
    ) -> None:
        result = _invoke(
            runner,
            cli_deps_with_processor,
            [
                "generate",
                "--backend",
                "pywal",
                "--param",
                "saturation=1.5",
                "--param",
                "algorithm=wal",
                "/tmp/test.jpg",
            ],
            monkeypatch,
        )
        assert result.exit_code == 0, f"stderr={result.stderr}"
        params = _recorded_config(fake_processor).params
        assert params.get("saturation") == "1.5"
        assert params.get("algorithm") == "wal"

    def test_param_bogus_raises_config_error(
        self, runner, cli_deps_with_processor, fake_processor, monkeypatch
    ) -> None:
        result = _invoke(
            runner,
            cli_deps_with_processor,
            ["generate", "--backend", "custom", "--param", "bogus=1", "/tmp/test.jpg"],
            monkeypatch,
        )
        assert result.exit_code == 1
        error_payload = json.loads(result.stderr)
        assert error_payload["error"]["type"] == "ConfigResolutionError"

    def test_param_no_equals_dropped(
        self, runner, cli_deps_with_processor, fake_processor, monkeypatch
    ) -> None:
        result = _invoke(
            runner,
            cli_deps_with_processor,
            ["generate", "--param", "badformat", "/tmp/test.jpg"],
            monkeypatch,
        )
        assert result.exit_code == 0, f"stderr={result.stderr}"
        assert _recorded_config(fake_processor).params == {}


class TestGenerateFormatFlag:
    def test_format_flag_only_renders_those(
        self, runner, cli_deps_with_processor, fake_processor, monkeypatch
    ) -> None:
        result = _invoke(
            runner,
            cli_deps_with_processor,
            ["generate", "-f", "json", "-f", "css", "/tmp/test.jpg"],
            monkeypatch,
        )
        assert result.exit_code == 0, f"stderr={result.stderr}"
        formats = _recorded_config(fake_processor).formats
        assert ColorFormat.JSON in formats
        assert ColorFormat.CSS in formats

    def test_format_omitted_uses_settings_default(
        self, runner, fake_processor, monkeypatch
    ) -> None:
        deps = _deps_with_settings(
            fake_processor,
            _default_app_settings(default_formats=(ColorFormat.JSON, ColorFormat.SH)),
        )
        result = _invoke(runner, deps, ["generate", "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 0, f"stderr={result.stderr}"
        formats = _recorded_config(fake_processor).formats
        assert ColorFormat.JSON in formats
        assert ColorFormat.SH in formats

    def test_format_invalid_rejected(self, runner, cli_deps_with_processor, monkeypatch) -> None:
        result = _invoke(
            runner,
            cli_deps_with_processor,
            ["generate", "-f", "invalid_format", "/tmp/test.jpg"],
            monkeypatch,
        )
        assert result.exit_code == 2


class TestGenerateOutputDirFlag:
    def test_output_dir_flag_writes_there(
        self, runner, cli_deps_with_processor, fake_processor, monkeypatch
    ) -> None:
        result = _invoke(
            runner,
            cli_deps_with_processor,
            ["generate", "-o", "/custom/output", "/tmp/test.jpg"],
            monkeypatch,
        )
        assert result.exit_code == 0, f"stderr={result.stderr}"
        assert _recorded_config(fake_processor).output_dir == Path("/custom/output")

    def test_output_dir_omitted_uses_settings(self, runner, fake_processor, monkeypatch) -> None:
        deps = _deps_with_settings(
            fake_processor,
            _default_app_settings(output_directory=Path("/custom/output")),
        )
        result = _invoke(runner, deps, ["generate", "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 0, f"stderr={result.stderr}"
        assert _recorded_config(fake_processor).output_dir == Path("/custom/output")


class TestGenerateLazyProcessor:
    def test_injected_processor_skips_construction(
        self,
        runner,
        cli_deps_with_processor,
        fake_processor,
        monkeypatch,
    ) -> None:
        create_local = MagicMock()
        create_container = MagicMock()
        monkeypatch.setattr(
            "color_scheme_generator.cli.main.create_local_processor",
            create_local,
        )
        monkeypatch.setattr(
            "color_scheme_generator.cli.main.create_container_processor",
            create_container,
        )
        result = _invoke(
            runner,
            cli_deps_with_processor,
            ["generate", "--runtime", "container", "/tmp/test.jpg"],
            monkeypatch,
        )
        assert result.exit_code == 0, f"stderr={result.stderr}"
        assert len(fake_processor.calls) == 1
        create_local.assert_not_called()
        create_container.assert_not_called()

    def test_runtime_flag_resolves_effective_mode(
        self, runner, fake_processor, monkeypatch
    ) -> None:
        deps = _deps_with_settings(fake_processor, _default_app_settings())
        result = _invoke(
            runner,
            deps,
            ["generate", "--runtime", "container", "--container-engine", "podman", "/tmp/test.jpg"],
            monkeypatch,
        )
        assert result.exit_code == 0, f"stderr={result.stderr}"
        cli_overrides = deps.config_resolver.resolve.call_args[1]["cli_overrides"]
        assert cli_overrides["runtime.mode"] == "container"
        assert cli_overrides["container.engine"] == "podman"

    def test_container_runtime_unavailable_exits_1(
        self, runner, fake_processor, monkeypatch
    ) -> None:
        from color_scheme_generator.domain.exceptions import (
            ContainerRuntimeUnavailableError,
        )

        deps = _deps_with_settings(
            fake_processor,
            _default_app_settings(runtime_mode="container"),
        )
        deps.processor = None
        monkeypatch.setattr(
            "color_scheme_generator.cli.main.create_container_engine",
            MagicMock(side_effect=ContainerRuntimeUnavailableError(runtime="docker")),
        )
        result = _invoke(
            runner,
            deps,
            ["generate", "/tmp/test.jpg"],
            monkeypatch,
        )
        assert result.exit_code == 1
        error_payload = json.loads(result.stderr)
        assert error_payload["error"]["type"] == "ContainerRuntimeUnavailableError"


class TestGenerateConfigResolution:
    def test_resolver_failure_falls_back_to_defaults(
        self, runner, fake_processor, monkeypatch
    ) -> None:
        from color_scheme_generator.domain.exceptions import ColorSchemeError

        deps = _deps_with_settings(fake_processor, _default_app_settings())
        deps.config_resolver.resolve.side_effect = ColorSchemeError("config not found")
        result = _invoke(runner, deps, ["generate", "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 0, f"stderr={result.stderr}"
        assert len(fake_processor.calls) == 1

    def test_no_backend_catalog_loader_raises_on_params(
        self, runner, fake_processor, monkeypatch
    ) -> None:
        deps = _deps_with_settings(fake_processor, _default_app_settings())
        deps.backend_catalog_loader = None
        result = _invoke(
            runner,
            deps,
            ["generate", "--param", "saturation=1.0", "/tmp/test.jpg"],
            monkeypatch,
        )
        assert result.exit_code == 1
        error_payload = json.loads(result.stderr)
        assert error_payload["error"]["type"] == "ConfigResolutionError"


class TestCliErrorPaths:
    def test_generate_no_args_exits_2(self, runner, cli_deps_with_processor, monkeypatch) -> None:
        result = _invoke(runner, cli_deps_with_processor, ["generate"], monkeypatch)
        assert result.exit_code == 2

    def test_unknown_command_exits_2(self, runner, cli_deps_with_processor, monkeypatch) -> None:
        result = _invoke(runner, cli_deps_with_processor, ["unknown-command"], monkeypatch)
        assert result.exit_code == 2

    def test_nonexistent_templates_dir_exits_2(
        self, runner, cli_deps_with_processor, monkeypatch
    ) -> None:
        result = _invoke(
            runner,
            cli_deps_with_processor,
            ["generate", "--templates-dir", "/nonexistent-dir", "/tmp/test.jpg"],
            monkeypatch,
        )
        assert result.exit_code == 2


class TestShowFlags:
    def test_show_accepts_backend_and_param(
        self, runner, cli_deps_with_processor, fake_processor, monkeypatch
    ) -> None:
        result = _invoke(
            runner,
            cli_deps_with_processor,
            ["show", "--backend", "pywal", "--param", "saturation=1.5", "/tmp/test.jpg"],
            monkeypatch,
        )
        assert result.exit_code == 0, f"stderr={result.stderr}"
        assert len(fake_processor.calls) == 1
        assert fake_processor.calls[0]["command"] == "process_show"

    def test_show_rejects_format_flag(self, runner, cli_deps_with_processor, monkeypatch) -> None:
        result = _invoke(
            runner,
            cli_deps_with_processor,
            ["show", "-f", "json", "/tmp/test.jpg"],
            monkeypatch,
        )
        assert result.exit_code == 2

    def test_show_rejects_output_dir_flag(
        self, runner, cli_deps_with_processor, monkeypatch
    ) -> None:
        result = _invoke(
            runner,
            cli_deps_with_processor,
            ["show", "-o", "/tmp", "/tmp/test.jpg"],
            monkeypatch,
        )
        assert result.exit_code == 2

    def test_show_processor_error_exits_1(
        self, runner, cli_deps_with_processor, fake_processor, monkeypatch
    ) -> None:
        from color_scheme_generator.domain.exceptions import BackendNotAvailableError

        fake_processor.error = BackendNotAvailableError(
            backend=Backend.CUSTOM,
            hint="Try `csg install`",
        )
        result = _invoke(
            runner,
            cli_deps_with_processor,
            ["show", "/tmp/test.jpg"],
            monkeypatch,
        )
        assert result.exit_code == 1
        error_payload = json.loads(result.stderr)
        assert error_payload["error"]["type"] == "BackendNotAvailableError"
