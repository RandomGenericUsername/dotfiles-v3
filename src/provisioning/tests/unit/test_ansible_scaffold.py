from __future__ import annotations

import configparser
from pathlib import Path

import yaml

from provisioning.domain.enums import Distro


def _find_ansible_dir() -> Path:
    """Locate the real ansible scaffold dir by walking up from this test file.

    Resolves the repo root robustly (no fixed-depth assumption) and fails
    loudly if the scaffold is missing, so AC 1-5 coverage can never silently
    disappear from the run.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file():
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

# Every logical entry in dotfiles/provisioning/packages.yaml (Story 2.1).
_LOGICAL_PACKAGE_KEYS = ("hyprland", "hyprpaper", "waybar", "fonts")


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
        assert localhost["ansible_host"] == "127.0.0.1"
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


class TestRequirementsYaml:
    _PATH = _ANSIBLE_DIR / "requirements.yml"

    def test_parses_and_declares_external_collections(self) -> None:
        data = yaml.safe_load(self._PATH.read_text())
        declared = {entry["name"] for entry in data["collections"]}
        assert {"community.general", "ansible.posix", "kewlfft.aur"} <= declared


class TestAnsibleCfg:
    _PATH = _ANSIBLE_DIR / "ansible.cfg"

    def test_declares_inventory_and_roles_path(self) -> None:
        parser = configparser.ConfigParser()
        parser.read(self._PATH)
        assert parser.has_section("defaults")
        assert parser.get("defaults", "inventory") == "inventory/localhost.yaml"
        assert parser.get("defaults", "roles_path") == "roles"


class TestGroupVars:
    def test_filenames_match_distro_seam_contract(self) -> None:
        files = sorted(p.stem for p in (_ANSIBLE_DIR / "group_vars").glob("*.yml"))
        assert files == sorted({"all"} | {d.value for d in Distro})

    @staticmethod
    def _packages_map(basename: str) -> dict[str, object]:
        data = yaml.safe_load((_ANSIBLE_DIR / "group_vars" / basename).read_text())
        packages = data["packages"]
        assert isinstance(packages, dict)
        return packages

    def test_arch_packages_cover_logical_set(self) -> None:
        packages = self._packages_map("arch.yml")
        for key in _LOGICAL_PACKAGE_KEYS:
            assert key in packages, f"arch.yml missing logical entry {key}"

    def test_debian_family_packages_cover_logical_set(self) -> None:
        packages = self._packages_map("debian-family.yml")
        for key in _LOGICAL_PACKAGE_KEYS:
            assert key in packages, f"debian-family.yml missing logical entry {key}"

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
