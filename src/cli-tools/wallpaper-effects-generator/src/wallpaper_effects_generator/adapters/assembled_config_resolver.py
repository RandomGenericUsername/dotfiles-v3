from __future__ import annotations

from pathlib import Path

from config_assembler_engine import (
    OverrideRule,
    OverrideSource,
    ResolutionPolicy,
)
from config_assembler_engine.adapters.factories import create_standard_assembler
from config_assembler_engine.adapters.parsers.toml_parser import TomlConfigParser
from config_assembler_engine.adapters.strategies.cli_path import CliPathStrategy
from config_assembler_engine.adapters.strategies.default_file import DefaultFileStrategy
from config_assembler_engine.adapters.strategies.directory import DirectoryTraversalStrategy
from config_assembler_engine.adapters.strategies.env_path import EnvPathStrategy
from config_assembler_engine.adapters.strategies.xdg import XdgStrategy

from wallpaper_effects_generator.adapters.schemas.settings_schema import CoreSettingsSchema
from wallpaper_effects_generator.domain.enums import RuntimeMode, Verbosity
from wallpaper_effects_generator.domain.models import (
    AppSettings,
    BackendSettings,
    ContainerSettings,
    ExecutionSettings,
    OutputSettings,
    ProcessingSettings,
    RuntimeSettings,
)


def _pydantic_to_app_settings(schema: CoreSettingsSchema) -> AppSettings:
    raw_mode = schema.runtime.mode.lower().strip()
    try:
        runtime_mode = RuntimeMode(raw_mode)
    except ValueError:
        runtime_mode = RuntimeMode.LOCAL

    return AppSettings(
        version=schema.version,
        execution=ExecutionSettings(
            parallel=schema.execution.parallel,
            strict=schema.execution.strict,
            max_workers=schema.execution.max_workers,
        ),
        output=OutputSettings(
            verbosity=Verbosity(schema.output.verbosity),
        ),
        processing=ProcessingSettings(
            temp_dir=Path(schema.processing.temp_dir) if schema.processing.temp_dir else None,
        ),
        backend=BackendSettings(
            binary=schema.backend.binary,
        ),
        runtime=RuntimeSettings(mode=runtime_mode),
        container=ContainerSettings(
            engine=schema.container.engine,
            image_tag=schema.container.image_tag,
            image_registry=schema.container.image_registry or "",
        ),
    )


_STRATEGIES = [
    CliPathStrategy(),
    EnvPathStrategy(),
    DirectoryTraversalStrategy(filename="settings.toml", max_levels=3),
    XdgStrategy(xdg_subdir="weg", filename="settings.toml"),
]

_ALL_SETTINGS_FIELDS = [
    "execution.parallel",
    "execution.strict",
    "execution.max_workers",
    "output.verbosity",
    "output.directory",
    "backend.binary",
    "runtime.mode",
    "container.engine",
    "container.image_tag",
    "container.image_registry",
]

_OVERRIDE_RULES = [
    OverrideRule(field_path=field, sources={OverrideSource.ENV, OverrideSource.CLI})
    for field in _ALL_SETTINGS_FIELDS
]


class AssembledConfigResolver:
    def __init__(self, default_settings_path: Path | None = None) -> None:
        strategies = list(_STRATEGIES)
        if default_settings_path:
            strategies.append(DefaultFileStrategy(path=default_settings_path))
        self._assembler = create_standard_assembler(
            parser=TomlConfigParser(),
            strategies=strategies,
        )
        self._resolved_path: Path | None = None

    def resolve(self, explicit_path: Path | None = None) -> AppSettings:
        result = self._assembler.execute(
            policy=ResolutionPolicy(env_prefix="WALLPAPER"),
            rules=_OVERRIDE_RULES,
            schema=CoreSettingsSchema,
            explicit_path=str(explicit_path) if explicit_path else None,
        )
        self._resolved_path = result.resolved_path.path
        return _pydantic_to_app_settings(result.config)

    def get_resolved_path(self) -> Path | None:
        return self._resolved_path
