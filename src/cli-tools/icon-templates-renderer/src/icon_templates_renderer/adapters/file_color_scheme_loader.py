from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from icon_templates_renderer.domain.exceptions import ColorSchemeNotFoundError
from icon_templates_renderer.domain.models import ColorScheme

_SUPPORTED_SUFFIXES = (".yaml", ".yml", ".json")
_SPECIAL_KEYS = ("background", "foreground", "cursor")


class FileColorSchemeLoader:
    def load(self, path: Path) -> ColorScheme:
        if not path.exists():
            raise ColorSchemeNotFoundError(f"Color scheme file not found: {path}")

        if path.suffix in (".yaml", ".yml"):
            return self._load_yaml(path)
        if path.suffix == ".json":
            return self._load_json(path)
        raise ColorSchemeNotFoundError(
            f"Unsupported color scheme format: {path.suffix}. Use .yaml or .json"
        )

    def supports(self, path: Path) -> bool:
        return path.suffix in _SUPPORTED_SUFFIXES

    def _load_yaml(self, path: Path) -> ColorScheme:
        with path.open() as f:
            data = yaml.safe_load(f)
        return self._parse_yaml_data(data)

    def _load_json(self, path: Path) -> ColorScheme:
        with path.open() as f:
            data = json.load(f)
        return self._parse_json_data(data)

    def _parse_yaml_data(self, data: dict[str, Any]) -> ColorScheme:
        """Parse colors.yaml format: special keys + colors as a list."""
        return ColorScheme.from_dict(self._extract_values(data))

    def _parse_json_data(self, data: dict[str, Any]) -> ColorScheme:
        """Parse colors.json format: special keys + colors as a dict (color0, color1, ...)."""
        return ColorScheme.from_dict(self._extract_values(data))

    def _extract_values(self, data: dict[str, Any]) -> dict[str, str]:
        """Extract color values from a color-scheme file.

        Supports both layouts:
        - legacy: ``special.{background,foreground,cursor}`` + ``colors`` (list or dict)
        - CSG export: top-level ``{background,foreground,cursor}`` + ``colors`` list
        - semantic: any additional top-level string keys (e.g. ``surface``, ``accent``,
          ``accent-muted``) are preserved so schemes can carry semantic tokens
        """
        if not isinstance(data, dict):
            return {}
        values: dict[str, str] = {}

        special = data.get("special")
        if isinstance(special, dict):
            for key in _SPECIAL_KEYS:
                value = special.get(key)
                if value is not None:
                    values[key] = str(value)

        for key in _SPECIAL_KEYS:
            value = data.get(key)
            if value is not None:
                values[key] = str(value)

        colors = data.get("colors")
        if isinstance(colors, list):
            for i, color in enumerate(colors):
                values[f"color{i}"] = str(color)
        elif isinstance(colors, dict):
            values.update({str(k): str(v) for k, v in colors.items()})

        for key, value in data.items():
            if key in ("special", "colors"):
                continue
            if isinstance(value, (str, int, float)) and key not in values:
                values[key] = str(value)
        return values
