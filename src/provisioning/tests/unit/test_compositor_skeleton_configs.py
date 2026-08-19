from __future__ import annotations

from pathlib import Path


def _find_repo_root() -> Path:
    """Locate the repo root by walking up from this test file, anchored on the
    compositor skeleton marker.

    Mirrors ``_find_ansible_dir()`` (test_default_palette_role.py), but anchors
    on ``dotfiles/config/hypr/hyprland.conf`` instead of ``pyproject.toml`` +
    ``ansible/``: the config skeletons live at the repo root, NOT under
    ``src/provisioning``, so the pyproject+ansible anchor would fail here.

    These skeletons have NO Python consumer in Phase 1 (the compositor_configs
    role in Story 2.9 only copies them), so these tests are PURE structural
    real-file assertions — existence + exact first-line/path strings — rather
    than reader-parsing tests. Do NOT "fix" them to go through a reader that
    does not exist.
    """
    for parent in Path(__file__).resolve().parents:
        marker = parent / "dotfiles" / "config" / "hypr" / "hyprland.conf"
        if marker.is_file():
            return parent
    raise FileNotFoundError(
        "dotfiles/config/ not found walking up from the test file; "
        "AC 1-6 real-skeleton coverage requires the authored skeleton dirs"
    )


_REPO_ROOT = _find_repo_root()
_CONFIG_DIR = _REPO_ROOT / "dotfiles" / "config"

_HYPR_CONF = _CONFIG_DIR / "hypr" / "hyprland.conf"
_AGS_APP = _CONFIG_DIR / "ags" / "app.tsx"
_AGS_CSS = _CONFIG_DIR / "ags" / "style.css"
_HYPRPAPER_CONF = _CONFIG_DIR / "hyprpaper" / "hyprpaper.conf"

_HYPR_HEADER = "source = {{ compositor_configs_xdg_config_home }}/hypr/colors.conf"
_AGS_PALETTE_LOAD = "app.apply_css(`${GLib.get_user_config_dir()}/ags/colors.css`)"
_HYPRPAPER_PRELOAD = "preload = ~/.local/share/dotfiles/wallpapers/default.png"
_HYPRPAPER_WALLPAPER = "wallpaper = ,~/.local/share/dotfiles/wallpapers/default.png"

_EXISTING_DIRS_KNOWN_FILES = {
    "nvim": ("init.lua",),
    "starship": ("starship.toml",),
    "wlogout": ("layout", "style.css.tpl"),
    "zsh": (".zshrc.j2",),
}

_TEMPLATE_SUFFIXES = (".j2", ".tpl")


def _first_line(path: Path) -> str:
    return path.read_text(encoding="utf-8").splitlines()[0]


class TestHyprlandSkeleton:
    def test_hyprland_conf_exists(self) -> None:
        """AC 1: dotfiles/config/hypr/hyprland.conf exists."""
        assert _HYPR_CONF.is_file(), "dotfiles/config/hypr/hyprland.conf missing"

    def test_first_line_sources_colors_conf(self) -> None:
        """AC 1: FIRST line is `source = {{ compositor_configs_xdg_config_home
        }}/hypr/colors.conf` — the fragment target Story 2.7/2.9 copies to the
        resolved XDG config home. Review decision 2026-08-12: the skeleton
        first line is templated so it stays correct when $XDG_CONFIG_HOME is
        set (the old verbatim `~/.config` reference diverged from the role's
        XDG-aware fragment dest); Story 2.9 renders it via the template module
        with `force: false` (AC 5 — a placed skeleton is never re-touched)."""
        assert _first_line(_HYPR_CONF) == _HYPR_HEADER


class TestAgsSkeleton:
    def test_app_tsx_exists(self) -> None:
        """AC 2: dotfiles/config/ags/app.tsx exists."""
        assert _AGS_APP.is_file(), "dotfiles/config/ags/app.tsx missing"

    def test_loads_palette_at_runtime(self) -> None:
        """AC 2: the skeleton applies the Story 2.7-emitted AGS palette fragment
        (colors.gtk.css) at RUNTIME via app.apply_css() — NOT bundled at build
        time — so the Phase 2 runtime can repoint ~/.config/ags/colors.css ->
        current/colors.gtk.css and take effect on the next `ags run` restart."""
        assert _AGS_PALETTE_LOAD in _AGS_APP.read_text(encoding="utf-8"), (
            "app.tsx must apply the palette fragment colors.css at runtime"
        )

    def test_style_css_exists(self) -> None:
        """AC 2: dotfiles/config/ags/style.css exists — the AGS bar stylesheet
        referencing the palette @color_00..@color_15 variables."""
        assert _AGS_CSS.is_file(), "dotfiles/config/ags/style.css missing"


class TestHyprpaperSkeleton:
    def test_hyprpaper_conf_exists(self) -> None:
        """AC 4: dotfiles/config/hyprpaper/hyprpaper.conf exists."""
        assert _HYPRPAPER_CONF.is_file(), "dotfiles/config/hyprpaper/hyprpaper.conf missing"

    def test_preload_line_exact(self) -> None:
        """AC 4: exact `preload` line pointing at the default wallpaper path.
        Full-line equality (splitlines), not substring containment, so a future
        path change or a malformed line with trailing junk is a loud failure."""
        assert _HYPRPAPER_PRELOAD in _HYPRPAPER_CONF.read_text(encoding="utf-8").splitlines(), (
            f"hyprpaper.conf must contain exactly {_HYPRPAPER_PRELOAD!r}"
        )

    def test_wallpaper_line_exact(self) -> None:
        """AC 4: exact `wallpaper` line (empty monitor selector + default path).
        Full-line equality, so a raw `<install>` placeholder or trailing-junk
        variant can never pass."""
        assert _HYPRPAPER_WALLPAPER in _HYPRPAPER_CONF.read_text(encoding="utf-8").splitlines(), (
            f"hyprpaper.conf must contain exactly {_HYPRPAPER_WALLPAPER!r}"
        )

    def test_no_literal_install_placeholder(self) -> None:
        """AC 4 guard: the config is FLAT STATIC — a raw `<install>` literal
        must never appear (it would be a broken Hyprpaper path)."""
        assert "<install>" not in _HYPRPAPER_CONF.read_text(encoding="utf-8")


class TestExistingDirsUnchanged:
    def test_existing_config_dirs_still_hold_known_files(self) -> None:
        """AC 5: existing config dirs are unchanged — locked at the
        file-presence level (nvim/init.lua, starship/starship.toml,
        wlogout/layout, wlogout/style.css.tpl, zsh/.zshrc.j2) so a future
        story's legitimate additions are not frozen."""
        for dir_name, files in _EXISTING_DIRS_KNOWN_FILES.items():
            for name in files:
                assert (_CONFIG_DIR / dir_name / name).is_file(), (
                    f"expected {dir_name}/{name} to remain present (AC 5)"
                )

    def test_icon_mappings_dir_unchanged(self) -> None:
        """AC 5: icon-template-color-scheme-mappings still holds at least one
        *.yaml (it was present at authoring time and must remain unchanged)."""
        mapping_dir = _CONFIG_DIR / "icon-template-color-scheme-mappings"
        assert mapping_dir.is_dir()
        assert list(mapping_dir.glob("*.yaml")), (
            "icon-template-color-scheme-mappings must keep its *.yaml files"
        )


class TestSkeletonsAreStatic:
    def test_new_skeletons_have_no_template_suffix(self) -> None:
        """AC 1-4 guard: the three new skeleton files are STATIC — unlike the
        zsh `.zshrc.j2` and wlogout `style.css.tpl` templates, they must NOT
        carry a template suffix."""
        new_files = (_HYPR_CONF, _AGS_APP, _AGS_CSS, _HYPRPAPER_CONF)
        for path in new_files:
            assert not path.name.endswith(_TEMPLATE_SUFFIXES), (
                f"{path.name} must not use a template suffix ({_TEMPLATE_SUFFIXES})"
            )

    def test_skeleton_dirs_have_no_dash_and_no_config_suffix(self) -> None:
        """Naming contract: skeleton dirs are exactly hypr / ags /
        hyprpaper (no dash, no `.config` suffix) — they mirror the
        ~/.config/{hypr,ags,hyprpaper} targets Story 2.9 copies to."""
        assert (_CONFIG_DIR / "hypr").is_dir()
        assert (_CONFIG_DIR / "ags").is_dir()
        assert (_CONFIG_DIR / "hyprpaper").is_dir()
