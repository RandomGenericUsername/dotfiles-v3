from __future__ import annotations

from typing import Any

from pydantic import BaseModel, RootModel, field_validator

_VALID_PARAM_TYPES = {"float", "int", "str"}


class BackendParameterSchema(BaseModel):
    key: str
    param_type: str
    default: Any = None
    choices: list[str] | None = None
    description: str = ""
    required: bool = False

    @field_validator("param_type")
    @classmethod
    def _validate_param_type(cls, v: str) -> str:
        if v not in _VALID_PARAM_TYPES:
            raise ValueError(
                f"Invalid param_type '{v}' — must be one of: "
                f"{', '.join(sorted(_VALID_PARAM_TYPES))}"
            )
        return v


class BackendDefinitionSchema(BaseModel):
    description: str = ""
    parameters: list[BackendParameterSchema] = []
    display_name: str = ""
    min_version: str = "0.0.0"


class BackendsCatalogSchema(RootModel[dict[str, BackendDefinitionSchema]]):
    pass
