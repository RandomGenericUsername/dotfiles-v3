from enum import Enum
from pathlib import Path
from typing import Any, Optional

import pytest

from config_assembler_engine.adapters.type_coercer import PydanticTypeCoercer
from config_assembler_engine.domain.models import OverrideSource, OverrideValue
from config_assembler_engine.errors import OverrideCoercionError


class Color(Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


def make_ov(raw: str) -> OverrideValue:
    return OverrideValue(field_path="x", raw_value=raw, source=OverrideSource.ENV)


class TestPydanticTypeCoercer:
    def test_coerce_str(self):
        c = PydanticTypeCoercer()
        result = c.coerce(make_ov("hello"), str)
        assert result == "hello"

    def test_coerce_int(self):
        c = PydanticTypeCoercer()
        result = c.coerce(make_ov("42"), int)
        assert result == 42

    def test_coerce_int_raises_on_bad(self):
        c = PydanticTypeCoercer()
        with pytest.raises(OverrideCoercionError) as exc:
            c.coerce(make_ov("abc"), int)
        assert exc.value.target_type == "int"

    def test_coerce_float(self):
        c = PydanticTypeCoercer()
        result = c.coerce(make_ov("3.14"), float)
        assert result == 3.14

    def test_coerce_float_raises_on_bad(self):
        c = PydanticTypeCoercer()
        with pytest.raises(OverrideCoercionError):
            c.coerce(make_ov("not_a_float"), float)

    def test_coerce_bool_true_values(self):
        c = PydanticTypeCoercer()
        assert c.coerce(make_ov("true"), bool) is True
        assert c.coerce(make_ov("True"), bool) is True
        assert c.coerce(make_ov("1"), bool) is True
        assert c.coerce(make_ov("yes"), bool) is True
        assert c.coerce(make_ov("on"), bool) is True

    def test_coerce_bool_false_values(self):
        c = PydanticTypeCoercer()
        assert c.coerce(make_ov("false"), bool) is False
        assert c.coerce(make_ov("0"), bool) is False
        assert c.coerce(make_ov("no"), bool) is False
        assert c.coerce(make_ov("off"), bool) is False

    def test_coerce_bool_unknown_returns_false(self):
        c = PydanticTypeCoercer()
        assert c.coerce(make_ov("ture"), bool) is False

    def test_coerce_path(self):
        c = PydanticTypeCoercer()
        result = c.coerce(make_ov("/tmp/foo"), Path)
        assert result == Path("/tmp/foo")

    def test_coerce_list_str(self):
        c = PydanticTypeCoercer()
        result = c.coerce(make_ov("a,b,c"), list[str])
        assert result == ["a", "b", "c"]

    def test_coerce_list_int(self):
        c = PydanticTypeCoercer()
        result = c.coerce(make_ov("1,2,3"), list[int])
        assert result == [1, 2, 3]

    def test_coerce_empty_list(self):
        c = PydanticTypeCoercer()
        result = c.coerce(make_ov(""), list[str])
        assert result == []

    def test_coerce_dict_str_int(self):
        c = PydanticTypeCoercer()
        result = c.coerce(make_ov("a:1;b:2"), dict[str, int])
        assert result == {"a": 1, "b": 2}

    def test_coerce_empty_dict(self):
        c = PydanticTypeCoercer()
        result = c.coerce(make_ov(""), dict[str, str])
        assert result == {}

    def test_coerce_dict_malformed_entry(self):
        c = PydanticTypeCoercer()
        with pytest.raises(OverrideCoercionError):
            c.coerce(make_ov("a:1;bad"), dict[str, int])

    def test_coerce_enum_by_name(self):
        c = PydanticTypeCoercer()
        result = c.coerce(make_ov("RED"), Color)
        assert result is Color.RED

    def test_coerce_enum_case_insensitive(self):
        c = PydanticTypeCoercer()
        result = c.coerce(make_ov("green"), Color)
        assert result is Color.GREEN

    def test_coerce_enum_invalid_raises(self):
        c = PydanticTypeCoercer()
        with pytest.raises(OverrideCoercionError):
            c.coerce(make_ov("YELLOW"), Color)

    def test_coerce_optional_unwraps(self):
        c = PydanticTypeCoercer()
        result = c.coerce(make_ov("42"), Optional[int])
        assert result == 42

    def test_override_coercion_error_carries_context(self):
        c = PydanticTypeCoercer()
        ov = OverrideValue(field_path="timeout", raw_value="abc", source=OverrideSource.ENV)
        with pytest.raises(OverrideCoercionError) as exc:
            c.coerce(ov, int)
        assert exc.value.field_path == "timeout"
        assert exc.value.raw_value == "abc"
