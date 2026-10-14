from __future__ import annotations

import os
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

# Bound ImageMagick's per-invocation pixel-cache memory. WEG runs every effect
# in parallel (see ExecutionSettings.max_workers), so an unbounded `magick`
# lets a single large wallpaper balloon: on a 7680x4320 (8K) input each worker
# reached ~2.3 GiB anonymous RSS, and ~20 workers together exhausted RAM and
# triggered a global OOM.
#
# ImageMagick reads MAGICK_MEMORY_LIMIT as the `memory` resource (verified:
# `MAGICK_MEMORY_LIMIT=256MiB magick -list resource` -> Memory: 256MiB). With
# the cap, an 8K vignette's anonymous RSS measured 2.3 GiB -> ~0.22 GiB; the
# excess spills off-heap instead of competing for RAM. Pass memory_limit=None
# to opt out (e.g. a caller that wants ImageMagick's own defaults).
#
# CAVEAT: the spill still has to go somewhere. If ImageMagick's temp cache
# lands on a RAM-backed /tmp (tmpfs), the "disk" fallback consumes RAM too and
# workers can abort under pressure. Pair this cap with a disk-backed temp path
# (MAGICK_TEMPORARY_PATH / settings.processing.temp_dir) for full relief.
DEFAULT_MEMORY_LIMIT = "256MiB"
_MEMORY_LIMIT_ENV_VAR = "MAGICK_MEMORY_LIMIT"
# ImageMagick's pixel cache spills to this path once MAGICK_MEMORY_LIMIT is
# exceeded. Pointing it at a disk-backed directory (settings.processing.temp_dir)
# is what turns the cap into relief instead of forcing the spill back into a
# RAM-backed /tmp (tmpfs).
_TEMPORARY_PATH_ENV_VAR = "MAGICK_TEMPORARY_PATH"


class SubprocessCommandRunner:
    def __init__(
        self,
        binary: str | None = None,
        sanitizer: CommandSanitizer | None = None,
        memory_limit: str | None = DEFAULT_MEMORY_LIMIT,
        temporary_path: str | None = None,
    ) -> None:
        self._sanitizer = sanitizer or CommandSanitizer()
        self._binary = binary or self._detect_binary()
        self._memory_limit = memory_limit
        self._temporary_path = temporary_path
        if not self.is_available(self._binary):
            raise BinaryNotFoundError(self._binary)

    def _build_env(self) -> dict[str, str] | None:
        """Environment for the subprocess, with the ImageMagick memory cap and
        pixel-cache temporary path.

        Returns ``None`` (inherit the parent environment unchanged) when
        neither is configured.
        """
        if not self._memory_limit and not self._temporary_path:
            return None
        env = {**os.environ}
        if self._memory_limit:
            env[_MEMORY_LIMIT_ENV_VAR] = self._memory_limit
        if self._temporary_path:
            env[_TEMPORARY_PATH_ENV_VAR] = self._temporary_path
        return env

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
                env=self._build_env(),
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
