from typing import Any, Protocol

from pydantic import BaseModel


class ConfigValidatorPort(Protocol):
    def validate(self, raw: dict[str, Any], schema: type[BaseModel]) -> BaseModel: ...

    def get_field_info(self, schema: type[BaseModel], field_path: str) -> Any: ...
