from typing import Generic, TypeVar

from oci_runtime.domain.exceptions import ContainerRuntimeError, OciError
from oci_runtime.domain.types import RawExecResult
from oci_runtime.domain.capabilities import RuntimeCapabilities
from oci_runtime.ports.parsers import ContainerParser, ImageParser, NetworkParser, VolumeParser
from oci_runtime.ports.transport import Transport

P = TypeVar("P", bound=ContainerParser | ImageParser | VolumeParser | NetworkParser)


class CliBaseManager(Generic[P]):
    """Base class for CLI-based managers, residing in the Adapters layer.
    
    This keeps the Ports layer (interfaces) pure by moving shared implementation 
    logic for CLI command execution and result checking here.
    """

    _not_found_error: type[OciError] = OciError
    _generic_error: type[OciError] = ContainerRuntimeError

    def __init__(self, transport: Transport, parser: P, caps: RuntimeCapabilities):
        self._transport = transport
        self._parser = parser
        self._caps = caps

    def _decode_bytes(self, data: bytes) -> str:
        return data.decode("utf-8", errors="replace")

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
