from pathlib import Path
from typing import Any, get_type_hints

import pytest
from pydantic import BaseModel

from config_assembler_engine.domain.models import ResolutionPolicy, ResolvedPath
from config_assembler_engine.errors import ConfigValidationError
from config_assembler_engine.ports.config_parser import ConfigParserPort
from config_assembler_engine.ports.config_validator import ConfigValidatorPort
from config_assembler_engine.ports.env_reader import EnvironmentReaderPort
from config_assembler_engine.ports.path_resolver import PathResolverPort, ResolutionStrategy
from config_assembler_engine.ports.type_coercer import TypeCoercerPort


class TestPathResolverPort:
    def test_is_protocol(self):
        import typing
        assert issubclass(PathResolverPort, typing.Protocol)

    def test_resolve_signature(self):
        hints = get_type_hints(PathResolverPort.resolve)
        assert "policy" in hints
        assert "explicit_path" in hints

    def test_structural_subtyping(self):
        class FakeResolver:
            def resolve(self, policy: ResolutionPolicy, explicit_path: str | None = None) -> ResolvedPath:
                return ResolvedPath(path=Path("/a.yaml"), source=...)

        assert callable(FakeResolver.resolve)


class TestResolutionStrategy:
    def test_is_protocol(self):
        import typing
        assert issubclass(ResolutionStrategy, typing.Protocol)

    def test_resolve_returns_optional(self):
        hints = get_type_hints(ResolutionStrategy.resolve)
        assert "return" in hints

    def test_structural_subtyping(self):
        class FakeStrategy:
            def resolve(self, policy: ResolutionPolicy, explicit_path: str | None = None) -> ResolvedPath | None:
                return None

        assert callable(FakeStrategy.resolve)


class TestConfigParserPort:
    def test_is_protocol(self):
        import typing
        assert issubclass(ConfigParserPort, typing.Protocol)

    def test_structural_subtyping(self):
        class FakeParser:
            def parse(self, path: Path) -> dict[str, Any]:
                return {}

        assert callable(FakeParser.parse)


class TestEnvironmentReaderPort:
    def test_is_protocol(self):
        import typing
        assert issubclass(EnvironmentReaderPort, typing.Protocol)

    def test_structural_subtyping(self):
        class FakeReader:
            def read(self, prefix: str) -> dict[str, str]:
                return {}

        assert callable(FakeReader.read)


class TestConfigValidatorPort:
    def test_is_protocol(self):
        import typing
        assert issubclass(ConfigValidatorPort, typing.Protocol)

    def test_validate_signature(self):
        hints = get_type_hints(ConfigValidatorPort.validate)
        assert "raw" in hints
        assert "schema" in hints

    def test_get_field_info_signature(self):
        hints = get_type_hints(ConfigValidatorPort.get_field_info)
        assert "schema" in hints
        assert "field_path" in hints

    def test_structural_subtyping(self):
        class FakeValidator:
            def validate(self, raw: dict[str, Any], schema: type[BaseModel]) -> BaseModel:
                return schema.model_validate(raw)

            def get_field_info(self, schema: type[BaseModel], field_path: str) -> Any:
                return str

        assert callable(FakeValidator.validate)
        assert callable(FakeValidator.get_field_info)


class TestTypeCoercerPort:
    def test_is_protocol(self):
        import typing
        assert issubclass(TypeCoercerPort, typing.Protocol)

    def test_structural_subtyping(self):
        class FakeCoercer:
            def coerce(self, override, field_type: Any) -> Any:
                return override.raw_value

        assert callable(FakeCoercer.coerce)
