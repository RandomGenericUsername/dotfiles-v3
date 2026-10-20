from __future__ import annotations

import os
from pathlib import Path

_HERMETIC_XDG_VARS = (
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
    "XDG_DATA_HOME",
    "XDG_STATE_HOME",
)
_HERMETIC_HOST_ONLY_VARS = (
    "DOTFILES_INSTALL_SPINE",
    "DOTFILES_DEV_INPUTS_ROOT",
    "COLORSCHEME_CONFIG_FILE_PATH",
    "WALLPAPER_CONFIG_FILE_PATH",
    "ICON_RENDERER_CONFIG_FILE_PATH",
)


def test_hermetic_environment_canary() -> None:
    """Fail if the autouse fixture is bypassed and the host spine is reachable."""
    home = Path(os.environ["HOME"])
    root = home.parent
    assert home.name == "home"
    assert Path.home() == home
    assert (home / ".local" / "share" / "dotfiles").is_relative_to(root)
    assert Path.cwd().is_relative_to(root)

    for name in _HERMETIC_XDG_VARS:
        value = Path(os.environ[name])
        assert value.is_relative_to(root), f"{name}={value} is outside {root}"
        assert value.is_dir(), f"{name}={value} is not a directory"

    for name in _HERMETIC_HOST_ONLY_VARS:
        assert name not in os.environ, f"{name} leaked from the host environment"
