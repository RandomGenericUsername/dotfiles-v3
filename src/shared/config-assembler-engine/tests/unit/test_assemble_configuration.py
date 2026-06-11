from pathlib import Path
from typing import Any

from pydantic import BaseModel

from config_assembler_engine.application.use_cases import AssembleConfiguration
from config_assembler_engine.domain.models import (
    AppliedOverride,
    OverrideRule,
    OverrideSource,
    PathSource,
    ResolutionPolicy,
    ResolvedPath,
)
from config_assembler_engine.errors import ConfigValidationError, OverrideCoercionError, PathResolutionError


class FakeAppConfig(BaseModel):
    engine: str = "docker"
    timeout: int = 30
    mounts: list[str] = []


class FakePathResolver:
    def __init__(self, resolved: ResolvedPath | None = None) -> None:
        self._resolved = resolved or ResolvedPath(
            path=Path("/fake/config.yaml"), source=PathSource.DEFAULT
        )

    def resolve(
        self, policy: ResolutionPolicy, explicit_path: str | None = None
    ) -> ResolvedPath:
        if explicit_path == "/raise":
            raise PathResolutionError("forced")
        return self._resolved


class FakeParser:
    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self._data = data or {}

    def parse(self, path: Path) -> dict[str, Any]:
        return self._data


class FakeEnvReader:
    def __init__(self, env: dict[str, str] | None = None) -> None:
        self._env = env or {}

    def read(self, prefix: str) -> dict[str, str]:
        return self._env


class FakeValidator:
    def __init__(self) -> None:
        self.schema = None

    def validate(self, raw: dict[str, Any], schema: type[BaseModel]) -> BaseModel:
        self.schema = schema
        return schema.model_validate(raw)

    def get_field_info(self, schema: type[BaseModel], field_path: str) -> Any:
        from pydantic import BaseModel
        from typing import get_args, get_origin

        parts = field_path.split(".")
        current = schema
        for part in parts:
            if isinstance(current, type) and issubclass(current, BaseModel):
                current = current.model_fields[part].annotation
        return current


class FakeCoercer:
    def coerce(self, override, field_type: Any) -> Any:
        if field_type is int:
            try:
                return int(override.raw_value)
            except ValueError:
                raise OverrideCoercionError(
                    override.field_path, override.raw_value, "int", "bad"
                )
        return override.raw_value


class TestAssembleConfiguration:
    def test_basic_execution(self):
        uc = AssembleConfiguration(
            path_resolver=FakePathResolver(),
            parser=FakeParser({"engine": "podman", "timeout": 60}),
            env_reader=FakeEnvReader(),
            validator=FakeValidator(),
            coercer=FakeCoercer(),
        )
        result = uc.execute(
            policy=ResolutionPolicy(env_prefix="APP"),
            rules=[],
            schema=FakeAppConfig,
        )
        assert result.config.engine == "podman"
        assert result.config.timeout == 60
        assert result.resolved_path.path == Path("/fake/config.yaml")
        assert result.applied_overrides == []

    def test_uses_defaults_with_empty_config(self):
        uc = AssembleConfiguration(
            path_resolver=FakePathResolver(),
            parser=FakeParser({}),
            env_reader=FakeEnvReader(),
            validator=FakeValidator(),
            coercer=FakeCoercer(),
        )
        result = uc.execute(
            policy=ResolutionPolicy(env_prefix="APP"),
            rules=[],
            schema=FakeAppConfig,
        )
        assert result.config.engine == "docker"
        assert result.config.timeout == 30

    def test_env_override_applied(self):
        uc = AssembleConfiguration(
            path_resolver=FakePathResolver(),
            parser=FakeParser({"engine": "docker", "timeout": 30}),
            env_reader=FakeEnvReader({"timeout": "60"}),
            validator=FakeValidator(),
            coercer=FakeCoercer(),
        )
        result = uc.execute(
            policy=ResolutionPolicy(env_prefix="APP"),
            rules=[OverrideRule(field_path="timeout", sources={OverrideSource.ENV})],
            schema=FakeAppConfig,
        )
        assert result.config.timeout == 60

    def test_cli_override_applied(self):
        uc = AssembleConfiguration(
            path_resolver=FakePathResolver(),
            parser=FakeParser({"engine": "docker", "timeout": 30}),
            env_reader=FakeEnvReader(),
            validator=FakeValidator(),
            coercer=FakeCoercer(),
        )
        result = uc.execute(
            policy=ResolutionPolicy(env_prefix="APP"),
            rules=[OverrideRule(field_path="engine", sources={OverrideSource.CLI})],
            schema=FakeAppConfig,
            cli_overrides={"engine": "podman"},
        )
        assert result.config.engine == "podman"

    def test_cli_wins_over_env(self):
        uc = AssembleConfiguration(
            path_resolver=FakePathResolver(),
            parser=FakeParser({"engine": "docker", "timeout": 30}),
            env_reader=FakeEnvReader({"timeout": "10"}),
            validator=FakeValidator(),
            coercer=FakeCoercer(),
        )
        result = uc.execute(
            policy=ResolutionPolicy(env_prefix="APP"),
            rules=[
                OverrideRule(field_path="timeout", sources={OverrideSource.ENV, OverrideSource.CLI}),
            ],
            schema=FakeAppConfig,
            cli_overrides={"timeout": "99"},
        )
        assert result.config.timeout == 99

    def test_applied_overrides_tracked(self):
        uc = AssembleConfiguration(
            path_resolver=FakePathResolver(),
            parser=FakeParser({"engine": "docker", "timeout": 30}),
            env_reader=FakeEnvReader({"timeout": "60"}),
            validator=FakeValidator(),
            coercer=FakeCoercer(),
        )
        result = uc.execute(
            policy=ResolutionPolicy(env_prefix="APP"),
            rules=[OverrideRule(field_path="timeout", sources={OverrideSource.ENV})],
            schema=FakeAppConfig,
        )
        assert len(result.applied_overrides) == 1
        ao = result.applied_overrides[0]
        assert ao.field_path == "timeout"
        assert ao.raw_value == "60"
        assert ao.coerced_value == 60
        assert ao.source == OverrideSource.ENV

    def test_explicit_path_passed_to_resolver(self):
        class RecordingResolver:
            def __init__(self):
                self.called_with = None

            def resolve(self, policy, explicit_path=None):
                self.called_with = explicit_path
                return ResolvedPath(path=Path("/custom.yaml"), source=PathSource.CLI_PATH)

        resolver = RecordingResolver()
        uc = AssembleConfiguration(
            path_resolver=resolver,
            parser=FakeParser({"engine": "docker"}),
            env_reader=FakeEnvReader(),
            validator=FakeValidator(),
            coercer=FakeCoercer(),
        )
        uc.execute(
            policy=ResolutionPolicy(env_prefix="APP"),
            rules=[],
            schema=FakeAppConfig,
            explicit_path="/custom.yaml",
        )
        assert resolver.called_with == "/custom.yaml"

    def test_validation_error_on_final_validation(self):
        class StrictValidator(FakeValidator):
            def validate(self, raw, schema):
                raise ConfigValidationError("invalid")

        uc = AssembleConfiguration(
            path_resolver=FakePathResolver(),
            parser=FakeParser({"engine": "docker"}),
            env_reader=FakeEnvReader(),
            validator=StrictValidator(),
            coercer=FakeCoercer(),
        )
        import pytest
        with pytest.raises(ConfigValidationError):
            uc.execute(
                policy=ResolutionPolicy(env_prefix="APP"),
                rules=[],
                schema=FakeAppConfig,
            )

    def test_coercion_error_propagates(self):
        uc = AssembleConfiguration(
            path_resolver=FakePathResolver(),
            parser=FakeParser({"engine": "docker", "timeout": 30}),
            env_reader=FakeEnvReader({"timeout": "not_a_number"}),
            validator=FakeValidator(),
            coercer=FakeCoercer(),
        )
        import pytest
        with pytest.raises(OverrideCoercionError):
            uc.execute(
                policy=ResolutionPolicy(env_prefix="APP"),
                rules=[OverrideRule(field_path="timeout", sources={OverrideSource.ENV})],
                schema=FakeAppConfig,
            )

    def test_path_resolution_error_propagates(self):
        uc = AssembleConfiguration(
            path_resolver=FakePathResolver(),
            parser=FakeParser({}),
            env_reader=FakeEnvReader(),
            validator=FakeValidator(),
            coercer=FakeCoercer(),
        )
        import pytest
        with pytest.raises(PathResolutionError):
            uc.execute(
                policy=ResolutionPolicy(env_prefix="APP"),
                rules=[],
                schema=FakeAppConfig,
                explicit_path="/raise",
            )
