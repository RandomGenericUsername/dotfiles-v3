from typing import Generic, TypeVar

from oci_runtime.domain.exceptions import ContainerRuntimeError, OciError
from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.parsers import (
    ContainerParser,
    ImageParser,
    NetworkParser,
    VolumeParser,
)
from oci_runtime.ports.transport import Transport

P = TypeVar("P", bound=ContainerParser | ImageParser | VolumeParser | NetworkParser)


class CliBaseManager(Generic[P]):
    """Base class for CLI-based managers, residing in the Adapters layer.

    This keeps the Ports layer (interfaces) pure by moving shared implementation
    logic for CLI command execution and result checking here.
    """

    _not_found_error: type[OciError]
    _generic_error: type[OciError] = ContainerRuntimeError
    _auth_error: type[OciError] | None = None

    def __init__(self, transport: Transport, parser: P, caps: RuntimeCapabilities):
        self._transport = transport
        self._parser = parser
        self._caps = caps

    def _decode_bytes(self, data: bytes) -> str:
        return data.decode("utf-8", errors="replace")

    def _execute_list(
        self,
        entity_type: str,
        subcommand: list[str],
        show_all: bool = False,
        filters: dict[str, str] | None = None,
    ) -> list:
        cmd = [self._transport.get_runtime_binary()] + subcommand
        cmd.extend(self._caps.list_format_flags)
        if show_all:
            cmd.append("-a")
        if filters:
            for key, val in filters.items():
                cmd.extend(["--filter", f"{key}={val}"])
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation=f"list {entity_type}", entity="")
        return self._parser.parse_list(self._decode_bytes(result.stdout))

    def _check_result(
        self,
        result: RawExecResult,
        cmd: list[str],
        *,
        operation: str = "execute command",
        entity: str = "",
        not_found: type[OciError] | None = None,
    ) -> None:
        if result.returncode == 0:
            return

        if not_found is None:
            not_found = self._not_found_error

        stderr_str = result.stderr.decode("utf-8", errors="replace")

        is_auth = getattr(self._parser, "is_auth_error", None)
        if self._auth_error is not None and is_auth is not None and is_auth(stderr_str):
            raise self._auth_error(entity)

        if self._parser.is_not_found_error(stderr_str):
            raise not_found(entity)

        message_parts = [f"Failed to {operation}"]
        if entity:
            message_parts.append(f"entity: {entity}")
        if stderr_str:
            message_parts.append(f"error: {stderr_str}")

        message = " | ".join(message_parts)

        raise self._generic_error(
            message=message,
            command=cmd,
            exit_code=result.returncode,
            stderr=stderr_str,
        )
