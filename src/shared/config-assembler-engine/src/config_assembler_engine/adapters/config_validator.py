from typing import Any, get_args, get_origin

from pydantic import BaseModel, ValidationError

from config_assembler_engine.domain.type_utils import unwrap_optional
from config_assembler_engine.errors import ConfigValidationError
from config_assembler_engine.ports.config_validator import ConfigValidatorPort


class PydanticValidator(ConfigValidatorPort):
    def validate(self, raw: dict[str, Any], schema: type[BaseModel]) -> BaseModel:
        try:
            return schema.model_validate(raw)
        except ValidationError as e:
            raise ConfigValidationError(str(e), errors=e.errors()) from e

    def get_field_info(self, schema: type[BaseModel], field_path: str) -> Any:
        parts = field_path.split(".")
        current_type = schema

        for i, part in enumerate(parts):
            current_type = unwrap_optional(current_type)

            if isinstance(current_type, type) and issubclass(current_type, BaseModel):
                if part not in current_type.model_fields:
                    path_so_far = ".".join(parts[: i + 1])
                    raise ConfigValidationError(
                        f"Field '{path_so_far}' not found in schema {current_type.__name__}"
                    )
                field_info = current_type.model_fields[part]
                current_type = field_info.annotation
                continue

            origin = get_origin(current_type)
            args = get_args(current_type)

            if origin is dict:
                if len(args) > 1:
                    current_type = args[1]
                else:
                    current_type = Any
                continue

            if origin is list:
                list_field = ".".join(parts[: i + 1])
                raise ConfigValidationError(
                    f"Cannot navigate into '{list_field}': '{parts[i - 1]}' is a list. "
                    f"Element-wise overrides for list fields are not supported. "
                    f"Override the entire list field instead "
                    f"(e.g. <prefix>__{parts[i - 1].upper()}=val1,val2)."
                )

            if i < len(parts) - 1:
                path_so_far = ".".join(parts[: i + 1])
                raise ConfigValidationError(
                    f"Cannot navigate beyond '{path_so_far}': "
                    f"type {current_type} is not a BaseModel, Dict, or list"
                )

        return unwrap_optional(current_type)
