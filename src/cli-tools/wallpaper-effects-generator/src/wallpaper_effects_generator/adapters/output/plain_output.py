from __future__ import annotations

import sys

from wallpaper_effects_generator.domain.enums import CatalogQuery
from wallpaper_effects_generator.domain.models import (
    AppSettings,
    BatchResult,
    EffectsCatalog,
    ProcessingResult,
)


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
        lines: list[str] = []
        if query in (CatalogQuery.EFFECT, CatalogQuery.ALL):
            for e in catalog.effects:
                lines.append(f"effect: {e.name}")
                lines.append(f"  description: {e.description}")
                lines.append(f"  command: {e.command}")
                lines.append("  ---")
        if query in (CatalogQuery.COMPOSITE, CatalogQuery.ALL):
            for c in catalog.composites:
                steps = ", ".join(s.effect_name for s in c.steps)
                lines.append(f"composite: {c.name}")
                lines.append(f"  description: {c.description}")
                lines.append(f"  steps: [{steps}]")
                lines.append("  ---")
        if query in (CatalogQuery.PRESET, CatalogQuery.ALL):
            for p in catalog.presets:
                lines.append(f"preset: {p.name}")
                lines.append(f"  description: {p.description}")
                lines.append(f"  effects: {', '.join(p.effects)}")
                lines.append("  ---")
        sys.stdout.write("\n".join(lines) + "\n")

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

    def dump_config(
        self,
        settings: AppSettings,
        sources: list[str],
    ) -> None:
        lines = [
            f"version: {settings.version}",
            f"parallel: {settings.execution.parallel}",
            f"strict: {settings.execution.strict}",
            f"max_workers: {settings.execution.max_workers}",
            f"verbosity: {settings.output.verbosity.value}",
            f"temp_dir: {settings.processing.temp_dir}",
            f"binary: {settings.backend.binary}",
            f"runtime_mode: {settings.runtime.mode.value}",
            f"container_engine: {settings.container.engine}",
            f"image_tag: {settings.container.image_tag}",
        ]
        if settings.container.image_registry:
            lines.append(f"image_registry: {settings.container.image_registry}")
        if sources:
            lines.append(f"sources: {', '.join(sources)}")
        sys.stdout.write("\n".join(lines) + "\n")

    def error(self, exc: Exception) -> None:
        sys.stderr.write(f"error: {type(exc).__name__}: {exc}\n")

    def message(self, msg: str) -> None:
        sys.stdout.write(f"{msg}\n")
