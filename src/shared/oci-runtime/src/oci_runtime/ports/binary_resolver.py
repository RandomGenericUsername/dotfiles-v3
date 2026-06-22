from abc import ABC, abstractmethod


class BinaryResolver(ABC):
    """Port: resolves a runtime binary name to an executable path.

    Caches the result so repeated calls do not re-invoke the syscall.
    Raises RuntimeNotAvailableError if the binary is not found.
    """

    @abstractmethod
    def resolve(self, binary: str) -> str:
        """Return the resolved path. Raises RuntimeNotAvailableError if not found."""
        ...

    @abstractmethod
    def is_available(self, binary: str) -> bool:
        """Return True if the binary is resolvable, False otherwise. Does not raise."""
        ...
