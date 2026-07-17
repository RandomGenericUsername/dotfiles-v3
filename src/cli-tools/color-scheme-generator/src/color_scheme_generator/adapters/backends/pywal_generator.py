from __future__ import annotations

import json
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import (
    BackendNotAvailableError,
    ColorExtractionError,
)
from color_scheme_generator.domain.models import Color, ColorScheme, GeneratorConfig
from color_scheme_generator.domain.services import ColorAdjustmentService

_SUBPROCESS_TIMEOUT = 60
_CACHE_FILE = Path.home() / ".cache" / "wal" / "colors.json"
_CACHE_RETRY_DELAY = 0.1


class PywalGenerator:
    def is_available(self) -> bool:
        return shutil.which("wal") is not None

    def generate(self, image_path: Path, config: GeneratorConfig) -> ColorScheme:
        if not self.is_available():
            raise BackendNotAvailableError(
                Backend.PYWAL, "pip install color-scheme-generator[pywal]"
            )

        params = config.params or {}
        algorithm = params.get("algorithm", "wal")
        timeout = params.get("timeout", _SUBPROCESS_TIMEOUT)
        saturation = params.get("saturation", 1.0)

        cmd = [
            "wal",
            "-i", str(image_path),
            "-n", "-s", "-t", "-e",
            "--backend", str(algorithm),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise ColorExtractionError(
                Backend.PYWAL,
                f"subprocess timed out after {timeout}s",
            ) from None

        if result.returncode != 0:
            raise ColorExtractionError(
                Backend.PYWAL,
                f"wal exited with code {result.returncode}",
                stderr=result.stderr.decode("utf-8", errors="replace"),
            )

        if result.stdout and result.stdout.strip():
            colors = self._parse_stdout(result.stdout)
        else:
            colors = self._parse_cache_file()

        colors = sorted(colors, key=lambda c: sum(c.rgb))
        saturation = max(0.0, min(1.0, float(saturation)))
        colors = [
            ColorAdjustmentService.adjust_saturation(c, saturation)
            for c in colors
        ]

        background = colors[0]
        foreground = colors[-1]
        cursor = max(colors, key=lambda c: max(c.rgb) - min(c.rgb))

        return ColorScheme(
            background=background,
            foreground=foreground,
            cursor=cursor,
            colors=tuple(colors),
            source_image=image_path,
            backend=Backend.PYWAL,
            generated_at=datetime.now(),
        )

    def _parse_stdout(self, stdout: bytes) -> list[Color]:
        raw = stdout.decode("utf-8", errors="replace").strip()
        colors: list[Color] = []
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("#") and len(line) == 7:
                r, g, b = int(line[1:3], 16), int(line[3:5], 16), int(line[5:7], 16)
                colors.append(Color(line, (r, g, b)))
        return colors

    def _parse_cache_file(self) -> list[Color]:
        data = self._read_cache_with_retry()
        raw_colors = data.get("colors", {})

        colors: list[Color] = []
        for i in range(16):
            key = f"color{i}"
            hex_val = raw_colors.get(key, "#000000")
            if not hex_val.startswith("#"):
                hex_val = f"#{hex_val}"
            if len(hex_val) == 4:
                hex_val = f"#{hex_val[1]*2}{hex_val[2]*2}{hex_val[3]*2}"
            r, g, b = int(hex_val[1:3], 16), int(hex_val[3:5], 16), int(hex_val[5:7], 16)
            colors.append(Color(hex_val, (r, g, b)))
        return colors

    def _read_cache_with_retry(self) -> dict:
        for attempt in range(2):
            try:
                with open(_CACHE_FILE) as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                if attempt == 0:
                    time.sleep(_CACHE_RETRY_DELAY)
                else:
                    raise ColorExtractionError(
                        Backend.PYWAL,
                        f"Failed to read cache file after retry: {_CACHE_FILE}",
                    ) from None
        return {}
