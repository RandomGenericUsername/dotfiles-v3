from __future__ import annotations

from collections.abc import Callable

from oci_runtime.domain.exceptions import OciError
from oci_runtime.domain.result_checking import check_cli_result
from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.result_checker import ResultChecker


class CliResultChecker(ResultChecker):
    def __init__(
        self,
        generic_error: type[OciError],
        not_found_error: type[OciError],
        is_not_found: Callable[[str], bool],
        *,
        auth_error: type[OciError] | None = None,
        is_auth: Callable[[str], bool] | None = None,
    ):
        self._generic_error = generic_error
        self._not_found_error = not_found_error
        self._is_not_found = is_not_found
        self._auth_error = auth_error
        self._is_auth = is_auth

    def check(
        self,
        result: RawExecResult,
        cmd: list[str],
        *,
        operation: str = "execute",
        entity: str = "",
        not_found_error: type[OciError] | None = None,
    ) -> None:
        check_cli_result(
            result,
            cmd,
            operation=operation,
            entity=entity,
            not_found_error=not_found_error or self._not_found_error,
            generic_error=self._generic_error,
            auth_error=self._auth_error,
            is_auth=self._is_auth,
            is_not_found=self._is_not_found,
        )
