"""Port abstraction for reading declarative provisioning manifests.

``IManifestReader`` parses one ``dotfiles/provisioning/*.yaml`` manifest into
a domain ``ProvisionManifest``. Concrete adapters live in
``provisioning.adapters`` (Story 1.5).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from provisioning.domain.models import ProvisionManifest


class IManifestReader(ABC):
    @abstractmethod
    def read(self, manifest_path: Path) -> ProvisionManifest:
        raise NotImplementedError
