from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml


def _find_ansible_dir() -> Path:
    """Locate the real ansible scaffold dir by walking up from this test file.

    Mirrors the sibling role test files: anchored on ``pyproject.toml`` so the
    sibling project's ``ansible/`` tree in a shared workspace is never matched.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError(
        "src/provisioning/ansible/ not found walking up from the test file; "
        "AC 4-5 real-scaffold coverage requires the authored playbook"
    )


_ANSIBLE_DIR = _find_ansible_dir()
_PLAYBOOKS_DIR = _ANSIBLE_DIR / "playbooks"

# The exact dependency order (plan §11 step 7, story 2.12 AC 4, Epic 4):
# packages first (system packages), verify last (done-criteria assert).
# Epic 4: default-palette.yaml + icons.yaml deleted (runtime owns all
# generation); runtime-seed.yaml (wallpaper set default.png) runs after
# config-links, before display-manager/verify. gloview-plugin.yaml runs after
# display-manager, before verify: it owns the GloView build/load lifecycle
# behind the provision-owned touchpad gestures. Each imported playbook
# keeps its OWN hosts/become/gather_facts/group_by — the aggregate is
# imports-only.
_EXPECTED_ORDER = [
    "packages.yaml",
    "cli-tools.yaml",
    "filesystem.yaml",
    "assets.yaml",
    "compositor-configs.yaml",
    "config-copies.yaml",
    "settings.yaml",
    "zsh-tools.yaml",
    "zsh-config.yaml",
    "wlogout-config.yaml",
    "config-links.yaml",
    "runtime-seed.yaml",
    "display-manager.yaml",
    "gloview-plugin.yaml",
    "verify.yaml",
]


def _load_imports() -> list[dict[str, object]]:
    data = yaml.safe_load((_PLAYBOOKS_DIR / "bootstrap.yaml").read_text())
    assert isinstance(data, list)
    return [dict(entry) for entry in data]


class TestBootstrapPlaybook:
    _PATH = _PLAYBOOKS_DIR / "bootstrap.yaml"

    def test_parses_as_list_of_import_playbook_entries(self) -> None:
        """The aggregate is a top-level list of exactly fifteen `import_playbook`
        statements (one per per-role playbook + the runtime-seed step + the
        gloview-plugin lifecycle)."""
        imports = _load_imports()
        assert len(imports) == 15, (
            f"bootstrap.yaml must import exactly 15 playbooks; found {len(imports)}"
        )
        for entry in imports:
            assert "import_playbook" in entry, (
                f"every top-level entry must be an import_playbook statement; got {entry}"
            )

    def test_imports_in_exact_dependency_order(self) -> None:
        """AC 4: the fifteen imports appear in the EXACT dependency order —
        packages → cli-tools → filesystem → assets →
        compositor-configs → config-copies → settings → zsh-tools →
        zsh-config → wlogout-config → config-links → runtime-seed →
        display-manager → gloview-plugin → verify (Epic 4: no default-palette/icons)."""
        order = [str(entry["import_playbook"]) for entry in _load_imports()]
        assert order == _EXPECTED_ORDER, (
            f"bootstrap.yaml import order must be {_EXPECTED_ORDER}; got {order}"
        )

    def test_verify_is_last_import(self) -> None:
        """The aggregate must end with verify.yaml — done-criteria are asserted
        AFTER every role placed its outputs."""
        imports = _load_imports()
        assert str(imports[-1]["import_playbook"]) == "verify.yaml", (
            "verify.yaml must be the LAST import of bootstrap.yaml"
        )

    def test_each_imported_playbook_exists(self) -> None:
        """Every referenced playbook must exist under playbooks/ — a typo'd
        import fails only at parse time, never at test time, otherwise."""
        for entry in _load_imports():
            target = _PLAYBOOKS_DIR / str(entry["import_playbook"])
            assert target.is_file(), (
                f"imported playbook {entry['import_playbook']} missing from playbooks/"
            )

    def test_no_top_level_play_keys(self) -> None:
        """The aggregate is imports-only: NO top-level hosts/roles/tasks keys
        (a flattened play would mix become:true packages with user-scoped
        roles and break the locked privilege contract)."""
        for entry in _load_imports():
            assert "hosts" not in entry, (
                f"import entry {entry} must not declare hosts (imports-only aggregate)"
            )
            assert "roles" not in entry
            assert "tasks" not in entry

    def test_syntax_check_exits_zero(self) -> None:
        """The aggregate parses recursively (import_playbook reads each imported
        playbook at parse time). NOTE: we do NOT run a full bootstrap.yaml
        --check here — the end-to-end dry-run integration tests are Story 3.2
        (test_ansible_dryrun.py); this locks structure + syntax only."""
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping syntax-check")
        env = dict(os.environ)
        env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")
        result = subprocess.run(
            [
                ansible_playbook,
                "--syntax-check",
                str(self._PATH),
                "-e",
                "install_dir=/tmp/x",
                "-e",
                "os_family=arch",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr
