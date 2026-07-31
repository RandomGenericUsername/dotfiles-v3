from __future__ import annotations

import shutil
import subprocess
import time

from wallpaper_effects_generator.domain.exceptions import (
    BinaryNotFoundError,
    CommandExecutionError,
)
from wallpaper_effects_generator.domain.models import CommandResult
from wallpaper_effects_generator.domain.services import CommandSanitizer

_BINARY_CANDIDATES = ["magick", "convert"]


class SubprocessCommandRunner:
    def __init__(
        self, binary: str | None = None, sanitizer: CommandSanitizer | None = None
    ) -> None:
        self._sanitizer = sanitizer or CommandSanitizer()
        self._binary = binary or self._detect_binary()
        if not self.is_available(self._binary):
            raise BinaryNotFoundError(self._binary)

    def is_available(self, binary: str | None = None) -> bool:
        return shutil.which(binary or self._binary) is not None

    def get_binary(self) -> str:
        return self._binary

    def execute(self, command: str | list[str], timeout: int | None = None) -> CommandResult:
        start = time.monotonic()
        try:
            args = command if isinstance(command, list) else self._sanitizer.split(command)
            completed = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration = time.monotonic() - start
            return CommandResult(
                stdout=completed.stdout,
                stderr=completed.stderr,
                return_code=completed.returncode,
                duration=duration,
            )
        except OSError as e:
            duration = time.monotonic() - start
            raise CommandExecutionError(str(command), -1, str(e)) from e
        except subprocess.TimeoutExpired as e:
            duration = time.monotonic() - start
            raise CommandExecutionError(str(command), -1, e.stderr or "") from e

    @staticmethod
    def _detect_binary() -> str:
        for candidate in _BINARY_CANDIDATES:
            if shutil.which(candidate):
                return candidate
        raise BinaryNotFoundError(f"None of {_BINARY_CANDIDATES} found on PATH")
