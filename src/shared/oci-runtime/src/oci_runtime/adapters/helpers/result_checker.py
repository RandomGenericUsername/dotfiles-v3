from collections.abc import Callable

from oci_runtime.domain.encoding import safe_decode
from oci_runtime.domain.exceptions import OciError
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
        if result.returncode == 0:
            return
        not_found_error = not_found_error or self._not_found_error
        stderr_str = safe_decode(result.stderr)

        if self._auth_error and self._is_auth and self._is_auth(stderr_str):
            raise self._auth_error(
                entity,
                command=cmd,
                exit_code=result.returncode,
                stderr=stderr_str,
            )

        if self._is_not_found(stderr_str):
            raise not_found_error(entity)

        raise self._generic_error(
            message=f"Failed to {operation} | {stderr_str}",
            command=cmd,
            exit_code=result.returncode,
            stderr=stderr_str,
        )
