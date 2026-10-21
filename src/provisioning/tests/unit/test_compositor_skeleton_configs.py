from __future__ import annotations

from pathlib import Path

import yaml

# S2: the static config corpus is NOT authored in this checkout any more — it
# ships in the pinned `dotfiles-assets` repo (`configs/` class) and the
# compositor_configs / config_copies roles read the checkout. The old
# byte-level assertions of this module (dofile wiring, hyprpaper's exact lines,
# the session PATH prepend) had the repo files as their subject; that subject
# moved with the bytes, so what remains here is the CONSUMER contract that no
# single role test states on its own:
#
#   1. every config source in both roles is the pinned checkout, at the tag the
#      assets manifest declares (no role-local pin drift, no repo tree);
#   2. the 15 compositor skeletons are exactly the configs-class files the
#      consumer addresses (an unregistered file silently never deploys);
#   3. the in-tree static corpus is gone, while the S3 template sources stay.
#
# The corpus's own content checks now belong to the assets repo (configs/README.md
# and the release acceptance grep); a consumer-side byte test would have to fetch
# the tag, which this suite deliberately does not do.


def _find_repo_root() -> Path:
    """Locate the repo root anchored on the assets manifest (the pin every config
    source derives from)."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "dotfiles" / "provisioning" / "assets.yaml").is_file():
            return parent
    raise FileNotFoundError(
        "dotfiles/provisioning/assets.yaml not found walking up from the test "
        "file; the config corpus pin is the subject of this module"
    )


_REPO_ROOT = _find_repo_root()
_ANSIBLE_DIR = _REPO_ROOT / "src" / "provisioning" / "ansible"
_ROLES_DIR = _ANSIBLE_DIR / "roles"
_CONFIG_DIR = _REPO_ROOT / "dotfiles" / "config"


def _vars(role: str) -> dict[str, object]:
    data = yaml.safe_load((_ROLES_DIR / role / "vars" / "main.yml").read_text())
    assert isinstance(data, dict)
    return data


def _assets_tag() -> str:
    manifest = yaml.safe_load(
        (_REPO_ROOT / "dotfiles" / "provisioning" / "assets.yaml").read_text()
    )
    return str(manifest["assets"]["tag"])


#: The 15 non-bar compositor skeletons, relative to the assets `configs/` class.
_EXPECTED_COMPOSITOR_FILES = {
    "hypr/animations.lua",
    "hypr/autostart.lua",
    "hypr/colors.lua",
    "hypr/cursor.lua",
    "hypr/decoration.lua",
    "hypr/env-variables.lua",
    "hypr/general.lua",
    "hypr/gloview.lua",
    "hypr/hyprland.lua",
    "hypr/input.lua",
    "hypr/keybindings.lua",
    "hypr/monitors.lua",
    "hypr/window-rules.lua",
    "hyprpaper/hyprpaper.conf",
    "rofi/launcher/config.rasi",
}

#: Retired in S2 (the copied corpus). wlogout's DIRECTORY stays: it keeps the
#: Jinja source until S3, so only its copied `layout` is retired.
_RETIRED_CONFIG_TREES = ("hypr", "hyprpaper", "nvim", "rofi", "starship")


class TestConfigCorpusPin:
    def test_compositor_sources_are_the_pinned_configs_class(self) -> None:
        data = _vars("compositor_configs")
        tag = _assets_tag()
        assert str(data["compositor_configs_assets_pinned_tag"]) == tag, (
            "the compositor config pin must equal dotfiles/provisioning/assets.yaml "
            "`assets.tag` — a role-local pin drifts silently"
        )
        prefix = (
            "{{ install_dir | trim }}/assets/"
            "{{ compositor_configs_assets_pinned_tag }}/configs/"
        )
        assert str(data["compositor_configs_assets_configs_dir"]) == prefix.rstrip("/")
        relative = {
            str(entry["source"]).split("}}/", 1)[1]
            for entry in data["compositor_configs_skeleton_files"]
        }
        assert relative == _EXPECTED_COMPOSITOR_FILES, (
            "the 15 compositor skeletons must be exactly the configs-class files "
            f"the consumer addresses; diff={relative ^ _EXPECTED_COMPOSITOR_FILES}"
        )
        for entry in data["compositor_configs_skeleton_files"]:
            assert str(entry["source"]).startswith(
                "{{ compositor_configs_assets_configs_dir }}/"
            ), entry["source"]
            assert "dotfiles/config" not in str(entry["source"])

    def test_config_copy_sources_are_the_pinned_configs_class(self) -> None:
        data = _vars("config_copies")
        assert str(data["config_copies_assets_pinned_tag"]) == _assets_tag()
        prefix = (
            "{{ install_dir | trim }}/assets/"
            "{{ config_copies_assets_pinned_tag }}/configs/"
        )
        assert str(data["config_copies_assets_configs_dir"]) == prefix.rstrip("/")
        entries = {str(entry["name"]): dict(entry) for entry in data["config_copies_entries"]}
        assert set(entries) == {"nvim", "starship", "wlogout"}, (
            "the copy set is nvim, starship and wlogout (S2 dropped zsh — its only "
            "file was a template nothing read)"
        )
        assert entries["wlogout"].get("files") == ["layout"], (
            "wlogout is per-file: style.css is RENDERED by wlogout_config"
        )


class TestRetiredConfigCorpus:
    def test_static_config_dirs_are_gone(self) -> None:
        for name in _RETIRED_CONFIG_TREES:
            assert not (_CONFIG_DIR / name).exists(), (
                f"dotfiles/config/{name}/ still exists — the static corpus is the "
                "pinned dotfiles-assets repo (configs class)"
            )

    def test_wlogout_keeps_only_its_template_source(self) -> None:
        wlogout = _CONFIG_DIR / "wlogout"
        assert wlogout.is_dir(), "wlogout/ must survive: it holds style.css.tpl until S3"
        assert not (wlogout / "layout").exists(), (
            "wlogout/layout is copied from the pinned corpus; an in-tree copy is a "
            "second source of truth"
        )
        assert (wlogout / "style.css.tpl").is_file(), (
            "style.css.tpl is S3's template source and must stay until S3 renders "
            "from the assets templates class"
        )

    def test_s3_sources_still_present(self) -> None:
        assert (_CONFIG_DIR / "zsh" / ".zshrc.j2").is_file(), (
            "zsh/.zshrc.j2 is S3's template source and must stay until S3"
        )
        assert (_CONFIG_DIR / "btop" / "active-theme").is_file(), (
            "btop/active-theme is host state and is not part of the S2 corpus"
        )
