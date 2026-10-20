from __future__ import annotations

from pathlib import Path

import pytest

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


@pytest.fixture(autouse=True)
def _hermetic_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep every test off the host HOME/XDG/spine config (S0b AD-8)."""
    root = tmp_path / "hermetic"
    home = root / "home"
    work = root / "work" / "a" / "b" / "c"
    home.mkdir(parents=True)
    work.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    for name in _HERMETIC_XDG_VARS:
        path = root / name.lower()
        path.mkdir(parents=True)
        monkeypatch.setenv(name, str(path))
    for name in _HERMETIC_HOST_ONLY_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(work)
