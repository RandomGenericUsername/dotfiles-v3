from __future__ import annotations

from pathlib import Path

import pytest

from provisioning.application import VerifyCapabilityUseCase
from provisioning.domain.models import ProvisionResult
from tests.unit.application.conftest import FakeExecutor, FakeFactReader, RaisingExecutor


class TestVerifyCapabilityUseCase:
    def test_verify_runs_executor_with_check_false(self) -> None:
        executor = FakeExecutor(ProvisionResult(success=True))
        use_case = VerifyCapabilityUseCase(
            executor=executor,
            fact_reader=FakeFactReader("arch"),
            playbook=Path("verify.yaml"),
        )
        use_case.verify()
        assert len(executor.calls) == 1
        assert executor.calls[0][1] is False

    def test_default_playbook_is_verify_yaml(self) -> None:
        executor = FakeExecutor(ProvisionResult(success=True))
        use_case = VerifyCapabilityUseCase(
            executor=executor,
            fact_reader=FakeFactReader("arch"),
        )
        use_case.verify()
        assert len(executor.calls) == 1
        assert executor.calls[0][0] == Path("verify.yaml")

    def test_injected_playbook_is_passed_through(self) -> None:
        executor = FakeExecutor(ProvisionResult(success=True))
        use_case = VerifyCapabilityUseCase(
            executor=executor,
            fact_reader=FakeFactReader("arch"),
            playbook=Path("playbooks/verify.yaml"),
        )
        use_case.verify()
        assert len(executor.calls) == 1
        assert executor.calls[0][0] == Path("playbooks/verify.yaml")

    def test_extra_vars_carry_exactly_install_dir_and_os_family(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("XDG_DATA_HOME", "/home/user/.local/share")
        executor = FakeExecutor(ProvisionResult(success=True))
        use_case = VerifyCapabilityUseCase(
            executor=executor,
            fact_reader=FakeFactReader("debian-family"),
            playbook=Path("verify.yaml"),
        )
        use_case.verify()
        assert len(executor.calls) == 1
        extra_vars = executor.calls[0][2]
        assert extra_vars == {
            "install_dir": str(Path("/home/user/.local/share/dotfiles")),
            "os_family": "debian-family",
        }
        assert set(extra_vars) == {"install_dir", "os_family"}

    def test_result_returned_unchanged(self) -> None:
        expected = ProvisionResult(
            success=False,
            tasks=(("verify : assert preconditions", "failed"),),
            returncode=3,
            stderr="fatal: [localhost]: FAILED!",
        )
        executor = FakeExecutor(expected)
        use_case = VerifyCapabilityUseCase(
            executor=executor,
            fact_reader=FakeFactReader("arch"),
            playbook=Path("verify.yaml"),
        )
        result = use_case.verify()
        assert len(executor.calls) == 1
        assert result == expected

    def test_executor_errors_propagate(self) -> None:
        use_case = VerifyCapabilityUseCase(
            executor=RaisingExecutor(),
            fact_reader=FakeFactReader("arch"),
            playbook=Path("verify.yaml"),
        )
        with pytest.raises(RuntimeError, match="boom"):
            use_case.verify()
