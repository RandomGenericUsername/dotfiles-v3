from __future__ import annotations

import json
import sys
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any

from wallpaper_effects_generator.domain.enums import CatalogQuery
from wallpaper_effects_generator.domain.models import (
    AppSettings,
    BatchResult,
    EffectsCatalog,
    ProcessingResult,
)


class _CustomEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, Path):
            return str(o)
        if isinstance(o, Enum):
            return o.value
        return super().default(o)


class JsonOutputAdapter:
    def process_result(self, result: ProcessingResult) -> None:
        data = {
            "status": "success" if result.success else "failure",
            "command": result.command,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.return_code,
            "duration": result.duration,
            "output_path": str(result.output_path) if result.output_path else None,
        }
        sys.stdout.write(json.dumps(data, cls=_CustomEncoder, indent=2) + "\n")

    def batch_result(self, result: BatchResult) -> None:
        data = {
            "total": result.total,
            "succeeded": result.succeeded,
            "failed": result.failed,
            "attempted": result.attempted,
            "cancelled": result.cancelled,
            "output_dir": str(result.output_dir) if result.output_dir else None,
            "results": [asdict(r) for r in result.results],
        }
        sys.stdout.write(json.dumps(data, cls=_CustomEncoder, indent=2) + "\n")

    def catalog_list(self, catalog: EffectsCatalog, query: CatalogQuery) -> None:
        items: list[dict[str, Any]] = []
        collections: dict[str, list[dict[str, Any]]] = {}
        if query == CatalogQuery.EFFECT:
            items = [asdict(e) for e in catalog.effects]
        elif query == CatalogQuery.COMPOSITE:
            items = [asdict(c) for c in catalog.composites]
        elif query == CatalogQuery.PRESET:
            items = [asdict(p) for p in catalog.presets]
        elif query == CatalogQuery.ALL:
            collections = {
                "effects": [asdict(e) for e in catalog.effects],
                "composites": [asdict(c) for c in catalog.composites],
                "presets": [asdict(p) for p in catalog.presets],
            }
        data = collections or {"items": items, "count": len(items)}
        sys.stdout.write(json.dumps(data, cls=_CustomEncoder, indent=2) + "\n")

    def config_info(
        self,
        settings: AppSettings,
        catalog: EffectsCatalog,
        sources: list[str],
    ) -> None:
        data = {
            "version": settings.version,
            "settings": asdict(settings),
            "catalog": {
                "effects_count": len(catalog.effects),
                "composites_count": len(catalog.composites),
                "presets_count": len(catalog.presets),
            },
            "sources": sources,
        }
        sys.stdout.write(json.dumps(data, cls=_CustomEncoder, indent=2) + "\n")

    def dump_config_template(self, content: str) -> None:
        sys.stdout.write(content)

    def dump_effects_template(self, content: str) -> None:
        sys.stdout.write(content)

    def error(self, exc: Exception) -> None:
        data = {
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            }
        }
        sys.stderr.write(json.dumps(data, cls=_CustomEncoder, indent=2) + "\n")

    def message(self, msg: str) -> None:
        data = {"message": msg}
        sys.stdout.write(json.dumps(data, cls=_CustomEncoder, indent=2) + "\n")
