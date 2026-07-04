import pytest

from oci_runtime.domain.exceptions import (
    ContainerNotFoundError,
    ContainerRuntimeError,
    ImageNotFoundError,
    ImagePullAccessDeniedError,
)
from oci_runtime.domain.result_checking import check_cli_result
from oci_runtime.domain.types import RawExecResult


class _is_not_found:
    def __call__(self, stderr: str) -> bool:
        return "not found" in stderr.lower()


class _is_auth:
    def __call__(self, stderr: str) -> bool:
        return "denied" in stderr.lower() or "unauthorized" in stderr.lower()


class TestCheckCliResult:
    def test_success_returns_none(self):
        result = RawExecResult(returncode=0, stdout=b"ok", stderr=b"")
        assert (
            check_cli_result(
                result,
                cmd=["docker", "ps"],
                operation="list",
                entity="",
                not_found_error=ContainerNotFoundError,
                generic_error=ContainerRuntimeError,
                is_not_found=_is_not_found(),
            )
            is None
        )

    def test_not_found_raises_not_found_error(self):
        result = RawExecResult(returncode=1, stdout=b"", stderr=b"container not found")
        with pytest.raises(ContainerNotFoundError):
            check_cli_result(
                result,
                cmd=["docker", "inspect"],
                entity="abc123",
                not_found_error=ContainerNotFoundError,
                generic_error=ContainerRuntimeError,
                is_not_found=_is_not_found(),
            )

    def test_access_denied_raises_auth_error(self):
        result = RawExecResult(
            returncode=1, stdout=b"", stderr=b"pull access denied for image"
        )
        with pytest.raises(ImagePullAccessDeniedError):
            check_cli_result(
                result,
                cmd=["docker", "pull"],
                entity="private/image",
                operation="pull",
                not_found_error=ImageNotFoundError,
                generic_error=ContainerRuntimeError,
                auth_error=ImagePullAccessDeniedError,
                is_auth=_is_auth(),
                is_not_found=_is_not_found(),
            )

    def test_other_error_raises_generic_error(self):
        result = RawExecResult(returncode=2, stdout=b"", stderr=b"some random error")
        with pytest.raises(ContainerRuntimeError):
            check_cli_result(
                result,
                cmd=["docker", "run"],
                operation="run",
                entity="",
                not_found_error=ContainerNotFoundError,
                generic_error=ContainerRuntimeError,
                is_not_found=_is_not_found(),
            )

    def test_generic_error_includes_stderr_and_exit_code(self):
        result = RawExecResult(returncode=137, stdout=b"", stderr=b"OOM killed")
        with pytest.raises(ContainerRuntimeError) as exc:
            check_cli_result(
                result,
                cmd=["docker", "run"],
                operation="run",
                entity="",
                not_found_error=ContainerNotFoundError,
                generic_error=ContainerRuntimeError,
                is_not_found=_is_not_found(),
            )
        assert "OOM killed" in str(exc.value)
