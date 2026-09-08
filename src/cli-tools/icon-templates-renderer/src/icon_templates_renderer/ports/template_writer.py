from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from icon_templates_renderer.domain.models import (
    TemplateAnalysis,
    TemplateScanEntry,
    TemplateSetPlaceholderRequest,
)


@runtime_checkable
class TemplateWriterPort(Protocol):
    def analyze(self, path: Path) -> TemplateAnalysis: ...
    def scan(self, root: Path) -> list[TemplateScanEntry]: ...
    def set_placeholder(self, request: TemplateSetPlaceholderRequest) -> TemplateAnalysis: ...
