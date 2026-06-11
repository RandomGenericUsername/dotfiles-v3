from pathlib import Path

from config_assembler_engine.domain.models import PathSource, ResolutionPolicy, ResolvedPath
from config_assembler_engine.ports.path_resolver import ResolutionStrategy


class CliPathStrategy:
    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath | None:
        if not explicit_path:
            return None
        path = Path(explicit_path).expanduser().resolve()
        if path.exists():
            return ResolvedPath(path=path, source=PathSource.CLI_PATH)
        return None
