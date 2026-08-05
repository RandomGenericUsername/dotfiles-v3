from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

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


class RaisingExecutor(IProvisionExecutor):
    def run(
        self,
        playbook: Path,
        check: bool,
        extra_vars: Mapping[str, str],
    ) -> ProvisionResult:
        raise RuntimeError("boom")


class FakeFactReader(IFactReader):
    def __init__(self, family: str) -> None:
        self._family = family

    def os_family(self) -> str:
        return self._family
