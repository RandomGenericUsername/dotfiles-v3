import os
from pathlib import Path

from pydantic import BaseModel, Field

from config_assembler_engine import (
    OverrideRule,
    OverrideSource,
    ResolutionPolicy,
)
from config_assembler_engine.adapters.config_validator import PydanticValidator
from config_assembler_engine.adapters.env_reader import OsEnvironmentReader
from config_assembler_engine.adapters.factories import create_standard_assembler
from config_assembler_engine.adapters.parsers.yaml_parser import YamlConfigParser
from config_assembler_engine.adapters.path_resolver import CompositePathResolver
from config_assembler_engine.adapters.strategies.cli_path import CliPathStrategy
from config_assembler_engine.adapters.strategies.default_file import DefaultFileStrategy
from config_assembler_engine.adapters.strategies.directory import DirectoryTraversalStrategy
from config_assembler_engine.adapters.strategies.env_path import EnvPathStrategy
from config_assembler_engine.adapters.strategies.xdg import XdgStrategy
from config_assembler_engine.adapters.type_coercer import PydanticTypeCoercer
from config_assembler_engine.domain.models import ResourceKind


class AppConfig(BaseModel):
    engine: str = Field(default="docker")
    timeout: int = Field(default=30)
    mounts: list[str] = Field(default_factory=list)


class TestFullPipeline:
    def test_end_to_end_with_real_adapters(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("engine: docker\ntimeout: 30\nmounts:\n  - /data\n")

        monkeypatch.chdir(tmp_path)

        strategies = [
            DirectoryTraversalStrategy(filename="config.yaml", max_levels=0, kind=ResourceKind.FILE),
        ]

        assembler = create_standard_assembler(
            parser=YamlConfigParser(),
            strategies=strategies,
        )

        result = assembler.execute(
            policy=ResolutionPolicy(env_prefix="TEST"),
            rules=[
                OverrideRule(field_path="timeout", sources={OverrideSource.ENV, OverrideSource.CLI}),
                OverrideRule(field_path="engine", sources={OverrideSource.CLI}),
            ],
            schema=AppConfig,
            cli_overrides={"engine": "podman", "timeout": "60"},
        )

        assert result.config.engine == "podman"
        assert result.config.timeout == 60
        assert result.config.mounts == ["/data"]
        assert result.resolved_path.path == config_file.resolve()
        assert len(result.applied_overrides) == 2

    def test_env_override_in_full_pipeline(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("engine: docker\ntimeout: 30\n")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("TEST__TIMEOUT", "99")

        assemblies = create_standard_assembler(parser=YamlConfigParser())

        result = assemblies.execute(
            policy=ResolutionPolicy(env_prefix="TEST"),
            rules=[
                OverrideRule(field_path="timeout", sources={OverrideSource.ENV}),
            ],
            schema=AppConfig,
        )

        assert result.config.timeout == 99
        assert result.config.engine == "docker"
