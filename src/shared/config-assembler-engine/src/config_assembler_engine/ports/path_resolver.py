from typing import Optional, Protocol

from config_assembler_engine.domain.models import ResolutionPolicy, ResolvedPath


class ResolutionStrategy(Protocol):
    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath | None:
        ...


class PathResolverPort(Protocol):
    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath:
        ...
