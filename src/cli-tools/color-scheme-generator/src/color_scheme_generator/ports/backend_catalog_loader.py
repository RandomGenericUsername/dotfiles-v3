from __future__ import annotations

from typing import Protocol, runtime_checkable

from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.models import BackendDefinition


@runtime_checkable
class BackendCatalogLoaderPort(Protocol):
    def load(self) -> dict[Backend, BackendDefinition]:
        ...
