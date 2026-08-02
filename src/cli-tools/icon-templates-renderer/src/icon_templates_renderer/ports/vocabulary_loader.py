from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from icon_templates_renderer.domain.models import Vocabulary


@runtime_checkable
class VocabularyLoaderPort(Protocol):
    def load(self, path: Path | None) -> Vocabulary: ...
