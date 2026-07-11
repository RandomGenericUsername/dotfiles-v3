from __future__ import annotations

from oci_runtime.domain.encoding import safe_decode
from oci_runtime.domain.enums import Subcommand
from oci_runtime.domain.exceptions import VolumeNotFoundError
from oci_runtime.domain.types import VolumeInfo, PruneResult
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.list_executor import ListExecutor
from oci_runtime.ports.managers import VolumeManager
from oci_runtime.ports.parsers import VolumeParser
from oci_runtime.ports.result_checker import ResultChecker
from oci_runtime.ports.transport import Transport


class CliVolumeManager(VolumeManager):
    def __init__(
        self,
        transport: Transport,
        parser: VolumeParser,
        caps: RuntimeCapabilities,
        *,
        result_checker: ResultChecker,
        list_executor: ListExecutor[VolumeInfo],
    ):
        self._transport = transport
        self._parser = parser
        self._caps = caps
        self._result_checker = result_checker
        self._list_executor = list_executor

    def create(
        self, name: str, driver: str = "local", labels: dict[str, str] | None = None
    ) -> str:
        cmd = [
            self._transport.get_runtime_binary(),
            Subcommand.VOLUME.value,
            Subcommand.CREATE.value,
            "--driver",
            driver,
            name,
        ]
        if labels:
            for k, v in labels.items():
                cmd.extend(["--label", f"{k}={v}"])
        result = self._transport.execute(cmd)
        self._result_checker.check(result, cmd, operation="create volume", entity=name)
        return safe_decode(result.stdout).strip()

    def remove(self, name: str, force: bool = False) -> None:
        cmd = [
            self._transport.get_runtime_binary(),
            Subcommand.VOLUME.value,
            Subcommand.RM.value,
            name,
        ]
        if force:
            cmd.append("-f")
        result = self._transport.execute(cmd)
        self._result_checker.check(result, cmd, operation="remove volume", entity=name)

    def exists(self, name: str) -> bool:
        try:
            self.inspect(name)
            return True
        except VolumeNotFoundError:
            return False

    def inspect(self, name: str) -> VolumeInfo:
        cmd = [
            self._transport.get_runtime_binary(),
            Subcommand.VOLUME.value,
            Subcommand.INSPECT.value,
            "--format",
            "json",
            name,
        ]
        result = self._transport.execute(cmd)
        self._result_checker.check(result, cmd, operation="inspect volume", entity=name)
        return self._parser.parse_inspect(safe_decode(result.stdout))

    def list(self, filters: dict[str, str] | None = None) -> list[VolumeInfo]:
        return self._list_executor.execute_list(
            [Subcommand.VOLUME.value, Subcommand.LIST.value],
            "volumes",
            show_all=False,
            filters=filters,
        )

    def prune(self) -> PruneResult:
        cmd = [
            self._transport.get_runtime_binary(),
            Subcommand.VOLUME.value,
            Subcommand.PRUNE.value,
            "--force",
        ]
        result = self._transport.execute(cmd)
        self._result_checker.check(result, cmd, operation="prune volumes", entity="")
        return self._parser.parse_prune(safe_decode(result.stdout))
