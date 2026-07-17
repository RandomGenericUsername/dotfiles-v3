from __future__ import annotations

import os
from pathlib import Path

from config_assembler_engine.adapters.path_resolver import CompositePathResolver
from config_assembler_engine.domain.models import PathSource, ResolutionPolicy, ResolvedPath
from config_assembler_engine.errors import PathResolutionError

from color_scheme_generator.domain.exceptions import ConfigResolutionError

_PACKAGE_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_TEMPLATES_DIR = _PACKAGE_DIR / "defaults" / "templates"
_RESOLUTION_POLICY = ResolutionPolicy(env_prefix="COLORSCHEME_TEMPLATES")


class _EnvDirStrategy:
    def __init__(self, var: str) -> None:
        self._var = var

    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath | None:
        env_key = f"{policy.env_prefix}_{self._var}"
        if env_key not in os.environ:
            return None
        dir_path = os.environ[env_key]
        if not dir_path:
            return None
        path = Path(dir_path).expanduser().resolve()
        if path.is_dir():
            return ResolvedPath(path=path, source=PathSource.ENV_PATH)
        return None


class _XdgDirStrategy:
    def __init__(self, xdg_subdir: str, dirname: str) -> None:
        self._xdg_subdir = xdg_subdir
        self._dirname = dirname

    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath | None:
        try:
            home_default = Path.home() / ".config"
        except RuntimeError:
            home_default = Path("/root/.config")
        xdg_home = Path(os.environ.get("XDG_CONFIG_HOME", home_default))
        candidate = xdg_home / self._xdg_subdir / self._dirname
        if candidate.is_dir():
            return ResolvedPath(path=candidate.resolve(), source=PathSource.XDG)
        return None


class _DefaultDirStrategy:
    def __init__(self, path: Path) -> None:
        self._path = path

    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath | None:
        if self._path.is_dir():
            return ResolvedPath(path=self._path.resolve(), source=PathSource.DEFAULT)
        return None


class TemplateDirResolver:
    def __init__(self) -> None:
        strategies: list = [
            _EnvDirStrategy(var="TEMPLATES_DIR"),
            _XdgDirStrategy(xdg_subdir="color-scheme", dirname="templates"),
            _DefaultDirStrategy(path=_DEFAULT_TEMPLATES_DIR),
        ]
        self._resolver = CompositePathResolver(strategies)

    def resolve(self) -> Path:
        try:
            result = self._resolver.resolve(_RESOLUTION_POLICY)
        except PathResolutionError as exc:
            raise ConfigResolutionError(
                "templates_dir", f"Failed to resolve templates directory: {exc}"
            ) from exc
        return result.path
