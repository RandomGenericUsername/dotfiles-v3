import os
from pathlib import Path

from config_assembler_engine.domain.models import PathSource, ResolutionPolicy, ResourceKind, ResolvedPath


class EnvPathStrategy:
    def __init__(self, var: str = "CONFIG_FILE_PATH", *, kind: ResourceKind) -> None:
        self._var = var
        self._kind = kind

    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath | None:
        env_key = f"{policy.env_prefix}_{self._var}"
        file_path = os.environ.get(env_key)
        if not file_path:
            return None
        path = Path(file_path).expanduser().resolve()
        check = path.is_file if self._kind == ResourceKind.FILE else path.is_dir
        if check():
            return ResolvedPath(path=path, source=PathSource.ENV_PATH, kind=self._kind)
        return None


class EnvDirStrategy(EnvPathStrategy):
    def __init__(self, var: str = "CONFIG_DIR_PATH") -> None:
        super().__init__(var=var, kind=ResourceKind.DIRECTORY)
