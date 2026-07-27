from pathlib import Path

from config_assembler_engine.domain.models import PathSource, ResolutionPolicy, ResourceKind, ResolvedPath


class DirectoryTraversalStrategy:
    def __init__(self, filename: str, max_levels: int = 3, *, kind: ResourceKind) -> None:
        self._filename = filename
        self._max_levels = max_levels
        self._kind = kind

    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath | None:
        cwd = Path.cwd()
        for level in range(self._max_levels + 1):
            if level > 0 and level > len(cwd.parents):
                break
            check_dir = cwd.parents[level - 1] if level > 0 else cwd
            candidate = check_dir / self._filename
            check = candidate.is_file if self._kind == ResourceKind.FILE else candidate.is_dir
            if check():
                return ResolvedPath(path=candidate.resolve(), source=PathSource.DIRECTORY, kind=self._kind)
        return None


class DirTraversalStrategy(DirectoryTraversalStrategy):
    def __init__(self, dirname: str, max_levels: int = 3) -> None:
        super().__init__(filename=dirname, max_levels=max_levels, kind=ResourceKind.DIRECTORY)
