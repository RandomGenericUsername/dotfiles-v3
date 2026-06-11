from typing import Any


class ConfigAssemblerError(Exception):
    pass


class PathResolutionError(ConfigAssemblerError):
    pass


class ConfigParseError(ConfigAssemblerError):
    pass


class ConfigValidationError(ConfigAssemblerError):
    def __init__(
        self,
        message: str,
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.errors = errors
        self.applied_overrides: list[Any] | None = None


class OverrideCoercionError(ConfigAssemblerError):
    def __init__(
        self,
        field_path: str,
        raw_value: str,
        target_type: str,
        reason: str,
    ) -> None:
        self.field_path = field_path
        self.raw_value = raw_value
        self.target_type = target_type
        self.reason = reason
        super().__init__(
            f"Cannot coerce override '{field_path}'={raw_value} to {target_type}: {reason}"
        )
