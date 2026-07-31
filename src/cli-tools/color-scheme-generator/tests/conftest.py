from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from color_scheme_generator.adapters.yaml_backend_catalog_loader import (
    YamlBackendCatalogLoader,
)
from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.models import (
    AppSettings,
    Color,
    ColorScheme,
    GenerationRequest,
    GenerationResult,
)
from color_scheme_generator.factory import CliDependencies


def _scheme() -> ColorScheme:
    return ColorScheme(
        background=Color("#000000", (0, 0, 0)),
        foreground=Color("#ffffff", (255, 255, 255)),
        cursor=Color("#00ff00", (0, 255, 0)),
        colors=tuple(Color("#000000", (0, 0, 0)) for _ in range(16)),
        source_image=Path("/tmp/test.png"),
        backend=Backend.CUSTOM,
        generated_at=datetime.now(),
    )


@dataclass
class FakeProcessor:
    calls: list[dict[str, Any]] = field(default_factory=list)
    error: Exception | None = None

    def process_generate(
        self, request: GenerationRequest, settings: AppSettings
    ) -> GenerationResult:
        self.calls.append({"command": "process_generate", "request": request, "settings": settings})
        if self.error is not None:
            raise self.error
        output_files: list[Path] = []
        for fmt in request.config.formats:
            output_path = request.config.output_dir / f"colors.{fmt.value}"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("dummy")
            output_files.append(output_path)
        return GenerationResult(
            success=True,
            color_scheme=_scheme(),
            output_files=tuple(output_files),
            backend=request.config.backend,
            stderr="",
            return_code=0,
            duration=0.1,
            command="fake generate",
        )

    def process_show(
        self, request: GenerationRequest, settings: AppSettings
    ) -> GenerationResult:
        self.calls.append({"command": "process_show", "request": request, "settings": settings})
        if self.error is not None:
            raise self.error
        return GenerationResult(
            success=True,
            color_scheme=_scheme(),
            output_files=(),
            backend=request.config.backend,
            stderr="",
            return_code=0,
            duration=0.1,
            command="fake show",
        )


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def fake_processor() -> FakeProcessor:
    return FakeProcessor()


@pytest.fixture
def cli_deps_with_processor(fake_processor: FakeProcessor) -> CliDependencies:
    return CliDependencies(
        backend_registry={},
        backend_catalog_loader=YamlBackendCatalogLoader(),
        processor=fake_processor,
    )
