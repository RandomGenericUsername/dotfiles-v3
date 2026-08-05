from __future__ import annotations

import subprocess
from pathlib import Path

from provisioning.adapters.ansible_executor import AnsibleExecutor
from provisioning.domain.models import ProvisionResult


def _completed(returncode: int = 0, stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess[str](
        args=["ansible-playbook"],
        returncode=returncode,
        stdout=stdout,
        stderr="",
    )


class TestAnsibleExecutor:
    def _executor(
        self,
        commands: list[list[str]],
        *,
        returncode: int = 0,
        stdout: str = "",
    ) -> AnsibleExecutor:
        def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            return _completed(returncode, stdout)

        return AnsibleExecutor(
            inventory=Path("inventory/localhost.yaml"),
            tags="all",
            runner=runner,
        )

    def test_check_flag_present_when_check_true(self) -> None:
        commands: list[list[str]] = []
        executor = self._executor(commands)
        executor.run(
            Path("bootstrap.yaml"),
            check=True,
            extra_vars={"install_dir": "/x", "os_family": "arch"},
        )
        assert "--check" in commands[0]

    def test_check_flag_absent_when_check_false(self) -> None:
        commands: list[list[str]] = []
        executor = self._executor(commands)
        executor.run(Path("bootstrap.yaml"), check=False, extra_vars={})
        assert "--check" not in commands[0]

    def test_inventory_tags_and_playbook_present(self) -> None:
        commands: list[list[str]] = []
        executor = self._executor(commands)
        executor.run(Path("playbooks/packages.yaml"), check=True, extra_vars={})
        command = commands[0]
        assert command[0] == "ansible-playbook"
        assert command[command.index("-i") + 1] == "inventory/localhost.yaml"
        assert command[command.index("--tags") + 1] == "all"
        assert command[-1] == "playbooks/packages.yaml"

    def test_extra_vars_carry_exactly_install_dir_and_os_family(self) -> None:
        commands: list[list[str]] = []
        executor = self._executor(commands)
        executor.run(
            Path("bootstrap.yaml"),
            check=True,
            extra_vars={"install_dir": "/x", "os_family": "arch"},
        )
        command = commands[0]
        extra_vars = command[command.index("--extra-vars") + 1]
        keys = [token.split("=", 1)[0] for token in extra_vars.split()]
        assert keys == ["install_dir", "os_family"]

    def test_parses_tasks_from_stdout(self) -> None:
        stdout = (
            "PLAY [Provision localhost]\n\n"
            "TASK [packages : install hyprland] *************************\n"
            "changed: [localhost]\n\n"
            "TASK [packages : install waybar] ****************************\n"
            "ok: [localhost]\n\n"
            "PLAY RECAP ***************************************************\n"
            "localhost : ok=1 changed=1 unreachable=0 failed=0\n"
        )
        commands: list[list[str]] = []
        executor = self._executor(commands, stdout=stdout)
        result = executor.run(Path("bootstrap.yaml"), check=True, extra_vars={})
        assert result.tasks == (
            ("packages : install hyprland", "changed"),
            ("packages : install waybar", "ok"),
        )

    def test_zero_returncode_yields_success(self) -> None:
        commands: list[list[str]] = []
        executor = self._executor(commands, returncode=0)
        result = executor.run(Path("bootstrap.yaml"), check=True, extra_vars={})
        assert result is not None
        assert isinstance(result, ProvisionResult)
        assert result.success is True

    def test_non_zero_returncode_yields_success_false(self) -> None:
        commands: list[list[str]] = []
        executor = self._executor(commands, returncode=2)
        result = executor.run(Path("bootstrap.yaml"), check=True, extra_vars={})
        assert result.success is False
