from __future__ import annotations

import re
from typing import Any, ClassVar

from color_scheme_generator.domain.exceptions import ConfigResolutionError
from color_scheme_generator.domain.models import (
    _HEX_PATTERN,
    _UNSET,
    BackendParameterDefinition,
    Color,
)


class HexValidationService:
    _pattern: ClassVar[re.Pattern[str]] = _HEX_PATTERN

    @staticmethod
    def canonicalize(hex_str: str) -> str:
        return hex_str

    @staticmethod
    def validate(hex_str: str) -> bool:
        return bool(HexValidationService._pattern.match(hex_str))


class ColorAdjustmentService:
    @staticmethod
    def adjust_saturation(color: Color, factor: float) -> Color:
        return color.adjust_saturation(factor)


class PaletteNormalizationService:
    @staticmethod
    def normalize(colors: list[Color]) -> tuple[Color, ...]:
        if len(colors) > 16:
            return tuple(colors[:16])
        if len(colors) < 16:
            pad_color = colors[-1] if colors else Color("#000000", (0, 0, 0))
            return tuple(colors + [pad_color] * (16 - len(colors)))
        return tuple(colors)

    @staticmethod
    def sort_by_brightness(colors: list[Color]) -> list[Color]:
        return sorted(colors, key=lambda c: sum(c.rgb))


class ParameterResolutionService:
    @staticmethod
    def resolve_all(
        parameters: tuple[BackendParameterDefinition, ...],
        overrides: dict[str, Any],
    ) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        for param in parameters:
            if param.name in overrides:
                resolved[param.name] = overrides[param.name]
            elif param.default is not _UNSET:
                resolved[param.name] = param.default
            elif not param.required:
                resolved[param.name] = None
            else:
                raise ConfigResolutionError(
                    key=param.name,
                    reason=f"Required parameter '{param.name}' has no default and no override was provided",
                )
        return resolved
