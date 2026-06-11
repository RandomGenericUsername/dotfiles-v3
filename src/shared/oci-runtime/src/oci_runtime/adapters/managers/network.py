from oci_runtime.domain.exceptions import NetworkNotFoundError
from oci_runtime.domain.types import NetworkInfo
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.managers import NetworkManager
from oci_runtime.ports.parsers import NetworkParser
from oci_runtime.ports.transport import Transport
from oci_runtime.adapters.managers.base import CliBaseManager


class CliNetworkManager(CliBaseManager[NetworkParser], NetworkManager):
    def __init__(self, transport: Transport, parser: NetworkParser, caps: RuntimeCapabilities):
        super().__init__(transport, parser, caps)

    def create(self, name: str, driver: str = "bridge", labels: dict[str, str] | None = None) -> str:
        cmd = [self._transport.get_runtime_binary(), "network", "create", "--driver", driver, name]
        if labels:
            for k, v in labels.items():
                cmd.extend(["--label", f"{k}={v}"])
        result = self._transport.execute(cmd)
        return self._decode_stdout(result.stdout).strip()

    def remove(self, name: str) -> None:
        cmd = [self._transport.get_runtime_binary(), "network", "rm", name]
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="remove network", entity=name, not_found=NetworkNotFoundError)

    def connect(self, network: str, container: str) -> None:
        cmd = [self._transport.get_runtime_binary(), "network", "connect", network, container]
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="connect network", entity=network, not_found=NetworkNotFoundError)

    def disconnect(self, network: str, container: str, force: bool = False) -> None:
        cmd = [self._transport.get_runtime_binary(), "network", "disconnect", network, container]
        if force:
            cmd.append("-f")
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="disconnect network", entity=network, not_found=NetworkNotFoundError)

    def exists(self, name: str) -> bool:
        try:
            self.inspect(name)
            return True
        except NetworkNotFoundError:
            return False

    def inspect(self, name: str) -> NetworkInfo:
        cmd = [self._transport.get_runtime_binary(), "network", "inspect", name]
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, entity=name, not_found=NetworkNotFoundError)
        info = self._parser.parse_inspect(self._decode_stdout(result.stdout))
        if info is None:
            raise NetworkNotFoundError(name)
        return info

    def list(self, filters: dict[str, str] | None = None) -> list[NetworkInfo]:
        cmd = [self._transport.get_runtime_binary(), "network", "list"]
        if filters:
            for key, val in filters.items():
                cmd.extend(["--filter", f"{key}={val}"])
        result = self._transport.execute(cmd)
        return self._parser.parse_list(self._decode_stdout(result.stdout))

    def prune(self) -> dict[str, int]:
        cmd = [self._transport.get_runtime_binary(), "network", "prune", "--force"]
        result = self._transport.execute(cmd)
        return self._parser.parse_prune(self._decode_stdout(result.stdout))
