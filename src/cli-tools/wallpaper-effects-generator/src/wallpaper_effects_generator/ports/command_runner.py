from __future__ import annotations

from typing import Protocol, runtime_checkable

from wallpaper_effects_generator.domain.models import CommandResult


@runtime_checkable
class CommandRunnerPort(Protocol):
    def is_available(self, binary: str | None = None) -> bool: ...

    def get_binary(self) -> str: ...

    def execute(self, command: str | list[str], timeout: int | None = None) -> CommandResult: ...
