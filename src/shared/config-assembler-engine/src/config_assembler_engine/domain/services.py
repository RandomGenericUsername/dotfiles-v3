from copy import deepcopy
from typing import Any, ClassVar

from config_assembler_engine.domain.models import (
    OverrideRule,
    OverrideSource,
    OverrideValue,
)


class OverrideMatchingService:
    ENV_SEPARATOR: ClassVar[str] = "__"

    @staticmethod
    def match(
        env_vars: dict[str, str],
        cli_overrides: dict[str, str],
        rules: list[OverrideRule],
    ) -> list[OverrideValue]:
        values: list[OverrideValue] = []
        registered_paths = {r.field_path for r in rules}

        for raw_key, raw_val in env_vars.items():
            dotted = raw_key.replace(OverrideMatchingService.ENV_SEPARATOR, ".")
            if dotted in registered_paths:
                rule = next(r for r in rules if r.field_path == dotted)
                if OverrideSource.ENV in rule.sources:
                    values.append(
                        OverrideValue(
                            field_path=dotted,
                            raw_value=raw_val,
                            source=OverrideSource.ENV,
                        )
                    )

        for key, raw_val in cli_overrides.items():
            if key in registered_paths:
                rule = next(r for r in rules if r.field_path == key)
                if OverrideSource.CLI in rule.sources:
                    values.append(
                        OverrideValue(
                            field_path=key,
                            raw_value=raw_val,
                            source=OverrideSource.CLI,
                        )
                    )

        return values


class ConfigMergeService:
    @staticmethod
    def apply(base: dict[str, Any], override: OverrideValue, coerced_value: Any) -> dict[str, Any]:
        result = deepcopy(base)
        parts = override.field_path.split(".")
        current = result

        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            elif not isinstance(current[part], dict):
                raise TypeError(
                    f"Cannot set '{override.field_path}': "
                    f"'{part}' is {type(current[part]).__name__}, not a dict"
                )
            current = current[part]

        current[parts[-1]] = coerced_value
        return result
