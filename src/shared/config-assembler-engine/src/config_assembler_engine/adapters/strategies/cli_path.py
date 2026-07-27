from pathlib import Path

from config_assembler_engine.domain.models import PathSource, ResolutionPolicy, ResourceKind, ResolvedPath


class CliPathStrategy:
    def __init__(self, *, kind: ResourceKind) -> None:
        self._kind = kind

    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath | None:
        if not explicit_path:
            return None
        path = Path(explicit_path).expanduser().resolve()
        check = path.is_file if self._kind == ResourceKind.FILE else path.is_dir
        if check():
            return ResolvedPath(path=path, source=PathSource.CLI_PATH, kind=self._kind)
        return None


class CliDirStrategy(CliPathStrategy):
    def __init__(self) -> None:
        super().__init__(kind=ResourceKind.DIRECTORY)
