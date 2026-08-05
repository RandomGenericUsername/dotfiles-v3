from __future__ import annotations

from abc import ABC
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import pytest

from provisioning.domain.models import ProvisionResult
from provisioning.ports import IProvisionExecutor


class FakeExecutor(IProvisionExecutor):
    def __init__(self) -> None:
        self.calls: list[tuple[Path, bool, Mapping[str, str]]] = []

    def run(
        self,
        playbook: Path,
        check: bool,
        extra_vars: Mapping[str, str],
    ) -> ProvisionResult:
        self.calls.append((playbook, check, extra_vars))
        return ProvisionResult(success=True, tasks=())


class TestIProvisionExecutor:
    def test_is_abc(self) -> None:
        assert issubclass(IProvisionExecutor, ABC)

    def test_run_is_abstract(self) -> None:
        assert IProvisionExecutor.run.__isabstractmethod__  # type: ignore[attr-defined]

    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            IProvisionExecutor()  # type: ignore[abstract]

    def test_unimplemented_method_raises_not_implemented_error(self) -> None:
        with pytest.raises(NotImplementedError):
            IProvisionExecutor.run(
                cast(IProvisionExecutor, None),
                Path("bootstrap.yaml"),
                True,
                {},
            )

    def test_fake_satisfies_contract(self) -> None:
        fake = FakeExecutor()
        assert isinstance(fake, IProvisionExecutor)
        result = fake.run(
            Path("bootstrap.yaml"),
            check=True,
            extra_vars={"os_family": "arch"},
        )
        assert isinstance(result, ProvisionResult)
        assert result.success is True
        assert fake.calls == [(Path("bootstrap.yaml"), True, {"os_family": "arch"})]
