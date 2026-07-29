from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from color_scheme_generator.domain.enums import Backend, ColorFormat
from color_scheme_generator.domain.exceptions import (
    BackendNotAvailableError,
    ColorSchemeError,
    ConfigResolutionError,
)
from color_scheme_generator.domain.models import (
    AppSettings,
    BackendDefinition,
    BackendParameterDefinition,
    ContainerSettings,
    GenerationResult,
    GenerationSettings,
    OutputSettings,
    RuntimeSettings,
    TemplateSettings,
)
from color_scheme_generator.factory import CliDependencies


def _default_app_settings(**overrides: object) -> AppSettings:
    return AppSettings(
        output=OutputSettings(
            directory=Path("/tmp/color-scheme"),
            default_formats=(),
            overwrite=False,
        ),
        generation=GenerationSettings(
            backend=Backend.CUSTOM,
            default_params={},
        ),
        template=TemplateSettings(
            templates_dir=None,
            custom_templates_dir=None,
        ),
        runtime=RuntimeSettings(
            mode=overrides.get("runtime_mode", "local"),  # type: ignore[arg-type]
        ),
        container=ContainerSettings(
            image_prefix="csg",
            image_tag="latest",
            timeout_seconds=60,
            memory_limit="512m",
            mount_timeout_seconds=30,
        ),
    )


def _backend_catalog(backend: Backend, params: tuple | None = None) -> dict:
    return {
        backend: BackendDefinition(
            backend=backend,
            display_name=backend.value.title(),
            description="",
            parameters=params or (),
            min_version="0.0.0",
        )
    }


def _param_def(
    name: str, required: bool = False, default: object = None
) -> BackendParameterDefinition:
    return BackendParameterDefinition(
        name=name,
        type_="string",
        description="",
        required=required,
        choices=None,
        default=default,
    )


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_processor() -> MagicMock:
    mock = MagicMock()
    mock.process_generate.return_value = GenerationResult(
        success=True,
        color_scheme=None,
        output_files=(),
        backend=Backend.CUSTOM,
        stderr="",
        return_code=0,
        duration=0.5,
    )
    return mock


@pytest.fixture
def mock_output() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_config_resolver() -> MagicMock:
    mock = MagicMock()
    mock.resolve.return_value = _default_app_settings()
    return mock


@pytest.fixture
def mock_backend_catalog_loader() -> MagicMock:
    mock = MagicMock()
    mock.load.return_value = {
        Backend.CUSTOM: BackendDefinition(
            backend=Backend.CUSTOM,
            display_name="Custom",
            description="",
            parameters=(),
            min_version="0.0.0",
        ),
        Backend.PYWAL: BackendDefinition(
            backend=Backend.PYWAL,
            display_name="Pywal",
            description="",
            parameters=(
                _param_def("saturation", default=1.0),
                _param_def("algorithm", default="wal"),
            ),
            min_version="0.0.0",
        ),
    }
    return mock


@pytest.fixture
def mock_deps(
    mock_processor, mock_output, mock_config_resolver, mock_backend_catalog_loader
) -> CliDependencies:
    return CliDependencies(
        backend_registry=MagicMock(),
        backend_catalog_loader=mock_backend_catalog_loader,
        config_resolver=mock_config_resolver,
        output_adapter=mock_output,
        processor=mock_processor,
    )


def _invoke(runner, deps, output_mock, args, monkeypatch):
    monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: deps)
    monkeypatch.setattr(
        "color_scheme_generator.cli.main.create_output_adapter",
        lambda _fmt, **kwargs: output_mock,
    )
    from color_scheme_generator.cli.main import app
    return runner.invoke(app, args)


class TestGenerateBackendFlag:
    def test_backend_flag_overrides_default(
        self, runner, mock_deps, mock_processor, mock_output, mock_config_resolver,
        monkeypatch,
    ) -> None:
        result = _invoke(runner, mock_deps, mock_output,
                         ["generate", "--backend", "pywal", "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 0
        call_args = mock_processor.process_generate.call_args
        config = call_args[0][0].config
        assert config.backend == Backend.PYWAL

    def test_backend_invalid_raises_error(
        self, runner, mock_deps, mock_processor, mock_output,
        monkeypatch,
    ) -> None:
        result = _invoke(runner, mock_deps, mock_output,
                         ["generate", "--backend", "invalid", "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 2

    def test_backend_omitted_uses_settings_default(
        self, runner, mock_deps, mock_processor, mock_output, mock_config_resolver,
        monkeypatch,
    ) -> None:
        from color_scheme_generator.domain.enums import Backend
        mock_config_resolver.resolve.return_value = AppSettings(
            output=OutputSettings(
                directory=Path("/tmp/color-scheme"),
                default_formats=(),
                overwrite=False,
            ),
            generation=GenerationSettings(backend=Backend.PYWAL, default_params={}),
            template=TemplateSettings(
                templates_dir=None,
                custom_templates_dir=None,
            ),
            runtime=RuntimeSettings(
                mode="local",  # type: ignore[arg-type]
            ),
            container=ContainerSettings(
                image_prefix="csg",
                image_tag="latest",
                timeout_seconds=60,
                memory_limit="512m",
                mount_timeout_seconds=30,
            ),
        )
        result = _invoke(runner, mock_deps, mock_output,
                         ["generate", "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 0
        call_args = mock_processor.process_generate.call_args
        config = call_args[0][0].config
        assert config.backend == Backend.PYWAL


class TestGenerateParamFlag:
    def test_param_key_value_overrides(
        self, runner, mock_deps, mock_processor, mock_output, mock_config_resolver,
        monkeypatch,
    ) -> None:
        mock_config_resolver.resolve.return_value = _default_app_settings()
        result = _invoke(runner, mock_deps, mock_output,
                         ["generate", "--backend", "pywal",
                          "--param", "saturation=1.5", "--param", "algorithm=thief",
                          "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 0
        call_args = mock_processor.process_generate.call_args
        config = call_args[0][0].config
        assert config.params.get("saturation") == "1.5"
        assert config.params.get("algorithm") == "thief"

    def test_param_bogus_raises_config_error(
        self, runner, mock_deps, mock_processor, mock_output, mock_config_resolver,
        mock_backend_catalog_loader, monkeypatch,
    ) -> None:
        mock_backend_catalog_loader.load.return_value = {
            Backend.CUSTOM: BackendDefinition(
                backend=Backend.CUSTOM,
                display_name="Custom",
                description="",
                parameters=(),
                min_version="0.0.0",
            ),
        }
        result = _invoke(runner, mock_deps, mock_output,
                         ["generate", "--backend", "custom", "--param", "bogus=1",
                          "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 1
        mock_output.error.assert_called_once()
        call_arg = mock_output.error.call_args[0][0]
        assert isinstance(call_arg, ConfigResolutionError)

    def test_param_no_equals_dropped_silently(
        self, runner, mock_deps, mock_processor, mock_output, mock_config_resolver,
        monkeypatch,
    ) -> None:
        result = _invoke(runner, mock_deps, mock_output,
                         ["generate", "--param", "badformat", "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 0


class TestGenerateFormatFlag:
    def test_format_flag_only_renders_those(
        self, runner, mock_deps, mock_processor, mock_output, mock_config_resolver,
        monkeypatch,
    ) -> None:
        mock_config_resolver.resolve.return_value = _default_app_settings()
        result = _invoke(runner, mock_deps, mock_output,
                         ["generate", "-f", "json", "-f", "css", "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 0
        call_args = mock_processor.process_generate.call_args
        config = call_args[0][0].config
        assert ColorFormat.JSON in config.formats
        assert ColorFormat.CSS in config.formats

    def test_format_omitted_uses_settings_default(
        self, runner, mock_deps, mock_processor, mock_output, mock_config_resolver,
        monkeypatch,
    ) -> None:
        mock_config_resolver.resolve.return_value = AppSettings(
            output=OutputSettings(
                directory=Path("/tmp/color-scheme"),
                default_formats=(ColorFormat.JSON, ColorFormat.SH),
                overwrite=False,
            ),
            generation=GenerationSettings(backend=Backend.CUSTOM, default_params={}),
            template=TemplateSettings(
                templates_dir=None,
                custom_templates_dir=None,
            ),
            runtime=RuntimeSettings(
                mode="local",  # type: ignore[arg-type]
            ),
            container=ContainerSettings(
                image_prefix="csg",
                image_tag="latest",
                timeout_seconds=60,
                memory_limit="512m",
                mount_timeout_seconds=30,
            ),
        )
        result = _invoke(runner, mock_deps, mock_output,
                         ["generate", "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 0
        call_args = mock_processor.process_generate.call_args
        config = call_args[0][0].config
        assert ColorFormat.JSON in config.formats
        assert ColorFormat.SH in config.formats

    def test_format_invalid_rejected(
        self, runner, mock_deps, mock_processor, mock_output,
        monkeypatch,
    ) -> None:
        result = _invoke(runner, mock_deps, mock_output,
                         ["generate", "-f", "invalid_format", "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 2


class TestGenerateOutputDirFlag:
    def test_output_dir_flag_writes_there(
        self, runner, mock_deps, mock_processor, mock_output, mock_config_resolver,
        monkeypatch,
    ) -> None:
        result = _invoke(runner, mock_deps, mock_output,
                         ["generate", "-o", "/custom/output", "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 0
        call_args = mock_processor.process_generate.call_args
        config = call_args[0][0].config
        assert config.output_dir == Path("/custom/output")

    def test_output_dir_omitted_uses_settings(
        self, runner, mock_deps, mock_processor, mock_output, mock_config_resolver,
        monkeypatch,
    ) -> None:
        mock_config_resolver.resolve.return_value = AppSettings(
            output=OutputSettings(
                directory=Path("/custom/output"),
                default_formats=(),
                overwrite=False,
            ),
            generation=GenerationSettings(backend=Backend.CUSTOM, default_params={}),
            template=TemplateSettings(
                templates_dir=None,
                custom_templates_dir=None,
            ),
            runtime=RuntimeSettings(
                mode="local",  # type: ignore[arg-type]
            ),
            container=ContainerSettings(
                image_prefix="csg",
                image_tag="latest",
                timeout_seconds=60,
                memory_limit="512m",
                mount_timeout_seconds=30,
            ),
        )
        result = _invoke(runner, mock_deps, mock_output,
                         ["generate", "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 0
        call_args = mock_processor.process_generate.call_args
        config = call_args[0][0].config
        assert config.output_dir == Path("/custom/output")


class TestGenerateBackendUnavailable:
    def test_all_backends_unavailable_raises_error(
        self, runner, mock_deps, mock_processor, mock_output,
        monkeypatch,
    ) -> None:
        mock_processor.process_generate.side_effect = BackendNotAvailableError(
            backend=Backend.CUSTOM,
            hint="Try `csg install`",
        )
        result = _invoke(runner, mock_deps, mock_output,
                         ["generate", "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 1
        mock_output.error.assert_called_once()
        call_arg = mock_output.error.call_args[0][0]
        assert isinstance(call_arg, BackendNotAvailableError)


class TestGenerateConfigResolution:
    def test_resolves_config_via_assembled_config_resolver(
        self, runner, mock_deps, mock_processor, mock_output, mock_config_resolver,
        monkeypatch,
    ) -> None:
        result = _invoke(runner, mock_deps, mock_output,
                         ["generate", "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 0
        mock_config_resolver.resolve.assert_called_once()

    def test_resolver_failure_falls_back_to_defaults(
        self, runner, mock_deps, mock_processor, mock_output, mock_config_resolver,
        monkeypatch,
    ) -> None:
        mock_config_resolver.resolve.side_effect = ColorSchemeError("config not found")
        result = _invoke(runner, mock_deps, mock_output,
                         ["generate", "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 0
        mock_processor.process_generate.assert_called_once()

    def test_no_backend_catalog_loader_raises_on_params(
        self, runner, mock_deps, mock_processor, mock_output, mock_config_resolver,
        monkeypatch,
    ) -> None:
        mock_deps.backend_catalog_loader = None
        result = _invoke(runner, mock_deps, mock_output,
                         ["generate", "--param", "saturation=1.0", "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 1
        mock_output.error.assert_called_once()
        call_arg = mock_output.error.call_args[0][0]
        assert isinstance(call_arg, ConfigResolutionError)

    def test_backend_not_in_catalog_with_params_raises(
        self, runner, mock_deps, mock_processor, mock_output, mock_config_resolver,
        mock_backend_catalog_loader, monkeypatch,
    ) -> None:
        mock_backend_catalog_loader.load.return_value = {}
        result = _invoke(runner, mock_deps, mock_output,
                         ["generate", "--backend", "pywal", "--param", "saturation=1.0",
                          "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 1
        mock_output.error.assert_called_once()
        call_arg = mock_output.error.call_args[0][0]
        assert isinstance(call_arg, ConfigResolutionError)


class TestShowFlags:
    def test_show_accepts_backend_and_param(
        self, runner, mock_deps, mock_processor, mock_output, mock_config_resolver,
        monkeypatch,
    ) -> None:
        mock_processor.process_show.return_value = GenerationResult(
            success=True,
            color_scheme=None,
            output_files=(),
            backend=Backend.PYWAL,
            stderr="",
            return_code=0,
            duration=0.5,
        )
        result = _invoke(runner, mock_deps, mock_output,
                         ["show", "--backend", "pywal", "--param", "saturation=1.5",
                          "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 0

    def test_show_rejects_format_flag(
        self, runner, mock_deps, mock_processor, mock_output,
        monkeypatch,
    ) -> None:
        result = _invoke(runner, mock_deps, mock_output,
                         ["show", "-f", "json", "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 2

    def test_show_rejects_output_dir_flag(
        self, runner, mock_deps, mock_processor, mock_output,
        monkeypatch,
    ) -> None:
        result = _invoke(runner, mock_deps, mock_output,
                         ["show", "-o", "/tmp", "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 2

    def test_show_all_backends_unavailable_raises_error(
        self, runner, mock_deps, mock_processor, mock_output,
        monkeypatch,
    ) -> None:
        mock_processor.process_show.side_effect = BackendNotAvailableError(
            backend=Backend.CUSTOM,
            hint="Try `csg install`",
        )
        result = _invoke(runner, mock_deps, mock_output,
                         ["show", "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 1
        mock_output.error.assert_called_once()
        call_arg = mock_output.error.call_args[0][0]
        assert isinstance(call_arg, BackendNotAvailableError)

    def test_show_resolver_failure_falls_back_to_defaults(
        self, runner, mock_deps, mock_processor, mock_output, mock_config_resolver,
        monkeypatch,
    ) -> None:
        mock_processor.process_show.return_value = GenerationResult(
            success=True,
            color_scheme=None,
            output_files=(),
            backend=Backend.CUSTOM,
            stderr="",
            return_code=0,
            duration=0.5,
        )
        mock_config_resolver.resolve.side_effect = ColorSchemeError("config not found")
        result = _invoke(runner, mock_deps, mock_output,
                         ["show", "/tmp/test.jpg"], monkeypatch)
        assert result.exit_code == 0
        mock_processor.process_show.assert_called_once()
