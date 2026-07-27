from __future__ import annotations

from pathlib import Path

from config_assembler_engine.adapters.path_resolver import CompositePathResolver
from config_assembler_engine.adapters.strategies.cli_path import CliDirStrategy
from config_assembler_engine.adapters.strategies.default_file import DefaultDirStrategy
from config_assembler_engine.adapters.strategies.directory import DirTraversalStrategy
from config_assembler_engine.adapters.strategies.env_path import EnvDirStrategy
from config_assembler_engine.adapters.strategies.xdg import XdgDirStrategy
from config_assembler_engine.domain.models import ResolutionPolicy
from config_assembler_engine.errors import PathResolutionError

from color_scheme_generator.domain.exceptions import ConfigResolutionError

_PACKAGE_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_TEMPLATES_DIR = _PACKAGE_DIR / "defaults" / "templates"
_RESOLUTION_POLICY = ResolutionPolicy(env_prefix="COLORSCHEME_TEMPLATES")


class TemplateDirResolver:
    def __init__(self) -> None:
        strategies: list = [
            CliDirStrategy(),
            EnvDirStrategy(var="TEMPLATES_DIR"),
            DirTraversalStrategy(dirname="templates", max_levels=3),
            XdgDirStrategy(xdg_subdir="color-scheme", dirname="templates"),
            DefaultDirStrategy(path=_DEFAULT_TEMPLATES_DIR),
        ]
        self._resolver = CompositePathResolver(strategies)

    def resolve(self, settings_dir: Path | None = None) -> Path:
        try:
            result = self._resolver.resolve(_RESOLUTION_POLICY, explicit_path=str(settings_dir) if settings_dir else None)
        except PathResolutionError as exc:
            raise ConfigResolutionError(
                "templates_dir", f"Failed to resolve templates directory: {exc}"
            ) from exc
        return result.path
