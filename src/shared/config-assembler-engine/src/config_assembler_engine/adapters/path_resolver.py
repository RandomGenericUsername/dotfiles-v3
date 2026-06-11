from config_assembler_engine.domain.models import ResolutionPolicy, ResolvedPath
from config_assembler_engine.errors import PathResolutionError
from config_assembler_engine.ports.path_resolver import PathResolverPort, ResolutionStrategy


class CompositePathResolver(PathResolverPort):
    def __init__(self, strategies: list[ResolutionStrategy]) -> None:
        self._strategies = strategies

    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath:
        for strategy in self._strategies:
            result = strategy.resolve(policy, explicit_path)
            if result is not None:
                return result
        raise PathResolutionError("No strategy found a config file")
