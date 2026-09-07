from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from icon_templates_renderer.domain.models import TemplateAnalysis, TemplateSetPlaceholderRequest


@runtime_checkable
class TemplateWriterPort(Protocol):
    def analyze(self, path: Path) -> TemplateAnalysis: ...
    def set_placeholder(self, request: TemplateSetPlaceholderRequest) -> TemplateAnalysis: ...
