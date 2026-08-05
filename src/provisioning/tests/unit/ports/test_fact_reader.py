from __future__ import annotations

from abc import ABC
from typing import cast

import pytest

from provisioning.ports import IFactReader


class FakeFactReader(IFactReader):
    def os_family(self) -> str:
        return "arch"


class TestIFactReader:
    def test_is_abc(self) -> None:
        assert issubclass(IFactReader, ABC)

    def test_os_family_is_abstract(self) -> None:
        assert IFactReader.os_family.__isabstractmethod__  # type: ignore[attr-defined]

    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            IFactReader()  # type: ignore[abstract]

    def test_unimplemented_method_raises_not_implemented_error(self) -> None:
        with pytest.raises(NotImplementedError):
            IFactReader.os_family(cast(IFactReader, None))

    def test_fake_satisfies_contract(self) -> None:
        fake = FakeFactReader()
        assert isinstance(fake, IFactReader)
        assert fake.os_family() == "arch"
