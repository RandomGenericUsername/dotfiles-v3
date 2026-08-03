from __future__ import annotations

from pathlib import Path

from config_assembler_engine.adapters.path_resolver import CompositePathResolver
from config_assembler_engine.adapters.strategies.directory import DirTraversalStrategy
from config_assembler_engine.adapters.strategies.xdg import XdgDirStrategy
from config_assembler_engine.domain.models import ResolutionPolicy
from config_assembler_engine.errors import PathResolutionError

from icon_templates_renderer.constants import (
    TEMPLATES_TRAVERSAL_DEPTH,
    TEMPLATES_TRAVERSAL_DIRNAME,
    TEMPLATES_XDG_SUBDIR,
)

_RESOLUTION_POLICY = ResolutionPolicy(env_prefix="ICON_RENDERER")


class TemplateDirResolver:
    """Discovery-only templates dir resolver.

    Consulted only when no settings field/env/flag provided the templates dir.
    Returns ``None`` when nothing is found — the orchestrator decides whether
    that is fatal. Reads no env and no CLI (single env axis lives in settings).
    """

    def __init__(self) -> None:
        self._resolver = CompositePathResolver(
            [
                DirTraversalStrategy(
                    dirname=TEMPLATES_TRAVERSAL_DIRNAME,
                    max_levels=TEMPLATES_TRAVERSAL_DEPTH,
                ),
                XdgDirStrategy(
                    xdg_subdir=TEMPLATES_XDG_SUBDIR,
                    dirname=TEMPLATES_TRAVERSAL_DIRNAME,
                ),
            ]
        )

    def resolve(self) -> Path | None:
        try:
            result = self._resolver.resolve(_RESOLUTION_POLICY)
        except PathResolutionError:
            return None
        return result.path
