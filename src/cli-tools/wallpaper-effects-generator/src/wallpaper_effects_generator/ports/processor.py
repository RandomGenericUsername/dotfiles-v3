from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from wallpaper_effects_generator.domain.models import (
    BatchRequest,
    BatchResult,
    ProcessingRequest,
    ProcessingResult,
)


@runtime_checkable
class EffectProcessorPort(Protocol):
    def process_effect(
        self, name: str, request: ProcessingRequest, params: dict[str, Any] | None = None
    ) -> ProcessingResult: ...

    def process_composite(
        self, name: str, request: ProcessingRequest, params: dict[str, Any] | None = None
    ) -> ProcessingResult: ...

    def process_preset(
        self, name: str, request: ProcessingRequest, params: dict[str, Any] | None = None
    ) -> ProcessingResult: ...

    def process_batch(self, request: BatchRequest) -> BatchResult: ...
