import os
from pathlib import Path

from config_assembler_engine.domain.models import PathSource, ResolutionPolicy, ResolvedPath
from config_assembler_engine.ports.path_resolver import ResolutionStrategy


class EnvPathStrategy:
    def __init__(self, var: str = "CONFIG_FILE_PATH") -> None:
        self._var = var

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
        if path.exists():
            return ResolvedPath(path=path, source=PathSource.ENV_PATH)
        return None
