from __future__ import annotations

from typing import Protocol, runtime_checkable

from icon_templates_renderer.domain.models import (
    ListRequest,
    ListResult,
    MappingSetDefaultRequest,
    MappingSetDefaultResult,
    MappingSetRequest,
    MappingSetResult,
    MappingShowRequest,
    MappingShowResult,
    RenderRequest,
    RenderResult,
    ValidateRequest,
    ValidateResult,
)


@runtime_checkable
class IconRendererPort(Protocol):
    def render(self, request: RenderRequest) -> RenderResult: ...
    def list(self, request: ListRequest) -> ListResult: ...
    def validate(self, request: ValidateRequest) -> ValidateResult: ...
    def mapping_show(self, request: MappingShowRequest) -> MappingShowResult: ...
    def mapping_set(self, request: MappingSetRequest) -> MappingSetResult: ...
    def mapping_set_default(self, request: MappingSetDefaultRequest) -> MappingSetDefaultResult: ...
