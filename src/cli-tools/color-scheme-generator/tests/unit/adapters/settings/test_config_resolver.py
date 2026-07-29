from __future__ import annotations

from pathlib import Path
from unittest.mock import create_autospec

import pytest
from config_assembler_engine.application.use_cases import AssembleConfiguration
from config_assembler_engine.domain.models import (
    AppliedOverride,
    AssemblyResult,
    OverrideSource,
    PathSource,
    ResolvedPath,
)

from color_scheme_generator.adapters.settings.config_resolver import AssembledConfigResolver
from color_scheme_generator.adapters.settings.schema import CoreSettingsSchema
from color_scheme_generator.domain.enums import Backend, RuntimeMode
from color_scheme_generator.domain.exceptions import ConfigResolutionError
from color_scheme_generator.domain.models import AppliedOverride as DomainAppliedOverride
from color_scheme_generator.domain.models import (
    AppSettings,
    ConfigResolverResult,
    ContainerSettings,
    GenerationSettings,
    OutputSettings,
    RuntimeSettings,
    TemplateSettings,
)
from color_scheme_generator.ports.config_resolver import ConfigResolverPort


def _make_assembly_result(config: CoreSettingsSchema | None = None) -> AssemblyResult:
    if config is None:
        config = CoreSettingsSchema(
            output={"directory": "/tmp/out"},
            generation={"backend": "custom"},
            template={},
            runtime={"mode": "local"},
            container={"engine": "docker"},
        )
    return AssemblyResult(
        config=config,
        resolved_path=ResolvedPath(path=Path("/tmp/settings.toml"), source=PathSource.CLI_PATH),
        applied_overrides=[
            AppliedOverride(
                field_path="runtime.mode",
                raw_value="container",
                coerced_value="container",
                source=OverrideSource.CLI,
            ),
        ],
    )


class TestAssembledConfigResolver:
    def test_implements_config_resolver_port(self) -> None:
        resolver = AssembledConfigResolver()
        assert isinstance(resolver, ConfigResolverPort)

    def test_resolve_returns_app_settings(self) -> None:
        mock_assembler = create_autospec(AssembleConfiguration, instance=True)
        mock_assembler.execute.return_value = _make_assembly_result()

        resolver = AssembledConfigResolver(assembler=mock_assembler)
        result = resolver.resolve()

        assert isinstance(result, AppSettings)
        assert isinstance(result.output, OutputSettings)
        assert isinstance(result.generation, GenerationSettings)
        assert isinstance(result.template, TemplateSettings)
        assert isinstance(result.runtime, RuntimeSettings)
        assert isinstance(result.container, ContainerSettings)
        assert result.generation.backend == Backend.CUSTOM
        assert result.runtime.mode == RuntimeMode.LOCAL
        assert result.container.engine == "docker"

    def test_resolve_stores_last_result(self) -> None:
        mock_assembler = create_autospec(AssembleConfiguration, instance=True)
        raw = _make_assembly_result()
        mock_assembler.execute.return_value = raw

        resolver = AssembledConfigResolver(assembler=mock_assembler)
        resolver.resolve()

        assert resolver.last_result is not None
        assert isinstance(resolver.last_result, ConfigResolverResult)
        assert resolver.last_result.resolved_path == Path("/tmp/settings.toml")
        assert len(resolver.last_result.applied_overrides) == 1
        assert isinstance(resolver.last_result.applied_overrides[0], DomainAppliedOverride)
        assert resolver.last_result.applied_overrides[0].field_path == "runtime.mode"
        assert resolver.last_result.applied_overrides[0].source == "cli"

    def test_resolve_with_cli_overrides(self) -> None:
        mock_assembler = create_autospec(AssembleConfiguration, instance=True)
        mock_assembler.execute.return_value = _make_assembly_result()

        resolver = AssembledConfigResolver(assembler=mock_assembler)
        resolver.resolve(cli_overrides={"generation.backend": "pywal"})

        _, kwargs = mock_assembler.execute.call_args
        assert kwargs["cli_overrides"] == {"generation.backend": "pywal"}

    def test_resolve_with_explicit_path(self) -> None:
        mock_assembler = create_autospec(AssembleConfiguration, instance=True)
        mock_assembler.execute.return_value = _make_assembly_result()

        resolver = AssembledConfigResolver(assembler=mock_assembler)
        resolver.resolve(explicit_path="/custom/path/settings.toml")

        _, kwargs = mock_assembler.execute.call_args
        assert kwargs["explicit_path"] == "/custom/path/settings.toml"

    def test_resolve_passes_correct_policy(self) -> None:
        mock_assembler = create_autospec(AssembleConfiguration, instance=True)
        mock_assembler.execute.return_value = _make_assembly_result()

        resolver = AssembledConfigResolver(assembler=mock_assembler)
        resolver.resolve()

        _, kwargs = mock_assembler.execute.call_args
        assert kwargs["schema"] == CoreSettingsSchema
        assert kwargs["policy"].env_prefix == "COLORSCHEME"
        assert len(kwargs["rules"]) > 0


    def test_config_resolution_separate_instances(self) -> None:
        from color_scheme_generator.adapters.yaml_backend_catalog_loader import (
            YamlBackendCatalogLoader,
        )

        resolver = AssembledConfigResolver()
        catalog_loader = YamlBackendCatalogLoader()

        assert resolver._assembler is not catalog_loader._assembler


class TestAssembledConfigResolverIntegration:
    def test_malformed_toml_raises_config_resolution_error(self, tmp_path: Path) -> None:
        malformed = tmp_path / "settings.toml"
        malformed.write_text("{{{ not valid toml }}}")

        resolver = AssembledConfigResolver()
        with pytest.raises(ConfigResolutionError) as excinfo:
            resolver.resolve(explicit_path=str(malformed))

        assert "settings.toml" in str(excinfo.value.key) or "toml" in str(excinfo.value).lower()
