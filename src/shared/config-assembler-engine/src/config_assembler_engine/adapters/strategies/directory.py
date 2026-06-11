from pathlib import Path

from config_assembler_engine.domain.models import PathSource, ResolutionPolicy, ResolvedPath


class DirectoryTraversalStrategy:
    def __init__(self, filename: str, max_levels: int = 3) -> None:
        self._filename = filename
        self._max_levels = max_levels

    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath | None:
        cwd = Path.cwd()
        for level in range(self._max_levels + 1):
            check_dir = cwd.parents[level - 1] if level > 0 else cwd
            candidate = check_dir / self._filename
            if candidate.exists():
                return ResolvedPath(path=candidate.resolve(), source=PathSource.DIRECTORY)
        return None
