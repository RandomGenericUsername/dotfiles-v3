from __future__ import annotations

import colorsys
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from color_scheme_generator.domain.enums import Backend, ColorFormat

_HEX_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}\Z")


@dataclass(frozen=True)
class Color:
    hex: str
    rgb: tuple[int, int, int]

    def __post_init__(self) -> None:
        if not _HEX_PATTERN.match(self.hex):
            raise ValueError(f"Invalid hex color: {self.hex}")
        if len(self.rgb) != 3:
            raise ValueError(f"rgb must be a 3-tuple, got {len(self.rgb)} values")
        clamped = tuple(int(round(max(0, min(255, v)))) for v in self.rgb)
        if clamped != self.rgb:
            object.__setattr__(self, "rgb", clamped)
            object.__setattr__(self, "hex", f"#{clamped[0]:02x}{clamped[1]:02x}{clamped[2]:02x}")

    def adjust_saturation(self, factor: float) -> Color:
        r, g, b = self.rgb
        h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
        s = max(0.0, min(1.0, s * factor))
        r2, g2, b2 = colorsys.hls_to_rgb(h, l, s)
        nr, ng, nb = round(r2 * 255), round(g2 * 255), round(b2 * 255)
        return Color(f"#{nr:02x}{ng:02x}{nb:02x}", (nr, ng, nb))


@dataclass(frozen=True)
class ColorScheme:
    background: Color
    foreground: Color
    cursor: Color
    colors: tuple[Color, Color, Color, Color, Color, Color, Color, Color, Color, Color, Color, Color, Color, Color, Color, Color]
    source_image: Path
    backend: Backend
    generated_at: datetime

    def __post_init__(self) -> None:
        if len(self.colors) != 16:
            raise ValueError(f"ColorScheme requires exactly 16 colors, got {len(self.colors)}")


@dataclass(frozen=True)
class GeneratorConfig:
    backend: Backend
    params: dict[str, Any]
    formats: tuple[ColorFormat, ...]
    output_dir: Path


@dataclass(frozen=True)
class GenerationRequest:
    image_path: Path
    config: GeneratorConfig


@dataclass(frozen=True)
class GenerationResult:
    success: bool
    color_scheme: ColorScheme | None
    output_files: tuple[Path, ...]
    backend: Backend
    stderr: str
    return_code: int
    duration: float


class AppSettings:
    """Placeholder — will be defined as a frozen dataclass in Story 2.1."""
