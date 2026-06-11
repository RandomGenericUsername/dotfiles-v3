from typing import Any, Generic, Type, TypeVar

from oci_runtime.domain.exceptions import ContainerError, ContainerRuntimeError
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.transport import ExecResult, Transport

P = TypeVar("P")


class CliBaseManager(Generic[P]):
    """Base class for CLI-based managers, residing in the Adapters layer.
    
    This keeps the Ports layer (interfaces) pure by moving shared implementation 
    logic for CLI command execution and result checking here.
    """

    def __init__(self, transport: Transport, parser: P, caps: RuntimeCapabilities):
        self._transport = transport
        self._parser = parser
        self._caps = caps

    def _decode_stdout(self, data: bytes) -> str:
        return data.decode("utf-8", errors="replace")

    def _resolve_val(self, val: Any) -> str:
        """Safely extract string from Enum or raw string."""
        if val is None:
            return ""
        if hasattr(val, "value"):
            return str(val.value)
        return str(val)

    def _check_result(
        self,
        result: ExecResult,
        cmd: list[str],
        *,
        operation: str = "execute command",
        entity: str = "",
        not_found: Type[ContainerError],
    ) -> None:
        if result.returncode == 0:
            return

        stderr_str = result.stderr.decode("utf-8", errors="replace")

        if self._parser.is_not_found_error(stderr_str):
            raise not_found(entity)

        message_parts = [f"Failed to {operation}"]
        if entity:
            message_parts.append(f"entity: {entity}")
        if stderr_str:
            message_parts.append(f"error: {stderr_str}")

        message = " | ".join(message_parts)

        raise ContainerRuntimeError(
            message=message,
            command=cmd,
            exit_code=result.returncode,
            stderr=stderr_str,
        )
