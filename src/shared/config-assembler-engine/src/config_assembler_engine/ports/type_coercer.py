from typing import Any, Protocol


class TypeCoercerPort(Protocol):
    def coerce(self, override, field_type: Any) -> Any:
        ...
