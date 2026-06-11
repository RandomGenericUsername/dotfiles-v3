import os
from pathlib import Path

from config_assembler_engine.domain.models import PathSource, ResolutionPolicy, ResolvedPath


class XdgStrategy:
    def __init__(self, xdg_subdir: str, filename: str) -> None:
        self._xdg_subdir = xdg_subdir
        self._filename = filename

    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath | None:
        if not self._xdg_subdir:
            return None
        xdg_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        candidate = xdg_home / self._xdg_subdir / self._filename
        if candidate.exists():
            return ResolvedPath(path=candidate.resolve(), source=PathSource.XDG)
        return None
