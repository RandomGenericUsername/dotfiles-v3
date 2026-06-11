from pathlib import Path

from config_assembler_engine.domain.models import PathSource, ResolutionPolicy, ResolvedPath
from config_assembler_engine.ports.path_resolver import ResolutionStrategy


class DefaultFileStrategy:
    def __init__(self, path: Path) -> None:
        self._path = path

    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath | None:
        if self._path.exists():
            return ResolvedPath(path=self._path.resolve(), source=PathSource.DEFAULT)
        return None
