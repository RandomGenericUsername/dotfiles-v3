from pathlib import Path

import pytest

from config_assembler_engine.adapters.path_resolver import CompositePathResolver
from config_assembler_engine.domain.models import PathSource, ResolutionPolicy, ResolvedPath
from config_assembler_engine.errors import PathResolutionError
from config_assembler_engine.ports.path_resolver import ResolutionStrategy


class FakeStrategy:
    def __init__(self, result: ResolvedPath | None) -> None:
        self._result = result

    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath | None:
        return self._result


class TestCompositePathResolver:
    def test_returns_first_hit(self):
        s1 = FakeStrategy(None)
        s2 = FakeStrategy(ResolvedPath(path=Path("/a.yaml"), source=PathSource.DIRECTORY))
        s3 = FakeStrategy(ResolvedPath(path=Path("/b.yaml"), source=PathSource.DEFAULT))
        resolver = CompositePathResolver(strategies=[s1, s2, s3])
        result = resolver.resolve(ResolutionPolicy(env_prefix=""))
        assert result.path == Path("/a.yaml")

    def test_raises_if_all_return_none(self):
        s1 = FakeStrategy(None)
        s2 = FakeStrategy(None)
        resolver = CompositePathResolver(strategies=[s1, s2])
        with pytest.raises(PathResolutionError):
            resolver.resolve(ResolutionPolicy(env_prefix=""))

    def test_empty_strategies_list_raises(self):
        resolver = CompositePathResolver(strategies=[])
        with pytest.raises(PathResolutionError):
            resolver.resolve(ResolutionPolicy(env_prefix=""))

    def test_passes_explicit_path_to_strategies(self):
        class RecordingStrategy:
            def __init__(self):
                self.called_with = None

            def resolve(self, policy, explicit_path=None):
                self.called_with = explicit_path
                return None

        s = RecordingStrategy()
        resolver = CompositePathResolver(strategies=[s])
        with pytest.raises(PathResolutionError):
            resolver.resolve(ResolutionPolicy(env_prefix=""), explicit_path="/custom.yaml")
        assert s.called_with == "/custom.yaml"
