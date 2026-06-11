from enum import Enum
from typing import Any, Optional

import pytest
from pydantic import BaseModel, Field

from config_assembler_engine.adapters.config_validator import PydanticValidator
from config_assembler_engine.errors import ConfigValidationError


class NestedModel(BaseModel):
    host: str = "localhost"
    port: int = 8080


class AppConfig(BaseModel):
    engine: str = "docker"
    timeout: int = 30
    mounts: list[str] = []
    nested: NestedModel = NestedModel()
    optional_field: Optional[int] = None


class TestPydanticValidatorValidate:
    def test_valid_data(self):
        validator = PydanticValidator()
        result = validator.validate({"engine": "podman", "timeout": 60}, AppConfig)
        assert isinstance(result, AppConfig)
        assert result.engine == "podman"
        assert result.timeout == 60

    def test_uses_defaults(self):
        validator = PydanticValidator()
        result = validator.validate({}, AppConfig)
        assert result.engine == "docker"
        assert result.timeout == 30

    def test_raises_on_invalid(self):
        validator = PydanticValidator()
        with pytest.raises(ConfigValidationError) as exc:
            validator.validate({"timeout": "not_a_number"}, AppConfig)
        assert exc.value.errors is not None
        assert len(exc.value.errors) > 0

    def test_validation_error_no_errors_field(self):
        validator = PydanticValidator()
        with pytest.raises(ConfigValidationError) as exc:
            validator.validate({"timeout": "bad"}, AppConfig)
        assert exc.value.errors is not None


class TestPydanticValidatorGetFieldInfo:
    def test_simple_field(self):
        validator = PydanticValidator()
        result = validator.get_field_info(AppConfig, "engine")
        assert result is str

    def test_int_field(self):
        validator = PydanticValidator()
        result = validator.get_field_info(AppConfig, "timeout")
        assert result is int

    def test_nested_field(self):
        validator = PydanticValidator()
        result = validator.get_field_info(AppConfig, "nested.host")
        assert result is str

    def test_nested_int_field(self):
        validator = PydanticValidator()
        result = validator.get_field_info(AppConfig, "nested.port")
        assert result is int

    def test_optional_field_unwrapped(self):
        validator = PydanticValidator()
        result = validator.get_field_info(AppConfig, "optional_field")
        assert result is int

    def test_list_field_raises_on_navigation(self):
        validator = PydanticValidator()
        with pytest.raises(ConfigValidationError) as exc:
            validator.get_field_info(AppConfig, "mounts.0")
        assert "list" in str(exc.value).lower()

    def test_nonexistent_field_raises(self):
        validator = PydanticValidator()
        with pytest.raises(ConfigValidationError) as exc:
            validator.get_field_info(AppConfig, "does_not_exist")
        assert "not found" in str(exc.value).lower()
