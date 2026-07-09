from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from wallpaper_effects_generator import __version__


class ImportlibVersionProvider:
    def get_version(self) -> str:
        try:
            return version("wallpaper-effects-generator")
        except PackageNotFoundError:
            return __version__
