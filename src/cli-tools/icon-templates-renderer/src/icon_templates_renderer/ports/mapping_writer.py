from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class MappingWriterPort(Protocol):
    def set_mapping(
        self,
        yaml_path: Path,
        group: str,
        variant: str | None,
        placeholder: str,
        token: str,
    ) -> str: ...
    def set_default(self, yaml_path: Path, placeholder: str, token: str) -> str: ...
    def diff(self, yaml_path: Path, new_text: str) -> str: ...
