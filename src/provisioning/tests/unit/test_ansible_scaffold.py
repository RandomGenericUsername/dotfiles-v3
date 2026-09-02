from __future__ import annotations

import configparser
from pathlib import Path

import pytest
import yaml

from provisioning.domain.enums import Distro


def _find_ansible_dir() -> Path:
    """Locate the real ansible scaffold dir by walking up from this test file.

    Resolves the repo root robustly (no fixed-depth assumption) and fails
    loudly if the scaffold is missing, so AC 1-5 coverage can never silently
    disappear from the run. Anchored on ``pyproject.toml`` so a sibling
    project's ``ansible/`` tree in a shared workspace is never matched.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError(
        "src/provisioning/ansible/ not found walking up from the test file; "
        "AC 1-5 real-scaffold coverage requires the authored scaffold"
    )


_ANSIBLE_DIR = _find_ansible_dir()

_REQUIRED_FILES = (
    "inventory/localhost.yaml",
    "requirements.yml",
    "ansible.cfg",
    "group_vars/all.yml",
    "group_vars/arch.yml",
    "group_vars/debian-family.yml",
)

# Every logical key in the group_vars `packages` map (Story 2.1 parity lock).
# Shared base must be identical across arch.yml and debian-family.yml;
# distro-specific extras are pinned separately (gloview_build is Arch-only:
# cmake build deps for the gloview Hyprland plugin).
_LOGICAL_PACKAGE_KEYS = (
    "hyprland",
    "hyprpaper",
    "networkmanager",
    "wifitui",
    "wlogout",
    "librsvg",
    "uwsm",
    "ags",
    "fonts",
    "zsh",
    "terminal",
    "display_manager",
    "container_engine",
    "ffmpeg",
    "pipewire",
    "wireplumber",
    "gpu-screen-recorder",
    "wf-recorder",
    "btop",
    "thunderbird",
    "brightnessctl",
    "playerctl",
)
_ARCH_EXTRA_KEYS = ("gloview_build",)


class TestAnsibleScaffoldFilesExist:
    def test_required_scaffold_files_exist(self) -> None:
        for relative in _REQUIRED_FILES:
            assert (_ANSIBLE_DIR / relative).is_file(), f"missing {relative}"


class TestInventoryLocalhost:
    _PATH = _ANSIBLE_DIR / "inventory" / "localhost.yaml"

    def test_parses_and_targets_localhost(self) -> None:
        data = yaml.safe_load(self._PATH.read_text())
        localhost = data["all"]["hosts"]["localhost"]
        assert localhost["ansible_connection"] == "local"
        assert localhost["ansible_python_interpreter"] == "{{ ansible_playbook_python }}"

    def test_localhost_not_statically_grouped_by_distro(self) -> None:
        data = yaml.safe_load(self._PATH.read_text())
        all_hosts = data["all"]["hosts"]
        assert set(all_hosts.keys()) == {"localhost"}
        groups = data["all"].get("children", {})
        for distro in (Distro.ARCH.value, Distro.DEBIAN_FAMILY.value):
            assert distro not in groups, (
                f"localhost must not be statically placed under {distro} — "
                "group_vars sets would merge and break distro isolation"
            )
            assert distro not in data, (
                f"no top-level {distro} group may exist — a sibling of `all` "
                "containing localhost would merge group_vars sets undetected"
            )


class TestRequirementsYaml:
    _PATH = _ANSIBLE_DIR / "requirements.yml"

    def test_parses_and_declares_external_collections(self) -> None:
        data = yaml.safe_load(self._PATH.read_text())
        declared = {entry["name"] for entry in data["collections"]}
        assert declared == {"community.general", "ansible.posix", "kewlfft.aur"}
        for entry in data["collections"]:
            assert entry.get("version"), (
                f"collection {entry['name']} must pin a version for NFR-9 reproducibility"
            )


class TestAnsibleCfg:
    _PATH = _ANSIBLE_DIR / "ansible.cfg"

    def test_declares_inventory_and_roles_path(self) -> None:
        parser = configparser.ConfigParser()
        parser.read(self._PATH)
        assert parser.has_section("defaults")
        assert parser.get("defaults", "inventory") == "inventory/localhost.yaml"
        assert parser.get("defaults", "roles_path") == "roles"

    def test_ansible_resolves_relative_paths_from_cfg_dir(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pytest.importorskip("ansible.config.manager")
        monkeypatch.setenv("ANSIBLE_CONFIG", str(self._PATH))
        from ansible.config.manager import ConfigManager

        config = ConfigManager()
        assert config.get_config_value("CONFIG_FILE") == str(self._PATH)
        assert config.get_config_value("DEFAULT_HOST_LIST") == [
            str(_ANSIBLE_DIR / "inventory" / "localhost.yaml")
        ]
        assert config.get_config_value("DEFAULT_ROLES_PATH") == [str(_ANSIBLE_DIR / "roles")]


class TestGroupVars:
    def test_filenames_match_distro_seam_contract(self) -> None:
        files = sorted(
            p.stem
            for p in (_ANSIBLE_DIR / "group_vars").glob("*")
            if p.is_file() and p.suffix in (".yml", ".yaml")
        )
        assert files == sorted({"all"} | {d.value for d in Distro})

    @staticmethod
    def _packages_map(basename: str) -> dict[str, object]:
        data = yaml.safe_load((_ANSIBLE_DIR / "group_vars" / basename).read_text())
        packages = data["packages"]
        assert isinstance(packages, dict)
        return packages

    def test_all_yml_is_minimal_and_does_not_default_install_dir(self) -> None:
        data = yaml.safe_load((_ANSIBLE_DIR / "group_vars" / "all.yml").read_text())
        assert data is None or isinstance(data, dict)
        if isinstance(data, dict):
            assert "install_dir" not in data, (
                "install_dir must stay fail-loud (orchestrator seam always "
                "provides it via --extra-vars); all.yml must not default it"
            )

    def test_arch_packages_cover_exactly_logical_set(self) -> None:
        packages = self._packages_map("arch.yml")
        expected = set(_LOGICAL_PACKAGE_KEYS) | set(_ARCH_EXTRA_KEYS)
        assert set(packages.keys()) == expected

    def test_debian_family_packages_cover_exactly_logical_set(self) -> None:
        packages = self._packages_map("debian-family.yml")
        assert set(packages.keys()) == set(_LOGICAL_PACKAGE_KEYS)

    def test_arch_package_names_are_non_empty(self) -> None:
        packages = self._packages_map("arch.yml")
        for key, value in packages.items():
            names = value if isinstance(value, list) else [value]
            assert all(str(n).strip() for n in names), f"empty name under {key}"

    def test_debian_family_package_names_are_non_empty(self) -> None:
        packages = self._packages_map("debian-family.yml")
        for key, value in packages.items():
            names = value if isinstance(value, list) else [value]
            assert all(str(n).strip() for n in names), f"empty name under {key}"
