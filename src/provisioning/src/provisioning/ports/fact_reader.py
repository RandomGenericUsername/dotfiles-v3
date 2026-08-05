"""Port abstraction for the OS-family seam.

``IFactReader.os_family()`` returns the ``group_vars`` basename that applies
on the target machine (``"arch"`` | ``"debian-family"``, matching the domain
``Distro`` values). It only selects which ``group_vars`` apply — it never
inspects packages. Concrete adapters live in ``provisioning.adapters``
(Story 1.5).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IFactReader(ABC):
    @abstractmethod
    def os_family(self) -> str:
        raise NotImplementedError
