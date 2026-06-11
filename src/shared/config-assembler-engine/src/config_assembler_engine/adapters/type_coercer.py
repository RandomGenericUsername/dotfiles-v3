import json
from pathlib import Path
from typing import Any, get_args, get_origin

from config_assembler_engine.domain.models import OverrideSource, OverrideValue
from config_assembler_engine.domain.type_utils import unwrap_optional
from config_assembler_engine.errors import OverrideCoercionError
from config_assembler_engine.ports.type_coercer import TypeCoercerPort


class PydanticTypeCoercer(TypeCoercerPort):
    def coerce(self, override: OverrideValue, field_type: Any) -> Any:
        raw = override.raw_value

        field_type = unwrap_optional(field_type)

        origin = get_origin(field_type)
        args = get_args(field_type)

        if field_type is str or (isinstance(field_type, type) and issubclass(field_type, str)):
            return raw

        if field_type is bool:
            return raw.lower() in ("true", "1", "yes", "on")

        if field_type is int or (isinstance(field_type, type) and issubclass(field_type, int)):
            try:
                return int(raw)
            except ValueError:
                raise OverrideCoercionError(override.field_path, raw, "int", "not a valid integer")

        if field_type is float or (isinstance(field_type, type) and issubclass(field_type, float)):
            try:
                return float(raw)
            except ValueError:
                raise OverrideCoercionError(override.field_path, raw, "float", "not a valid float")

        if isinstance(field_type, type) and issubclass(field_type, Path):
            return Path(raw)

        if origin is list or (isinstance(field_type, type) and issubclass(field_type, list)):
            if not raw:
                return []
            item_type = args[0] if args else str
            items = [item.strip() for item in raw.split(",")]
            return [self._coerce_item(item, item_type) for item in items]

        if origin is dict or (isinstance(field_type, type) and issubclass(field_type, dict)):
            if not raw:
                return {}
            key_type = args[0] if len(args) > 0 else str
            val_type = args[1] if len(args) > 1 else str
            result: dict[Any, Any] = {}
            entries = raw.split(";")
            for entry in entries:
                if ":" not in entry:
                    raise OverrideCoercionError(
                        override.field_path, raw, "dict",
                        f"malformed entry '{entry}' — expected 'key:value'"
                    )
                k, v = entry.split(":", 1)
                result[self._coerce_item(k.strip(), key_type)] = self._coerce_item(v.strip(), val_type)
            return result

        if hasattr(field_type, "__members__"):
            try:
                return field_type[raw]
            except KeyError:
                for member in field_type:
                    if member.name.lower() == raw.lower():
                        return member
                raise OverrideCoercionError(override.field_path, raw, "enum", "not a valid member")

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        return raw

    def _coerce_item(self, raw: str, item_type: Any) -> Any:
        return self.coerce(
            OverrideValue(field_path="", raw_value=raw, source=OverrideSource.ENV),
            item_type,
        )
