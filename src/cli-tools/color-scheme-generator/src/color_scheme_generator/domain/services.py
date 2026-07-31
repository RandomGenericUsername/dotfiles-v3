from __future__ import annotations

import re
from pathlib import Path
from typing import Any, ClassVar

from color_scheme_generator.domain.enums import ColorFormat
from color_scheme_generator.domain.exceptions import ConfigResolutionError, TemplatesValidationError
from color_scheme_generator.domain.models import (
    _HEX_PATTERN,
    _UNSET,
    BackendParameterDefinition,
    Color,
    ColorSchemeTemplate,
    TemplateCatalog,
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


class TemplateCatalogService:
    _PREFIX = "colors."
    _SUFFIX = ".j2"
    _FORMATS = {f.value for f in ColorFormat}

    def derive(self, dir_path: Path) -> TemplateCatalog:
        if not dir_path.is_dir():
            raise ConfigResolutionError("templates_dir", f"Not a directory: {dir_path}")

        entries: list[ColorSchemeTemplate] = []
        unknown: list[tuple[str, str]] = []

        for f in sorted(dir_path.iterdir()):
            if f.suffix != self._SUFFIX or not f.is_file():
                continue
            stem = f.name[: -len(self._SUFFIX)]
            fmt_key = stem[len(self._PREFIX):] if stem.startswith(self._PREFIX) else stem

            try:
                fmt = ColorFormat(fmt_key)
            except ValueError:
                unknown.append((f.name, fmt_key))
                continue
            entries.append(ColorSchemeTemplate(name=f.name, format=fmt))

        if unknown:
            names = ", ".join(n for n, _ in unknown)
            raise TemplatesValidationError(
                f"Unknown template format(s) — not in ColorFormat enum: {names}"
            )
        return TemplateCatalog(templates=tuple(entries), source_dir=dir_path)
