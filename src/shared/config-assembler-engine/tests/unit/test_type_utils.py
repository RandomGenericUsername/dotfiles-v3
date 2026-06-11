from typing import Annotated, Any, Optional, Union

from config_assembler_engine.domain.type_utils import unwrap_optional


class TestUnwrapOptional:
    def test_plain_type_unchanged(self):
        assert unwrap_optional(str) is str

    def test_optional_int(self):
        result = unwrap_optional(Optional[int])
        assert result is int

    def test_optional_str(self):
        result = unwrap_optional(Optional[str])
        assert result is str

    def test_nested_optional(self):
        result = unwrap_optional(Optional[Optional[int]])
        assert result is int

    def test_annotated_int(self):
        from typing import Annotated
        result = unwrap_optional(Annotated[int, "some constraint"])
        assert result is int

    def test_optional_annotated(self):
        result = unwrap_optional(Optional[Annotated[int, "ge=0"]])
        assert result is int

    def test_union_not_optional(self):
        result = unwrap_optional(Union[str, int])
        assert result == Union[str, int]

    def test_none_input(self):
        assert unwrap_optional(None) is None

    def test_list_type_unchanged(self):
        result = unwrap_optional(list[str])
        assert result == list[str]

    def test_optional_list(self):
        result = unwrap_optional(Optional[list[str]])
        assert result == list[str]
