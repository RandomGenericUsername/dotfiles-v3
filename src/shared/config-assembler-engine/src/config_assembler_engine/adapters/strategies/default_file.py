from pathlib import Path

from config_assembler_engine.domain.models import PathSource, ResolutionPolicy, ResourceKind, ResolvedPath


class DefaultFileStrategy:
    def __init__(self, path: Path, *, kind: ResourceKind) -> None:
        self._path = path
        self._kind = kind

    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath | None:
        check = self._path.is_file if self._kind == ResourceKind.FILE else self._path.is_dir
        if check():
            return ResolvedPath(path=self._path.resolve(), source=PathSource.DEFAULT, kind=self._kind)
        return None


class DefaultDirStrategy(DefaultFileStrategy):
    def __init__(self, path: Path) -> None:
        super().__init__(path, kind=ResourceKind.DIRECTORY)
