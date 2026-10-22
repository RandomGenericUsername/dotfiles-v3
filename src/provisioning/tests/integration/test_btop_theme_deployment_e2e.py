"""btop-theme-deployment integration (capability `btop-theme-deployment`).

Runs the REAL `ansible-playbook btop-config.yaml` against a throwaway machine,
with the repo-owned active-theme setting and the authored-themes directory
pointed at temp locations via the role's own var seams (no repo mutation). Then
it runs the real btop binary on a pty to prove the selected authored theme is
what btop actually loads.

Covers: authored themes reach the spine, the active `color_theme` is the repo
setting, re-provisioning preserves the selection, `save_config_on_exit = false`,
and (end-to-end) a meter-fixed authored theme loads in btop.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.unit import assets_templates

pytestmark = pytest.mark.integration

_ANSIBLE_PLAYBOOK = shutil.which("ansible-playbook")
if _ANSIBLE_PLAYBOOK is None:
    pytest.skip(
        "ansible-playbook not on PATH; skipping the provisioned-machine gates",
        allow_module_level=True,
    )


def _find_ansible_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError("src/provisioning/ansible/ not found")


_ANSIBLE_DIR = _find_ansible_dir()
_PLAYBOOKS_DIR = _ANSIBLE_DIR / "playbooks"

# A meter-fixed authored theme (the "Reserve surface for meters" fix):
# meter_bg = surface, used_start raised to used_mid. A FULL 48-key theme is
# emitted (with a single fill colour for unspecified keys) so btop never falls
# back to Default_theme colours for keys the file omits — the application
# harness asserts zero Default-theme leak.
_AUTHORED = "btop-dusk.theme"
_KEYS = [
    "main_bg", "main_fg", "title", "hi_fg", "selected_bg", "selected_fg", "inactive_fg", "graph_text",
    "meter_bg", "proc_misc", "cpu_box", "mem_box", "net_box", "proc_box", "div_line",
    "temp_start", "temp_mid", "temp_end", "cpu_start", "cpu_mid", "cpu_end",
    "free_start", "free_mid", "free_end", "cached_start", "cached_mid", "cached_end",
    "available_start", "available_mid", "available_end", "used_start", "used_mid", "used_end",
    "download_start", "download_mid", "download_end", "upload_start", "upload_mid", "upload_end",
    "process_start", "process_mid", "process_end",
    "proc_pause_bg", "proc_follow_bg", "proc_banner_bg", "proc_banner_fg", "followed_bg", "followed_fg",
]
_FILL = "#3a4a5a"
_OVERRIDES = {
    "main_bg": "#101820",
    "main_fg": "#d8d0c0",
    "title": "#4aa5d8",
    "meter_bg": "#101820",
    "used_start": "#4aa5d8",
    "used_mid": "#4aa5d8",
    "used_end": "#9ad0e8",
}
_AUTHORED_BODY = "".join(
    f'theme[{key}]="{_OVERRIDES.get(key, _FILL)}"\n' for key in _KEYS
)


def _run_playbook(install: Path, home: Path, xdg: Path, setting: Path, authored: Path) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ANSIBLE_", "XDG_"))}
    env.update(
        {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(xdg),
            "ANSIBLE_CONFIG": str(_ANSIBLE_DIR / "ansible.cfg"),
        }
    )
    result = subprocess.run(
        [
            _ANSIBLE_PLAYBOOK,
            str(_PLAYBOOKS_DIR / "btop-config.yaml"),
            "-e",
            f"install_dir={install}",
            "-e",
            f"btop_config_active_theme_file={setting}",
            "-e",
            f"btop_config_authored_themes_repo_dir={authored}",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )
    assert result.returncode == 0, f"btop-config.yaml failed:\n{result.stdout}\n{result.stderr}"
    return result.stdout


def _parse_config(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip('"')
    return out


class TestAuthoredThemeDeployment:
    def test_selection_survives_reprovisioning_and_authored_theme_ships(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        xdg = tmp_path / "xdg"
        install = tmp_path / "install"
        for path in (home, xdg, install):
            path.mkdir(parents=True, exist_ok=True)
        # S3: btop.conf.j2 ships in the pinned assets corpus; seed the checkout the
        # assets playbook materializes before btop-config on the bootstrap chain.
        assets_templates.seed_install(install, "btop_config")
        setting = tmp_path / "active-theme"
        setting.write_text(f"{_AUTHORED}\n")
        authored = tmp_path / "btop-themes"
        authored.mkdir()
        (authored / _AUTHORED).write_text(_AUTHORED_BODY)

        first = _run_playbook(install, home, xdg, setting, authored)

        conf = _parse_config(install / "config/btop/btop.conf")
        assert conf["color_theme"] == _AUTHORED, (
            "the rendered btop.conf must select the repo-owned active-theme setting"
        )
        assert conf["save_config_on_exit"] == "false"
        assert (install / "config/btop/themes" / _AUTHORED).is_file(), (
            "the authored theme must be shipped into the spine themes dir btop scans"
        )
        # The generated pointer is runtime-owned: provisioning must not create it.
        assert not (install / "config/btop/themes/colors.btop.theme").exists()

        second = _run_playbook(install, home, xdg, setting, authored)
        assert "changed=0" in second, (
            "re-provisioning must be a no-op when the setting and themes are unchanged"
        )
        assert _parse_config(install / "config/btop/btop.conf")["color_theme"] == _AUTHORED, (
            "re-provisioning must preserve the active-theme selection"
        )

    def test_a_fixed_authored_theme_is_what_btop_loads(self, tmp_path: Path) -> None:
        """End-to-end (task 8.1): fork/fix -> save to repo -> re-provision ->
        btop loads the fixed theme by name."""
        btop = shutil.which("btop")
        if btop is None:
            pytest.skip("btop not installed; skipping the application gate")

        home = tmp_path / "home"
        xdg = tmp_path / "xdg"
        install = tmp_path / "install"
        state = tmp_path / "state"
        for path in (home, xdg, install, state):
            path.mkdir(parents=True, exist_ok=True)
        assets_templates.seed_install(install, "btop_config")
        setting = tmp_path / "active-theme"
        setting.write_text(f"{_AUTHORED}\n")
        authored = tmp_path / "btop-themes"
        authored.mkdir()
        (authored / _AUTHORED).write_text(_AUTHORED_BODY)

        _run_playbook(install, home, xdg, setting, authored)
        # config-links exposes the spine at the native XDG location btop reads.
        env = {k: v for k, v in os.environ.items() if not k.startswith(("ANSIBLE_", "XDG_"))}
        env.update(
            {
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(xdg),
                "ANSIBLE_CONFIG": str(_ANSIBLE_DIR / "ansible.cfg"),
            }
        )
        linked = subprocess.run(
            [_ANSIBLE_PLAYBOOK, str(_PLAYBOOKS_DIR / "config-links.yaml"), "-e", f"install_dir={install}"],
            capture_output=True,
            text=True,
            env=env,
            timeout=300,
        )
        assert linked.returncode == 0, linked.stdout + linked.stderr

        from tests.integration.btop_theme_harness import ThemeApplicationError, assert_theme_applied

        try:
            assert_theme_applied(
                config_home=xdg,
                state_home=state,
                theme_name=_AUTHORED,
                theme_file=install / "config/btop/themes" / _AUTHORED,
                binary=btop,
            )
        except ThemeApplicationError as error:  # pragma: no cover - environment dependent
            pytest.skip(f"btop could not run in this environment: {error}")
