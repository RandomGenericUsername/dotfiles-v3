from oci_runtime.ports.parsers import ParsingError
from oci_runtime.domain.exceptions import VolumeNotFoundError
from oci_runtime.domain.types import VolumeInfo
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.managers import VolumeManager
from oci_runtime.ports.parsers import VolumeParser
from oci_runtime.ports.transport import Transport
from oci_runtime.adapters.managers.base import CliBaseManager


class CliVolumeManager(CliBaseManager[VolumeParser], VolumeManager):
    def __init__(self, transport: Transport, parser: VolumeParser, caps: RuntimeCapabilities):
        super().__init__(transport, parser, caps)

    def create(self, name: str, driver: str = "local", labels: dict[str, str] | None = None) -> str:
        cmd = [self._transport.get_runtime_binary(), "volume", "create", "--driver", driver, name]
        if labels:
            for k, v in labels.items():
                cmd.extend(["--label", f"{k}={v}"])
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="create volume", entity=name, not_found=VolumeNotFoundError)
        return self._decode_stdout(result.stdout).strip()

    def remove(self, name: str, force: bool = False) -> None:
        cmd = [self._transport.get_runtime_binary(), "volume", "rm", name]
        if force:
            cmd.append("-f")
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="remove volume", entity=name, not_found=VolumeNotFoundError)

    def exists(self, name: str) -> bool:
        try:
            self.inspect(name)
            return True
        except (VolumeNotFoundError, ParsingError):
            return False

    def inspect(self, name: str) -> VolumeInfo:
        cmd = [self._transport.get_runtime_binary(), "volume", "inspect", "--format", "json", name]
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="inspect volume", entity=name, not_found=VolumeNotFoundError)
        return self._parser.parse_inspect(self._decode_stdout(result.stdout))

    def list(self, filters: dict[str, str] | None = None) -> list[VolumeInfo]:
        cmd = [self._transport.get_runtime_binary(), "volume", "list"]
        cmd.extend(self._caps.list_format_flags)
        if filters:
            for key, val in filters.items():
                cmd.extend(["--filter", f"{key}={val}"])
        result = self._transport.execute(cmd)
        return self._parser.parse_list(self._decode_stdout(result.stdout))

    def prune(self) -> dict[str, int]:
        cmd = [self._transport.get_runtime_binary(), "volume", "prune", "--force"]
        result = self._transport.execute(cmd)
        return self._parser.parse_prune(self._decode_stdout(result.stdout))
