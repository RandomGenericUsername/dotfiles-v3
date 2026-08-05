from __future__ import annotations

from abc import ABC
from pathlib import Path
from typing import cast

import pytest

from provisioning.domain.models import ProvisionManifest
from provisioning.ports import IManifestReader


class FakeManifestReader(IManifestReader):
    def __init__(self) -> None:
        self.last_path: Path | None = None

    def read(self, manifest_path: Path) -> ProvisionManifest:
        self.last_path = manifest_path
        return ProvisionManifest(kind="packages", entries=())


class TestIManifestReader:
    def test_is_abc(self) -> None:
        assert issubclass(IManifestReader, ABC)

    def test_read_is_abstract(self) -> None:
        assert IManifestReader.read.__isabstractmethod__  # type: ignore[attr-defined]

    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            IManifestReader()  # type: ignore[abstract]

    def test_unimplemented_method_raises_not_implemented_error(self) -> None:
        with pytest.raises(NotImplementedError):
            IManifestReader.read(cast(IManifestReader, None), Path("packages.yaml"))

    def test_fake_satisfies_contract(self) -> None:
        fake = FakeManifestReader()
        assert isinstance(fake, IManifestReader)
        manifest = fake.read(Path("packages.yaml"))
        assert isinstance(manifest, ProvisionManifest)
        assert manifest.kind == "packages"
        assert fake.last_path == Path("packages.yaml")
