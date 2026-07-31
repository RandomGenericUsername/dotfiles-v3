from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from typer.testing import CliRunner

from wallpaper_effects_generator.domain.models import (
    BatchRequest,
    BatchResult,
    ProcessingRequest,
    ProcessingResult,
)
from wallpaper_effects_generator.factory import CliDependencies


@dataclass
class FakeProcessor:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def process_effect(
        self, name: str, request: ProcessingRequest, params: dict[str, Any] | None = None
    ) -> ProcessingResult:
        self.calls.append(
            {"command": "process_effect", "name": name, "request": request, "params": params}
        )
        if request.output_path:
            request.output_path.parent.mkdir(parents=True, exist_ok=True)
            request.output_path.write_text("dummy")
        return ProcessingResult(
            success=True,
            command=f"process effect {name}",
            stdout="",
            stderr="",
            return_code=0,
            output_path=request.output_path,
        )

    def process_composite(
        self, name: str, request: ProcessingRequest, params: dict[str, Any] | None = None
    ) -> ProcessingResult:
        self.calls.append(
            {"command": "process_composite", "name": name, "request": request, "params": params}
        )
        if request.output_path:
            request.output_path.parent.mkdir(parents=True, exist_ok=True)
            request.output_path.write_text("dummy")
        return ProcessingResult(
            success=True,
            command=f"process composite {name}",
            stdout="",
            stderr="",
            return_code=0,
            output_path=request.output_path,
        )

    def process_preset(
        self, name: str, request: ProcessingRequest, params: dict[str, Any] | None = None
    ) -> ProcessingResult:
        self.calls.append(
            {"command": "process_preset", "name": name, "request": request, "params": params}
        )
        if request.output_path:
            request.output_path.parent.mkdir(parents=True, exist_ok=True)
            request.output_path.write_text("dummy")
        return ProcessingResult(
            success=True,
            command=f"process preset {name}",
            stdout="",
            stderr="",
            return_code=0,
            output_path=request.output_path,
        )

    def process_batch(self, request: BatchRequest) -> BatchResult:
        self.calls.append({"command": "process_batch", "request": request})
        output_dir = request.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        names = [
            "blur",
            "resize",
            "contrast",
            "brightness",
            "saturation",
            "sepia",
            "vignette",
            "negate",
            "blackwhite",
            "color_overlay",
            "edge_detect",
        ]
        results = tuple(
            ProcessingResult(
                success=True,
                command=f"batch {name}",
                stdout="",
                stderr="",
                return_code=0,
                output_path=output_dir / f"{name}.png",
            )
            for name in names
        )
        return BatchResult(
            total=len(names), succeeded=len(names), failed=0, results=results, output_dir=output_dir
        )


class FakeImageManager:
    def __init__(self, engine: FakeEngine):
        self._engine = engine

    def build(
        self,
        context: Any,
        image_name: str,
        timeout: float | None = 600.0,
    ) -> str:
        self._engine.builds.append((image_name, context))
        return "deadbeef"

    def exists(self, image: str) -> bool:
        self._engine.exist_checks.append(image)
        return self._engine.image_exists

    def remove(self, image: str, force: bool = False) -> None:
        self._engine.removals.append(image)


@dataclass
class FakeEngine:
    image_exists: bool = True
    available: bool = True
    builds: list[tuple] = field(default_factory=list)
    exist_checks: list[str] = field(default_factory=list)
    removals: list[str] = field(default_factory=list)

    @property
    def images(self) -> FakeImageManager:
        return FakeImageManager(self)

    def is_available(self) -> bool:
        return self.available


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def fake_processor() -> FakeProcessor:
    return FakeProcessor()


@pytest.fixture
def cli_deps_with_processor(
    fake_processor: FakeProcessor, monkeypatch: pytest.MonkeyPatch
) -> CliDependencies:
    deps = CliDependencies(processor=fake_processor)
    monkeypatch.setattr("wallpaper_effects_generator.cli.main.build_deps", lambda: deps)
    return deps
