from __future__ import annotations

from importlib.resources import files as resource_files
from pathlib import Path

from config_assembler_engine.adapters.config_validator import PydanticValidator
from config_assembler_engine.adapters.env_reader import OsEnvironmentReader
from config_assembler_engine.adapters.parsers.toml_parser import TomlConfigParser
from config_assembler_engine.adapters.path_resolver import CompositePathResolver
from config_assembler_engine.adapters.strategies.cli_path import CliPathStrategy
from config_assembler_engine.adapters.strategies.default_file import DefaultFileStrategy
from config_assembler_engine.adapters.strategies.directory import DirectoryTraversalStrategy
from config_assembler_engine.adapters.strategies.env_path import EnvPathStrategy
from config_assembler_engine.adapters.strategies.xdg import XdgStrategy
from config_assembler_engine.adapters.type_coercer import PydanticTypeCoercer
from config_assembler_engine.application.use_cases import AssembleConfiguration
from config_assembler_engine.domain.models import (
    OverrideRule,
    OverrideSource,
    ResolutionPolicy,
    ResourceKind,
)
from config_assembler_engine.errors import ConfigParseError, PathResolutionError

from color_scheme_generator.adapters.settings.schema import CoreSettingsSchema
from color_scheme_generator.domain.enums import Backend, RuntimeMode, Verbosity
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


def _convert_to_app_settings(validated: CoreSettingsSchema) -> AppSettings:
    return AppSettings(
        output=OutputSettings(
            directory=validated.output.directory,
            default_formats=tuple(validated.output.default_formats),
            overwrite=validated.output.overwrite,
            verbosity=Verbosity(validated.output.verbosity),
        ),
        generation=GenerationSettings(
            backend=Backend(validated.generation.backend),
            default_params=dict(validated.generation.default_params),
        ),
        template=TemplateSettings(
            templates_dir=validated.template.templates_dir,
            custom_templates_dir=validated.template.custom_templates_dir,
        ),
        runtime=RuntimeSettings(
            mode=RuntimeMode(validated.runtime.mode),
        ),
        container=ContainerSettings(
            engine=validated.container.engine,
            image_prefix=validated.container.image_prefix,
            image_tag=validated.container.image_tag,
            timeout_seconds=validated.container.timeout_seconds,
            memory_limit=validated.container.memory_limit,
            mount_timeout_seconds=validated.container.mount_timeout_seconds,
        ),
    )


class AssembledConfigResolver:
    def __init__(self, assembler: AssembleConfiguration | None = None) -> None:
        strategies = [
            CliPathStrategy(kind=ResourceKind.FILE),
            EnvPathStrategy(kind=ResourceKind.FILE),
            DirectoryTraversalStrategy(filename="settings.toml", max_levels=3, kind=ResourceKind.FILE),
            XdgStrategy(xdg_subdir="color-scheme-generator", filename="settings.toml", kind=ResourceKind.FILE),
            DefaultFileStrategy(
                path=Path(resource_files("color_scheme_generator") / "defaults" / "settings.toml"),
                kind=ResourceKind.FILE,
            ),
        ]
        self._assembler = assembler or AssembleConfiguration(
            path_resolver=CompositePathResolver(strategies),
            parser=TomlConfigParser(),
            env_reader=OsEnvironmentReader(),
            validator=PydanticValidator(),
            coercer=PydanticTypeCoercer(),
        )
        self._policy = ResolutionPolicy(env_prefix="COLORSCHEME")
        self._rules = [
            OverrideRule("output.directory", {OverrideSource.CLI, OverrideSource.ENV}),
            OverrideRule("output.default_formats", {OverrideSource.CLI, OverrideSource.ENV}),
            OverrideRule("output.overwrite", {OverrideSource.CLI, OverrideSource.ENV}),
            OverrideRule("output.verbosity", {OverrideSource.CLI, OverrideSource.ENV}),
            OverrideRule("generation.backend", {OverrideSource.CLI, OverrideSource.ENV}),
            OverrideRule("generation.default_params", {OverrideSource.CLI, OverrideSource.ENV}),
            OverrideRule("template.templates_dir", {OverrideSource.CLI, OverrideSource.ENV}),
            OverrideRule("template.custom_templates_dir", {OverrideSource.CLI, OverrideSource.ENV}),
            OverrideRule("runtime.mode", {OverrideSource.CLI, OverrideSource.ENV}),
            OverrideRule("container.engine", {OverrideSource.CLI, OverrideSource.ENV}),
            OverrideRule("container.image_prefix", {OverrideSource.CLI, OverrideSource.ENV}),
            OverrideRule("container.image_tag", {OverrideSource.CLI, OverrideSource.ENV}),
            OverrideRule("container.timeout_seconds", {OverrideSource.CLI, OverrideSource.ENV}),
            OverrideRule("container.memory_limit", {OverrideSource.CLI, OverrideSource.ENV}),
            OverrideRule(
                "container.mount_timeout_seconds", {OverrideSource.CLI, OverrideSource.ENV}
            ),
        ]
        self.last_result: ConfigResolverResult | None = None

    def resolve(
        self,
        *,
        cli_overrides: dict[str, str] | None = None,
        explicit_path: str | None = None,
    ) -> AppSettings:
        try:
            result = self._assembler.execute(
                policy=self._policy,
                rules=self._rules,
                schema=CoreSettingsSchema,
                cli_overrides=cli_overrides,
                explicit_path=explicit_path,
            )
        except ConfigParseError as e:
            raise ConfigResolutionError(
                key="settings.toml",
                reason=str(e),
                source=e,
            ) from e
        except PathResolutionError as e:
            raise ConfigResolutionError(
                key="settings.toml",
                reason=str(e),
                source=e,
            ) from e
        self.last_result = ConfigResolverResult(
            resolved_path=result.resolved_path.path,
            applied_overrides=tuple(
                AppliedOverride(
                    field_path=o.field_path,
                    raw_value=o.raw_value,
                    coerced_value=o.coerced_value,
                    source=o.source.value,
                )
                for o in result.applied_overrides
            ),
        )
        return _convert_to_app_settings(result.config)
