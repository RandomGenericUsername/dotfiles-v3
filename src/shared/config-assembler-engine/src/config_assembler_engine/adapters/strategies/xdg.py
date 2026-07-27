import os
from pathlib import Path

from config_assembler_engine.domain.models import PathSource, ResolutionPolicy, ResourceKind, ResolvedPath


class XdgStrategy:
    def __init__(self, xdg_subdir: str, filename: str, *, kind: ResourceKind) -> None:
        self._xdg_subdir = xdg_subdir
        self._filename = filename
        self._kind = kind

    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath | None:
        if not self._xdg_subdir:
            return None
        xdg_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        candidate = xdg_home / self._xdg_subdir / self._filename
        check = candidate.is_file if self._kind == ResourceKind.FILE else candidate.is_dir
        if check():
            return ResolvedPath(path=candidate.resolve(), source=PathSource.XDG, kind=self._kind)
        return None


class XdgDirStrategy(XdgStrategy):
    def __init__(self, xdg_subdir: str, dirname: str) -> None:
        super().__init__(xdg_subdir=xdg_subdir, filename=dirname, kind=ResourceKind.DIRECTORY)
