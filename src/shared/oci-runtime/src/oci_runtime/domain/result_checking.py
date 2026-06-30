from collections.abc import Callable

from oci_runtime.domain.encoding import safe_decode
from oci_runtime.domain.exceptions import OciError
from oci_runtime.domain.types import RawExecResult


def check_cli_result(
    result: RawExecResult,
    cmd: list[str],
    *,
    operation: str = "execute",
    entity: str = "",
    not_found_error: type[OciError],
    generic_error: type[OciError],
    auth_error: type[OciError] | None = None,
    is_auth: Callable[[str], bool] | None = None,
    is_not_found: Callable[[str], bool],
) -> None:
    if result.returncode == 0:
        return
    stderr_str = safe_decode(result.stderr)
    if auth_error is not None and is_auth is not None and is_auth(stderr_str):
        raise auth_error(entity)
    if is_not_found(stderr_str):
        raise not_found_error(entity)
    raise generic_error(
        message=f"Failed to {operation} | {stderr_str}",
        command=cmd,
        exit_code=result.returncode,
        stderr=stderr_str,
    )
