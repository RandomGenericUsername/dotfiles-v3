from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from provisioning.application import (
    BootstrapUseCase,
    ProvisionMachineUseCase,
    VerifyCapabilityUseCase,
)
from provisioning.domain.models import ProvisionResult
from provisioning.ports import IFactReader, IProvisionExecutor


class FakeExecutor(IProvisionExecutor):
    """Records (playbook, check, extra_vars) per run; raises ``error`` if set."""

    def __init__(self, result: ProvisionResult, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.calls: list[tuple[Path, bool, Mapping[str, str]]] = []

    def run(
        self,
        playbook: Path,
        check: bool,
        extra_vars: Mapping[str, str],
    ) -> ProvisionResult:
        self.calls.append((playbook, check, extra_vars))
        if self._error is not None:
            raise self._error
        return self._result


class FakeFactReader(IFactReader):
    def __init__(self, family: str = "arch") -> None:
        self._family = family

    def os_family(self) -> str:
        return self._family


class FakeDeps:
    """Composition-root substitute exposing real use cases over fake adapters.

    Each use case gets its own recording executor so tests can assert which
    command reached which use case with which ``check`` flag.
    """

    def __init__(self, result: ProvisionResult, error: Exception | None = None) -> None:
        plan_executor = FakeExecutor(result, error)
        apply_executor = FakeExecutor(result, error)
        verify_executor = FakeExecutor(result, error)
        bootstrap_executor = FakeExecutor(result, error)
        fact_reader = FakeFactReader()
        bootstrap_playbook = Path("bootstrap.yaml")
        verify_playbook = Path("verify.yaml")
        self.plan = ProvisionMachineUseCase(plan_executor, fact_reader, bootstrap_playbook)
        self.apply = ProvisionMachineUseCase(apply_executor, fact_reader, bootstrap_playbook)
        self.verify = VerifyCapabilityUseCase(verify_executor, fact_reader, verify_playbook)
        self.bootstrap = BootstrapUseCase(bootstrap_executor, fact_reader, bootstrap_playbook)
        self.plan_executor = plan_executor
        self.apply_executor = apply_executor
        self.verify_executor = verify_executor
        self.bootstrap_executor = bootstrap_executor


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _invoke(
    runner: CliRunner,
    deps: FakeDeps,
    args: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> Result:
    monkeypatch.setattr("provisioning.cli.main.build_deps", lambda: deps)
    from provisioning.cli.main import app

    return runner.invoke(app, args)
