from pathlib import Path
from typing import Any

from pydantic import BaseModel

from config_assembler_engine.domain.models import (
    AppliedOverride,
    AssemblyResult,
    OverrideRule,
    OverrideSource,
    OverrideValue,
    PathSource,
    ResolutionPolicy,
    ResolvedPath,
)


class TestPathSource:
    def test_members(self):
        assert PathSource.CLI_PATH.value == "cli_path"
        assert PathSource.ENV_PATH.value == "env_path"
        assert PathSource.DIRECTORY.value == "directory"
        assert PathSource.XDG.value == "xdg"
        assert PathSource.DEFAULT.value == "default"

    def test_is_enum(self):
        import enum
        assert issubclass(PathSource, enum.Enum)


class TestOverrideSource:
    def test_members(self):
        assert OverrideSource.ENV.value == "env"
        assert OverrideSource.CLI.value == "cli"

    def test_is_enum(self):
        import enum
        assert issubclass(OverrideSource, enum.Enum)


class TestResolutionPolicy:
    def test_fields(self):
        p = ResolutionPolicy(env_prefix="ABC_PROJECT")
        assert p.env_prefix == "ABC_PROJECT"

    def test_defaults(self):
        p = ResolutionPolicy(env_prefix="")
        assert p.env_prefix == ""


class TestOverrideRule:
    def test_fields(self):
        rule = OverrideRule(field_path="timeout", sources={OverrideSource.ENV, OverrideSource.CLI})
        assert rule.field_path == "timeout"
        assert rule.sources == {OverrideSource.ENV, OverrideSource.CLI}

    def test_single_source(self):
        rule = OverrideRule(field_path="engine", sources={OverrideSource.CLI})
        assert OverrideSource.CLI in rule.sources
        assert OverrideSource.ENV not in rule.sources


class TestResolvedPath:
    def test_fields(self):
        p = ResolvedPath(path=Path("/etc/config.yaml"), source=PathSource.CLI_PATH)
        assert p.path == Path("/etc/config.yaml")
        assert p.source == PathSource.CLI_PATH


class TestOverrideValue:
    def test_fields(self):
        ov = OverrideValue(field_path="timeout", raw_value="30", source=OverrideSource.ENV)
        assert ov.field_path == "timeout"
        assert ov.raw_value == "30"
        assert ov.source == OverrideSource.ENV


class TestAppliedOverride:
    def test_fields(self):
        ao = AppliedOverride(
            field_path="timeout",
            raw_value="30",
            coerced_value=30,
            source=OverrideSource.CLI,
        )
        assert ao.field_path == "timeout"
        assert ao.raw_value == "30"
        assert ao.coerced_value == 30
        assert ao.source == OverrideSource.CLI

    def test_coerced_value_any_type(self):
        ao = AppliedOverride(
            field_path="mounts",
            raw_value="/a,/b",
            coerced_value=["/a", "/b"],
            source=OverrideSource.ENV,
        )
        assert ao.coerced_value == ["/a", "/b"]


class TestAssemblyResult:
    def test_fields(self):
        class FakeConfig(BaseModel):
            x: int = 1

        rp = ResolvedPath(path=Path("/a.yaml"), source=PathSource.DEFAULT)
        config = FakeConfig()
        ao = AppliedOverride(
            field_path="x", raw_value="2", coerced_value=2, source=OverrideSource.CLI
        )
        result = AssemblyResult(config=config, resolved_path=rp, applied_overrides=[ao])
        assert result.config is config
        assert result.resolved_path is rp
        assert result.applied_overrides == [ao]

    def test_empty_overrides(self):
        class FakeConfig(BaseModel):
            x: int = 1

        rp = ResolvedPath(path=Path("/a.yaml"), source=PathSource.DEFAULT)
        result = AssemblyResult(config=FakeConfig(), resolved_path=rp, applied_overrides=[])
        assert result.applied_overrides == []
