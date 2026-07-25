from __future__ import annotations

import sys
from dataclasses import asdict

import yaml

from wallpaper_effects_generator.domain.enums import CatalogQuery, ItemType
from wallpaper_effects_generator.domain.models import (
    BatchResult,
    EffectsCatalog,
    ProcessingResult,
)


def _convert(obj: object) -> object:
    if isinstance(obj, tuple):
        return [_convert(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _convert(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert(i) for i in obj]
    return obj


def _effect_to_dict(e: object) -> dict:
    d = asdict(e)
    d["item_type"] = e.item_type.value if isinstance(e.item_type, ItemType) else e.item_type
    d["parameters"] = {
        p.key: {
            "type": str(type(p.default).__name__) if p.default is not None else "string",
            "default": p.default,
            "description": p.description,
        }
        for p in e.parameters
    }
    return d


class PlainOutputAdapter:
    def process_result(self, result: ProcessingResult) -> None:
        lines = [
            f"status: {'success' if result.success else 'failure'}",
            f"command: {result.command}",
        ]
        if result.stdout:
            lines.append(f"stdout: {result.stdout}")
        if result.stderr:
            lines.append(f"stderr: {result.stderr}")
        lines.append(f"return_code: {result.return_code}")
        if result.duration:
            lines.append(f"duration: {result.duration:.2f}s")
        if result.output_path:
            lines.append(f"output_path: {result.output_path}")
        sys.stdout.write("\n".join(lines) + "\n")

    def batch_result(self, result: BatchResult) -> None:
        lines = [
            f"total: {result.total}",
            f"succeeded: {result.succeeded}",
            f"failed: {result.failed}",
            "---",
        ]
        for r in result.results:
            lines.append(f"  command: {r.command}")
            lines.append(f"  status: {'success' if r.success else 'failure'}")
            if r.stdout:
                lines.append(f"  stdout: {r.stdout}")
            if r.stderr:
                lines.append(f"  stderr: {r.stderr}")
            if r.output_path:
                lines.append(f"  output: {r.output_path}")
            if r.duration:
                lines.append(f"  duration: {r.duration:.2f}s")
            lines.append("  ---")
        if result.output_dir:
            lines.append(f"output_dir: {result.output_dir}")
        sys.stdout.write("\n".join(lines) + "\n")

    def catalog_list(self, catalog: EffectsCatalog, query: CatalogQuery) -> None:
        data: dict[str, list[dict]] = {}
        if query in (CatalogQuery.EFFECT, CatalogQuery.ALL):
            data["effects"] = [_effect_to_dict(e) for e in catalog.effects]
        if query in (CatalogQuery.COMPOSITE, CatalogQuery.ALL):
            data["composites"] = _convert([asdict(c) for c in catalog.composites])
        if query in (CatalogQuery.PRESET, CatalogQuery.ALL):
            data["presets"] = _convert([asdict(p) for p in catalog.presets])
        yaml.dump({"version": "1.0", **data}, sys.stdout, default_flow_style=False, sort_keys=False)

    def config_info(
        self,
        settings: AppSettings,
        catalog: EffectsCatalog,
        sources: list[str],
    ) -> None:
        lines = [
            f"version: {settings.version}",
            f"effects_count: {len(catalog.effects)}",
            f"composites_count: {len(catalog.composites)}",
            f"presets_count: {len(catalog.presets)}",
            f"runtime_mode: {settings.runtime.mode.value}",
        ]
        if sources:
            lines.append(f"sources: {', '.join(sources)}")
        sys.stdout.write("\n".join(lines) + "\n")

    def dump_config_template(self, content: str) -> None:
        sys.stdout.write(content)

    def dump_effects_template(self, content: str) -> None:
        sys.stdout.write(content)

    def error(self, exc: Exception) -> None:
        sys.stderr.write(f"error: {type(exc).__name__}: {exc}\n")

    def message(self, msg: str) -> None:
        sys.stdout.write(f"{msg}\n")
