"""Port abstraction for provisioning execution.

``IProvisionExecutor`` abstracts ``ansible-playbook``: run a playbook in plan
mode (``check=True``) or apply mode (``check=False``), passing the seam
extra-vars keys ``install_dir`` and ``os_family``. Concrete adapters live in
``provisioning.adapters`` (Story 1.5).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from pathlib import Path

from provisioning.domain.models import ProvisionResult


class IProvisionExecutor(ABC):
    @abstractmethod
    def run(
        self,
        playbook: Path,
        check: bool,
        extra_vars: Mapping[str, str],
    ) -> ProvisionResult:
        raise NotImplementedError
