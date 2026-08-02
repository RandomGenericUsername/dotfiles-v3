from __future__ import annotations

from typing import Protocol, runtime_checkable

from icon_templates_renderer.domain.exceptions import IconRendererError
from icon_templates_renderer.domain.models import (
    ListResult,
    RenderResult,
    ValidateResult,
)


@runtime_checkable
class OutputPort(Protocol):
    def render_result(self, result: RenderResult) -> None: ...
    def list_result(self, result: ListResult) -> None: ...
    def validate_result(self, result: ValidateResult) -> None: ...
    def error(self, exc: IconRendererError) -> None: ...
    def message(self, msg: str) -> None: ...
