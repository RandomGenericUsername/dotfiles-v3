from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from oci_runtime.domain.list_command import build_list_command
from oci_runtime.domain.encoding import safe_decode
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.list_executor import ListExecutor
from oci_runtime.ports.result_checker import ResultChecker
from oci_runtime.ports.transport import Transport

T = TypeVar("T")


class CliListExecutor(ListExecutor[T]):
    def __init__(
        self,
        transport: Transport,
        caps: RuntimeCapabilities,
        result_checker: ResultChecker,
        parse_list: Callable[[str], list[T]],
    ):
        self._transport = transport
        self._caps = caps
        self._result_checker = result_checker
        self._parse_list = parse_list

    def execute_list(
        self,
        subcommand: list[str],
        entity_type: str,
        *,
        show_all: bool = False,
        filters: dict[str, str] | None = None,
    ) -> list[T]:
        cmd = build_list_command(
            self._transport.get_runtime_binary(),
            subcommand,
            self._caps.list_format_flags,
            show_all,
            filters,
        )
        result = self._transport.execute(cmd)
        self._result_checker.check(
            result,
            cmd,
            operation=f"list {entity_type}",
        )
        return self._parse_list(safe_decode(result.stdout))
