from abc import ABC, abstractmethod

from oci_runtime.domain.exceptions import OciError
from oci_runtime.domain.types import RawExecResult


class ResultChecker(ABC):
    @abstractmethod
    def check(
        self,
        result: RawExecResult,
        cmd: list[str],
        *,
        operation: str = "execute",
        entity: str = "",
        not_found_error: type[OciError] | None = None,
    ) -> None: ...
