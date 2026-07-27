from pathlib import Path

from config_assembler_engine.adapters.config_validator import PydanticValidator
from config_assembler_engine.adapters.env_reader import OsEnvironmentReader
from config_assembler_engine.adapters.path_resolver import CompositePathResolver
from config_assembler_engine.adapters.strategies.cli_path import CliPathStrategy
from config_assembler_engine.adapters.strategies.default_file import DefaultFileStrategy
from config_assembler_engine.adapters.strategies.directory import DirectoryTraversalStrategy
from config_assembler_engine.adapters.strategies.env_path import EnvPathStrategy
from config_assembler_engine.adapters.strategies.xdg import XdgStrategy
from config_assembler_engine.adapters.type_coercer import PydanticTypeCoercer
from config_assembler_engine.application.use_cases import AssembleConfiguration, AssembleDir
from config_assembler_engine.domain.models import ResourceKind
from config_assembler_engine.ports.config_parser import ConfigParserPort
from config_assembler_engine.ports.config_validator import ConfigValidatorPort
from config_assembler_engine.ports.path_resolver import ResolutionStrategy
from config_assembler_engine.ports.type_coercer import TypeCoercerPort

_DEFAULT_STRATEGIES = [
    CliPathStrategy(kind=ResourceKind.FILE),
    EnvPathStrategy(kind=ResourceKind.FILE),
    DirectoryTraversalStrategy(filename="config.yaml", max_levels=3, kind=ResourceKind.FILE),
    XdgStrategy(xdg_subdir="", filename="config.yaml", kind=ResourceKind.FILE),
    DefaultFileStrategy(path=Path("config.yaml"), kind=ResourceKind.FILE),
]


def create_directory_assembler(
    *,
    strategies: list[ResolutionStrategy] | None = None,
    file_pattern: str = "*",
) -> AssembleDir:
    return AssembleDir(
        path_resolver=CompositePathResolver(
            strategies if strategies is not None else _DEFAULT_STRATEGIES
        ),
        file_pattern=file_pattern,
    )


def create_standard_assembler(
    parser: ConfigParserPort,
    *,
    strategies: list[ResolutionStrategy] | None = None,
    validator: ConfigValidatorPort | None = None,
    coercer: TypeCoercerPort | None = None,
) -> AssembleConfiguration:
    env_reader = OsEnvironmentReader()
    return AssembleConfiguration(
        path_resolver=CompositePathResolver(
            strategies if strategies is not None else _DEFAULT_STRATEGIES
        ),
        parser=parser,
        env_reader=env_reader,
        validator=validator or PydanticValidator(),
        coercer=coercer or PydanticTypeCoercer(),
    )
