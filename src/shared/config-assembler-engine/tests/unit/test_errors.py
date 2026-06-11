from typing import Any

from config_assembler_engine.errors import (
    ConfigAssemblerError,
    ConfigParseError,
    ConfigValidationError,
    OverrideCoercionError,
    PathResolutionError,
)


class TestConfigAssemblerError:
    def test_is_exception(self):
        assert issubclass(ConfigAssemblerError, Exception)

    def test_can_raise_and_catch_base(self):
        try:
            raise PathResolutionError("not found")
        except ConfigAssemblerError:
            pass


class TestPathResolutionError:
    def test_message(self):
        err = PathResolutionError("No config file found")
        assert str(err) == "No config file found"


class TestConfigParseError:
    def test_message(self):
        err = ConfigParseError("Failed to parse TOML /x.yaml: syntax error")
        assert "Failed to parse TOML" in str(err)


class TestConfigValidationError:
    def test_base_fields_default_none(self):
        err = ConfigValidationError("validation failed")
        assert err.errors is None
        assert err.applied_overrides is None

    def test_errors_field(self):
        err = ConfigValidationError("bad", errors=[{"type": "value_error", "loc": ("x",), "msg": "x is bad"}])
        assert err.errors is not None
        assert len(err.errors) == 1
        assert err.errors[0]["type"] == "value_error"

    def test_applied_overrides_field(self):
        err = ConfigValidationError("bad")
        err.applied_overrides = []
        assert err.applied_overrides == []


class TestOverrideCoercionError:
    def test_carries_context(self):
        err = OverrideCoercionError(
            field_path="timeout",
            raw_value="abc",
            target_type="int",
            reason="not a valid integer",
        )
        assert err.field_path == "timeout"
        assert err.raw_value == "abc"
        assert err.target_type == "int"
        assert err.reason == "not a valid integer"

    def test_default_message_format(self):
        err = OverrideCoercionError(
            field_path="timeout",
            raw_value="abc",
            target_type="int",
            reason="not a valid integer",
        )
        msg = str(err)
        assert "timeout" in msg
        assert "abc" in msg
        assert "int" in msg

    def test_override_value_constructor(self):
        err = OverrideCoercionError("timeout", "abc", "int", "not a valid integer")
        assert err.field_path == "timeout"
