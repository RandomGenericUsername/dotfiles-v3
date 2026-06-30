import shutil

from oci_runtime.domain.exceptions import RuntimeNotAvailableError
from oci_runtime.ports.binary_resolver import BinaryResolver


class CliBinaryResolver(BinaryResolver):
    """Adapter: caches shutil.which results per binary name."""

    def __init__(self) -> None:
        self._cache: dict[str, str | None] = {}

    def resolve(self, binary: str) -> str:
        if binary not in self._cache:
            self._cache[binary] = shutil.which(binary)
        path = self._cache[binary]
        if path is None:
            raise RuntimeNotAvailableError(binary)
        return path

    def is_available(self, binary: str) -> bool:
        if binary not in self._cache:
            self._cache[binary] = shutil.which(binary)
        return self._cache[binary] is not None
