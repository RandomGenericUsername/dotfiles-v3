from __future__ import annotations

import json
import sys

from color_scheme_generator.domain.enums import Verbosity
from color_scheme_generator.domain.exceptions import (
    BackendNotAvailableError,
    ColorExtractionError,
    ColorSchemeError,
    ConfigResolutionError,
    InvalidImageError,
    OutputWriteError,
    PaletteGenerationError,
)
from color_scheme_generator.domain.models import Color, ColorScheme, GenerationResult


class JsonOutput:
    def __init__(self, verbosity: Verbosity = Verbosity.NORMAL) -> None:
        self._verbosity = verbosity

    def process_result(self, result: GenerationResult) -> None:
        if self._verbosity is Verbosity.QUIET:
            return
        payload: dict = {
            "success": result.success,
            "color_scheme": self._serialize_color_scheme(result.color_scheme),
            "output_files": [str(p) for p in result.output_files],
            "backend": result.backend.value,
            "duration": result.duration,
            "command": result.command or None,
        }
        json.dump(payload, sys.stdout, default=str)
        print()

    def error(self, exc: ColorSchemeError) -> None:
        payload: dict = {
            "success": False,
            "error": self._serialize_error(exc),
        }
        json.dump(payload, sys.stderr, default=str)
        print(file=sys.stderr)

    def palette_display(self, scheme: ColorScheme) -> None:
        payload = self._serialize_color_scheme(scheme)
        json.dump(payload, sys.stdout, default=str)
        print()

    def message(self, msg: str) -> None:
        json.dump({"message": msg}, sys.stdout, default=str)
        print()

    def config_info(
        self,
        settings: object,
        backends: dict,
        sources: list[str],
        templates: object = None,
    ) -> None:
        data = {
            "settings": self._serialize_settings(settings) if settings else {},
            "backends": backends,
            "templates": (
                {
                    "templates_count": len(templates.templates),  # type: ignore[union-attr]
                    "formats": [t.format.value for t in templates.templates],  # type: ignore[union-attr]
                }
                if templates
                else {"templates_count": 0, "formats": []}
            ),
            "sources": sources,
        }
        sys.stdout.write(json.dumps(data, indent=2, default=str) + "\n")

    def install_result(self, results: list[dict]) -> None:
        print(json.dumps({"install": results}, indent=2))

    def uninstall_result(self, results: list[dict]) -> None:
        print(json.dumps({"uninstall": results}, indent=2))

    def version_info(self, version: str) -> None:
        print(json.dumps({"version": version}))

    def backends_catalog(self, backends: list[dict], hint: str = "") -> None:
        payload: dict = {"backends": backends}
        if hint:
            payload["hint"] = hint
        print(json.dumps(payload, indent=2))

    @staticmethod
    def _serialize_settings(settings: object) -> dict:
        from dataclasses import fields
        result = {}
        for f in fields(settings):
            val = getattr(settings, f.name)
            if hasattr(val, "__dataclass_fields__"):
                result[f.name] = JsonOutput._serialize_settings(val)
            elif isinstance(val, tuple):
                result[f.name] = [JsonOutput._serialize_settings(v) if hasattr(v, "__dataclass_fields__") else str(v) for v in val]
            elif isinstance(val, dict):
                if val and hasattr(next(iter(val.values())), "__dataclass_fields__"):
                    result[f.name] = {k: JsonOutput._serialize_settings(v) for k, v in val.items()}
                else:
                    result[f.name] = {k: str(v) for k, v in val.items()}
            else:
                result[f.name] = val.value if hasattr(val, 'value') else str(val)
        return result

    def _serialize_color_scheme(self, scheme: ColorScheme | None) -> dict:
        if scheme is None:
            return {}
        return {
            "background": self._color_to_dict(scheme.background),
            "foreground": self._color_to_dict(scheme.foreground),
            "cursor": self._color_to_dict(scheme.cursor),
            "colors": [self._color_to_dict(c) for c in scheme.colors],
            "source_image": str(scheme.source_image),
            "backend": scheme.backend.value,
            "generated_at": scheme.generated_at.isoformat(),
        }

    def _color_to_dict(self, color: Color) -> dict:
        return {"hex": color.hex, "rgb": list(color.rgb)}

    def _serialize_error(self, exc: ColorSchemeError) -> dict:
        error_info: dict = {
            "type": type(exc).__name__,
            "message": str(exc),
        }

        if isinstance(exc, InvalidImageError):
            error_info["image_path"] = str(exc.image_path)
            error_info["reason"] = exc.reason
        elif isinstance(exc, ColorExtractionError):
            error_info["backend"] = exc.backend.value
            error_info["stderr"] = exc.stderr
        elif isinstance(exc, BackendNotAvailableError):
            error_info["backend"] = exc.backend.value
            error_info["hint"] = exc.hint
        elif isinstance(exc, OutputWriteError):
            error_info["path"] = str(exc.path)
            error_info["reason"] = exc.reason
        elif isinstance(exc, ConfigResolutionError):
            error_info["key"] = exc.key
            error_info["reason"] = exc.reason
            if exc.source is not None:
                error_info["source"] = str(exc.source)
        elif isinstance(exc, PaletteGenerationError):
            if exc.backend is not None:
                error_info["backend"] = exc.backend.value

        return error_info
