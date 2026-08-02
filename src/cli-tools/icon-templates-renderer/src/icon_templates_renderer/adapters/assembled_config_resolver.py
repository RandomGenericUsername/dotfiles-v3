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

from icon_templates_renderer.adapters.schemas.settings_schema import CoreSettingsSchema
from icon_templates_renderer.constants import (
    CONFIG_FILENAME,
    CONFIG_TRAVERSAL_DEPTH,
    CONFIG_XDG_SUBDIR,
)
from icon_templates_renderer.domain.enums import Verbosity
from icon_templates_renderer.domain.models import AppSettings, OutputSettings


class AssembledConfigResolver:
    def __init__(self, assembler: AssembleConfiguration | None = None) -> None:
        strategies = [
            CliPathStrategy(kind=ResourceKind.FILE),
            EnvPathStrategy(kind=ResourceKind.FILE),
            DirectoryTraversalStrategy(
                filename=CONFIG_FILENAME,
                max_levels=CONFIG_TRAVERSAL_DEPTH,
                kind=ResourceKind.FILE,
            ),
            XdgStrategy(
                xdg_subdir=CONFIG_XDG_SUBDIR,
                filename=CONFIG_FILENAME,
                kind=ResourceKind.FILE,
            ),
            DefaultFileStrategy(
                path=Path(resource_files("icon_templates_renderer") / "defaults" / CONFIG_FILENAME),
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
        self._policy = ResolutionPolicy(env_prefix="ICON_RENDERER")
        self._rules = [
            OverrideRule("output.verbosity", {OverrideSource.CLI, OverrideSource.ENV}),
        ]
        self._resolved_path: Path | None = None

    def resolve(
        self,
        *,
        cli_overrides: dict[str, str] | None = None,
        explicit_path: str | None = None,
    ) -> AppSettings:
        result = self._assembler.execute(
            policy=self._policy,
            rules=self._rules,
            schema=CoreSettingsSchema,
            cli_overrides=cli_overrides,
            explicit_path=explicit_path,
        )
        self._resolved_path = result.resolved_path.path
        return AppSettings(
            output=OutputSettings(
                verbosity=Verbosity(result.config.output.verbosity),
            ),
        )

    def get_resolved_path(self) -> Path | None:
        return self._resolved_path
