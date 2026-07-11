from __future__ import annotations

from oci_runtime.domain.encoding import safe_decode
from oci_runtime.domain.enums import Subcommand
from oci_runtime.domain.exceptions import NetworkNotFoundError
from oci_runtime.domain.types import NetworkInfo, PruneResult
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.list_executor import ListExecutor
from oci_runtime.ports.managers import NetworkManager
from oci_runtime.ports.parsers import NetworkParser
from oci_runtime.ports.result_checker import ResultChecker
from oci_runtime.ports.transport import Transport


class CliNetworkManager(NetworkManager):
    def __init__(
        self,
        transport: Transport,
        parser: NetworkParser,
        caps: RuntimeCapabilities,
        *,
        result_checker: ResultChecker,
        list_executor: ListExecutor[NetworkInfo],
    ):
        self._transport = transport
        self._parser = parser
        self._caps = caps
        self._result_checker = result_checker
        self._list_executor = list_executor

    def create(
        self, name: str, driver: str = "bridge", labels: dict[str, str] | None = None
    ) -> str:
        cmd = [
            self._transport.get_runtime_binary(),
            Subcommand.NETWORK.value,
            Subcommand.CREATE.value,
            "--driver",
            driver,
            name,
        ]
        if labels:
            for k, v in labels.items():
                cmd.extend(["--label", f"{k}={v}"])
        result = self._transport.execute(cmd)
        self._result_checker.check(result, cmd, operation="create network", entity=name)
        return safe_decode(result.stdout).strip()

    def remove(self, name: str) -> None:
        cmd = [
            self._transport.get_runtime_binary(),
            Subcommand.NETWORK.value,
            Subcommand.RM.value,
            name,
        ]
        result = self._transport.execute(cmd)
        self._result_checker.check(result, cmd, operation="remove network", entity=name)

    def connect(self, network: str, container: str) -> None:
        cmd = [
            self._transport.get_runtime_binary(),
            Subcommand.NETWORK.value,
            Subcommand.CONNECT.value,
            network,
            container,
        ]
        result = self._transport.execute(cmd)
        self._result_checker.check(
            result, cmd, operation="connect network", entity=network
        )

    def disconnect(self, network: str, container: str, force: bool = False) -> None:
        cmd = [
            self._transport.get_runtime_binary(),
            Subcommand.NETWORK.value,
            Subcommand.DISCONNECT.value,
            network,
            container,
        ]
        if force:
            cmd.append("-f")
        result = self._transport.execute(cmd)
        self._result_checker.check(
            result, cmd, operation="disconnect network", entity=network
        )

    def exists(self, name: str) -> bool:
        try:
            self.inspect(name)
            return True
        except NetworkNotFoundError:
            return False

    def inspect(self, name: str) -> NetworkInfo:
        cmd = [
            self._transport.get_runtime_binary(),
            Subcommand.NETWORK.value,
            Subcommand.INSPECT.value,
            "--format",
            "json",
            name,
        ]
        result = self._transport.execute(cmd)
        self._result_checker.check(
            result, cmd, operation="inspect network", entity=name
        )
        return self._parser.parse_inspect(safe_decode(result.stdout))

    def list(self, filters: dict[str, str] | None = None) -> list[NetworkInfo]:
        return self._list_executor.execute_list(
            [Subcommand.NETWORK.value, Subcommand.LIST.value],
            "networks",
            show_all=False,
            filters=filters,
        )

    def prune(self) -> PruneResult:
        cmd = [
            self._transport.get_runtime_binary(),
            Subcommand.NETWORK.value,
            Subcommand.PRUNE.value,
            "--force",
        ]
        result = self._transport.execute(cmd)
        self._result_checker.check(result, cmd, operation="prune networks", entity="")
        return self._parser.parse_prune(safe_decode(result.stdout))
