from __future__ import annotations

import json
import logging
import math
import shutil
import subprocess
import time
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any

from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import (
    BackendNotAvailableError,
    ColorExtractionError,
)
from color_scheme_generator.domain.models import Color, ColorScheme, GeneratorConfig
from color_scheme_generator.domain.services import (
    ColorAdjustmentService,
    PaletteNormalizationService,
)

_SUBPROCESS_TIMEOUT = 60
_CACHE_RETRY_DELAY = 0.5

logger = logging.getLogger(__name__)


@cache
def _get_cache_file() -> Path:
    return Path.home() / ".cache" / "wallust" / "colors.json"


class WallustGenerator:
    def is_available(self) -> bool:
        return shutil.which("wallust") is not None

    def generate(self, image_path: Path, config: GeneratorConfig) -> ColorScheme:
        if not self.is_available():
            raise BackendNotAvailableError(
                Backend.WALLUST, "Install wallust binary"
            )

        params = config.params or {}
        algorithm = params.get("algorithm", "kmeans")
        timeout = params.get("timeout", _SUBPROCESS_TIMEOUT)
        saturation = params.get("saturation", 1.0)

        if (
            not isinstance(timeout, (int, float))
            or math.isnan(timeout)
            or math.isinf(timeout)
            or timeout < 1
        ):
            timeout = _SUBPROCESS_TIMEOUT

        cmd = [
            "wallust",
            "run", str(image_path),
            "--backend", str(algorithm),
            "-s", "-T", "-q",
            "--print-scheme",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise ColorExtractionError(
                Backend.WALLUST,
                f"subprocess timed out after {timeout}s",
            ) from None
        except (FileNotFoundError, OSError) as e:
            raise ColorExtractionError(
                Backend.WALLUST,
                f"Failed to execute wallust: {e}",
            ) from None

        if result.returncode != 0:
            raise ColorExtractionError(
                Backend.WALLUST,
                f"wallust exited with code {result.returncode}",
                stderr=result.stderr.decode("utf-8", errors="replace"),
            )

        saturation = self._validate_saturation(saturation)
        special: dict[str, str] = {}

        if result.stdout and result.stdout.strip():
            colors = self._parse_stdout(result.stdout)
            if not colors:
                colors, special = self._parse_cache_file()
        else:
            colors, special = self._parse_cache_file()

        colors = [
            ColorAdjustmentService.adjust_saturation(c, saturation)
            for c in colors
        ]

        colors = sorted(colors, key=lambda c: sum(c.rgb))

        if special:
            bg_hex = special.get("background")
            fg_hex = special.get("foreground")
            cursor_hex = special.get("cursor")
            background = ColorAdjustmentService.adjust_saturation(
                self._hex_to_color(bg_hex), saturation
            ) if bg_hex else colors[0]
            foreground = ColorAdjustmentService.adjust_saturation(
                self._hex_to_color(fg_hex), saturation
            ) if fg_hex else colors[-1]
            cursor = ColorAdjustmentService.adjust_saturation(
                self._hex_to_color(cursor_hex), saturation
            ) if cursor_hex else max(colors, key=lambda c: max(c.rgb) - min(c.rgb))
        else:
            background = colors[0] if colors else Color("#000000", (0, 0, 0))
            foreground = colors[-1] if colors else Color("#000000", (0, 0, 0))
            cursor = (
                max(colors, key=lambda c: max(c.rgb) - min(c.rgb))
                if colors else Color("#000000", (0, 0, 0))
            )

        return ColorScheme(
            background=background,
            foreground=foreground,
            cursor=cursor,
            colors=PaletteNormalizationService.normalize(colors),
            source_image=image_path,
            backend=Backend.WALLUST,
            generated_at=datetime.now(),
        )

    @staticmethod
    def _validate_saturation(saturation: object) -> float:
        if (
            not isinstance(saturation, (int, float))
            or math.isnan(saturation)
            or math.isinf(saturation)
        ):
            return 1.0
        return max(0.0, min(1.0, float(saturation)))

    @staticmethod
    def _hex_to_color(hex_str: str) -> Color:
        if not hex_str.startswith("#"):
            hex_str = f"#{hex_str}"
        if len(hex_str) == 4:
            hex_str = f"#{hex_str[1]*2}{hex_str[2]*2}{hex_str[3]*2}"
        if len(hex_str) == 7:
            try:
                r = int(hex_str[1:3], 16)
                g = int(hex_str[3:5], 16)
                b = int(hex_str[5:7], 16)
                return Color(hex_str, (r, g, b))
            except ValueError:
                pass
        logger.warning("Failed to parse hex color '%s', falling back to black", hex_str)
        return Color("#000000", (0, 0, 0))

    @staticmethod
    def _parse_stdout(stdout: bytes) -> list[Color]:
        raw = stdout.decode("utf-8", errors="replace").strip()
        colors: list[Color] = []
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("#") and len(line) == 7:
                try:
                    r, g, b = int(line[1:3], 16), int(line[3:5], 16), int(line[5:7], 16)
                    colors.append(Color(line, (r, g, b)))
                except ValueError:
                    continue
        return colors

    @staticmethod
    def _parse_cache_file() -> tuple[list[Color], dict[str, Any]]:
        data = WallustGenerator._read_cache_with_retry()
        if not isinstance(data, dict):
            raise ColorExtractionError(
                Backend.WALLUST,
                f"Cache file is not a JSON object: {type(data).__name__}",
            )

        raw_colors = data.get("colors", {})
        if not isinstance(raw_colors, dict):
            raw_colors = {}

        colors: list[Color] = []
        for i in range(16):
            key = f"color{i}"
            hex_val = raw_colors.get(key, "#000000")
            colors.append(WallustGenerator._hex_to_color(hex_val))

        special = data.get("special", {})
        if not isinstance(special, dict):
            special = {}
        return colors, special

    @staticmethod
    def _read_cache_with_retry() -> dict:
        for attempt in range(2):
            try:
                with open(_get_cache_file()) as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                if attempt == 0:
                    time.sleep(_CACHE_RETRY_DELAY)
                else:
                    raise ColorExtractionError(
                        Backend.WALLUST,
                        f"Failed to read cache file after retry: {_get_cache_file()}",
                    ) from None
