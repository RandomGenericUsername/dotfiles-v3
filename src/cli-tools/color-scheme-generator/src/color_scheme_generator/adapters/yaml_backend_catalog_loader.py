from __future__ import annotations

import logging
from importlib.resources import files as resource_files

from config_assembler_engine.adapters.config_validator import PydanticValidator
from config_assembler_engine.adapters.env_reader import OsEnvironmentReader
from config_assembler_engine.adapters.parsers.yaml_parser import YamlConfigParser
from config_assembler_engine.adapters.path_resolver import CompositePathResolver
from config_assembler_engine.adapters.strategies.cli_path import CliPathStrategy
from config_assembler_engine.adapters.strategies.default_file import DefaultFileStrategy
from config_assembler_engine.adapters.strategies.directory import DirectoryTraversalStrategy
from config_assembler_engine.adapters.strategies.env_path import EnvPathStrategy
from config_assembler_engine.adapters.strategies.xdg import XdgStrategy
from config_assembler_engine.adapters.type_coercer import PydanticTypeCoercer
from config_assembler_engine.application.use_cases import AssembleConfiguration
from config_assembler_engine.domain.models import ResolutionPolicy
from config_assembler_engine.errors import (
    ConfigParseError,
    ConfigValidationError,
    PathResolutionError,
)

from color_scheme_generator.adapters.schemas.backends_catalog_schema import BackendsCatalogSchema
from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import ConfigResolutionError
from color_scheme_generator.domain.models import BackendDefinition, BackendParameterDefinition

logger = logging.getLogger(__name__)


def _schema_to_domain(schema: BackendsCatalogSchema) -> dict[Backend, BackendDefinition]:
    result: dict[Backend, BackendDefinition] = {}
    for name, def_schema in schema.root.items():
        try:
            backend = Backend(name)
        except ValueError:
            logger.warning("Unknown backend '%s' in catalog — skipping", name)
            continue
        params = tuple(
            BackendParameterDefinition(
                name=p.key,
                type_=p.param_type,
                description=p.description,
                required=p.required,
                choices=tuple(p.choices) if p.choices else None,
                default=p.default,
            )
            for p in def_schema.parameters
        )
        display_name = def_schema.display_name or backend.value.title()
        result[backend] = BackendDefinition(
            backend=backend,
            display_name=display_name,
            description=def_schema.description,
            parameters=params,
            min_version="0.0.0",
        )
    return result


class YamlBackendCatalogLoader:
    def __init__(self, assembler: AssembleConfiguration | None = None) -> None:
        strategies = [
            CliPathStrategy(),
            EnvPathStrategy(),
            DirectoryTraversalStrategy(filename="backends.yaml", max_levels=3),
            XdgStrategy(xdg_subdir="color-scheme-generator", filename="backends.yaml"),
            DefaultFileStrategy(
                path=resource_files("color_scheme_generator.defaults") / "backends.yaml"
            ),
        ]
        self._assembler = assembler or AssembleConfiguration(
            path_resolver=CompositePathResolver(strategies),
            parser=YamlConfigParser(),
            env_reader=OsEnvironmentReader(),
            validator=PydanticValidator(),
            coercer=PydanticTypeCoercer(),
        )
        self._policy = ResolutionPolicy(env_prefix="COLORSCHEME_BACKENDS")

    def load(self, *, explicit_path: str | None = None) -> dict[Backend, BackendDefinition]:
        try:
            result = self._assembler.execute(
                policy=self._policy,
                rules=[],
                schema=BackendsCatalogSchema,
                explicit_path=explicit_path,
            )
        except ConfigParseError as e:
            raise ConfigResolutionError(
                key="backends.yaml",
                reason=str(e),
                source=e,
            ) from e
        except PathResolutionError as e:
            raise ConfigResolutionError(
                key="backends.yaml",
                reason=str(e),
                source=e,
            ) from e
        except ConfigValidationError as e:
            raise ConfigResolutionError(
                key="backends.yaml",
                reason=str(e),
                source=e,
            ) from e
        return _schema_to_domain(result.config)
