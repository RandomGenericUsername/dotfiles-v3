from __future__ import annotations

from pathlib import Path

from config_assembler_engine.adapters.path_resolver import CompositePathResolver
from config_assembler_engine.adapters.strategies.directory import DirectoryTraversalStrategy
from config_assembler_engine.adapters.strategies.xdg import XdgStrategy
from config_assembler_engine.domain.models import ResolutionPolicy, ResourceKind
from config_assembler_engine.errors import PathResolutionError

from icon_templates_renderer.constants import (
    COLOR_SCHEME_FILENAME,
    COLOR_SCHEME_TRAVERSAL_DEPTH,
    COLOR_SCHEME_XDG_SUBDIR,
)

_RESOLUTION_POLICY = ResolutionPolicy(env_prefix="ICON_RENDERER")


class ColorSchemeResolver:
    """Discovery-only color scheme file resolver.

    Consulted only when no settings field/env/flag provided the color scheme.
    Returns ``None`` when nothing is found — the orchestrator decides whether
    that is fatal. Reads no env and no CLI (single env axis lives in settings).
    """

    def __init__(self) -> None:
        self._resolver = CompositePathResolver(
            [
                DirectoryTraversalStrategy(
                    filename=COLOR_SCHEME_FILENAME,
                    max_levels=COLOR_SCHEME_TRAVERSAL_DEPTH,
                    kind=ResourceKind.FILE,
                ),
                XdgStrategy(
                    xdg_subdir=COLOR_SCHEME_XDG_SUBDIR,
                    filename=COLOR_SCHEME_FILENAME,
                    kind=ResourceKind.FILE,
                ),
            ]
        )

    def resolve(self) -> Path | None:
        try:
            result = self._resolver.resolve(_RESOLUTION_POLICY)
        except PathResolutionError:
            return None
        return result.path
