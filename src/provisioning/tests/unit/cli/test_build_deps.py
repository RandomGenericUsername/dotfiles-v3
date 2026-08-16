from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from provisioning.adapters.ansible_executor import AnsibleExecutor
from provisioning.cli.main import _ANSIBLE_ROOT, build_deps


def _find_ansible_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError("src/provisioning/ansible/ not found")


_ANSIBLE_DIR = _find_ansible_dir()


def test_build_deps_uses_real_ansible_root() -> None:
    assert _ANSIBLE_ROOT == _ANSIBLE_DIR


def test_build_deps_wires_scaffold_config_file() -> None:
    deps = build_deps()
    executor = deps.plan._executor
    assert isinstance(executor, AnsibleExecutor)
    assert executor._config_file == _ANSIBLE_ROOT / "ansible.cfg"
    assert executor._config_file.is_file()


def test_build_deps_forwards_become_password_to_executor() -> None:
    deps = build_deps(become_password="secret")
    executor = deps.plan._executor
    assert isinstance(executor, AnsibleExecutor)
    assert executor._become_password == "secret"


def test_build_deps_defaults_become_password_to_none() -> None:
    deps = build_deps()
    executor = deps.plan._executor
    assert isinstance(executor, AnsibleExecutor)
    assert executor._become_password is None


def test_build_deps_executor_forwards_scaffold_ansible_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        captured["env"] = kwargs.get("env")
        return subprocess.CompletedProcess[str](args=command, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("provisioning.adapters.ansible_executor.subprocess.run", fake_run)
    deps = build_deps()
    executor = deps.plan._executor
    assert isinstance(executor, AnsibleExecutor)
    executor.run(
        _ANSIBLE_ROOT / "playbooks" / "bootstrap.yaml",
        check=True,
        extra_vars={"install_dir": "/x", "os_family": "arch"},
    )
    env = captured["env"]
    assert isinstance(env, dict)
    assert env["ANSIBLE_CONFIG"] == str(_ANSIBLE_ROOT / "ansible.cfg")
