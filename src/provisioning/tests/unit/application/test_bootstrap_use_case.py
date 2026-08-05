from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from provisioning.application import BootstrapUseCase
from provisioning.domain.models import ProvisionResult
from provisioning.ports import IFactReader, IProvisionExecutor


class FakeExecutor(IProvisionExecutor):
    def __init__(self, result: ProvisionResult) -> None:
        self._result = result
        self.calls: list[tuple[Path, bool, Mapping[str, str]]] = []

    def run(
        self,
        playbook: Path,
        check: bool,
        extra_vars: Mapping[str, str],
    ) -> ProvisionResult:
        self.calls.append((playbook, check, extra_vars))
        return self._result


class FakeFactReader(IFactReader):
    def __init__(self, family: str) -> None:
        self._family = family

    def os_family(self) -> str:
        return self._family


class TestBootstrapUseCase:
    def test_bootstrap_defaults_to_check_false(self) -> None:
        executor = FakeExecutor(ProvisionResult(success=True))
        use_case = BootstrapUseCase(
            executor=executor,
            fact_reader=FakeFactReader("arch"),
            playbook=Path("bootstrap.yaml"),
        )
        use_case.bootstrap()
        assert executor.calls[0][1] is False

    def test_bootstrap_with_check_true_passes_check_through(self) -> None:
        executor = FakeExecutor(ProvisionResult(success=True))
        use_case = BootstrapUseCase(
            executor=executor,
            fact_reader=FakeFactReader("arch"),
            playbook=Path("bootstrap.yaml"),
        )
        use_case.bootstrap(check=True)
        assert executor.calls[0][1] is True

    def test_default_playbook_is_bootstrap_yaml(self) -> None:
        executor = FakeExecutor(ProvisionResult(success=True))
        use_case = BootstrapUseCase(
            executor=executor,
            fact_reader=FakeFactReader("arch"),
        )
        use_case.bootstrap()
        assert executor.calls[0][0] == Path("bootstrap.yaml")

    def test_injected_playbook_is_passed_through(self) -> None:
        executor = FakeExecutor(ProvisionResult(success=True))
        use_case = BootstrapUseCase(
            executor=executor,
            fact_reader=FakeFactReader("arch"),
            playbook=Path("playbooks/bootstrap.yaml"),
        )
        use_case.bootstrap()
        assert executor.calls[0][0] == Path("playbooks/bootstrap.yaml")

    def test_extra_vars_carry_exactly_install_dir_and_os_family(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("XDG_DATA_HOME", "/home/user/.local/share")
        executor = FakeExecutor(ProvisionResult(success=True))
        use_case = BootstrapUseCase(
            executor=executor,
            fact_reader=FakeFactReader("debian-family"),
            playbook=Path("bootstrap.yaml"),
        )
        use_case.bootstrap()
        extra_vars = executor.calls[0][2]
        assert extra_vars == {
            "install_dir": str(Path("/home/user/.local/share/dotfiles")),
            "os_family": "debian-family",
        }
        assert set(extra_vars) == {"install_dir", "os_family"}

    def test_result_returned_unchanged(self) -> None:
        expected = ProvisionResult(success=False, tasks=(("packages : TASK", "failed"),))
        executor = FakeExecutor(expected)
        use_case = BootstrapUseCase(
            executor=executor,
            fact_reader=FakeFactReader("arch"),
            playbook=Path("bootstrap.yaml"),
        )
        result = use_case.bootstrap()
        assert result == expected
