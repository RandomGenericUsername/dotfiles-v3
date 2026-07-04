from collections.abc import Callable
from dataclasses import dataclass, replace

from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.domain.types import RuntimePreference
from oci_runtime.factory import (
    ResolvedRuntimeFactoryConfig,
    RuntimeFactory,
    RuntimeFactoryConfig,
    _resolve_config,
)
from oci_runtime.ports.binary_resolver import BinaryResolver
from oci_runtime.ports.cancellation import CancellationToken
from oci_runtime.ports.engine import ContainerEngine
from oci_runtime.ports.list_executor import ListExecutor
from oci_runtime.ports.output_stream import OutputStream
from oci_runtime.ports.provider import RuntimeProvider
from oci_runtime.ports.pty_transport import PtyTransport
from oci_runtime.ports.result_checker import ResultChecker
from oci_runtime.ports.streaming import StreamingTransport
from oci_runtime.ports.transport import Transport
from oci_runtime.ports.tty import TtyDetector


@dataclass(frozen=True)
class EngineBuildResult:
    engine: ContainerEngine
    resolved_config: ResolvedRuntimeFactoryConfig


class OciRuntimeBuilder:
    def __init__(self) -> None:
        self._config = RuntimeFactoryConfig()
        self._kind: RuntimeKind = RuntimeKind.DOCKER
        self._binary: str = "docker"
        self._providers: dict[RuntimeKind, RuntimeProvider] | None = None

    def with_runtime_kind(self, kind: RuntimeKind) -> "OciRuntimeBuilder":
        self._kind = kind
        return self

    def with_binary(self, binary: str) -> "OciRuntimeBuilder":
        self._binary = binary
        return self

    def with_transport_factory(
        self, factory: Callable[..., Transport]
    ) -> "OciRuntimeBuilder":
        self._config = replace(self._config, transport_factory=factory)
        return self

    def with_streaming_transport_factory(
        self, factory: Callable[..., StreamingTransport]
    ) -> "OciRuntimeBuilder":
        self._config = replace(self._config, streaming_transport_factory=factory)
        return self

    def with_tty_detector_factory(
        self, factory: Callable[[], TtyDetector]
    ) -> "OciRuntimeBuilder":
        self._config = replace(self._config, tty_detector_factory=factory)
        return self

    def with_output_stream_factory(
        self, factory: Callable[[], OutputStream]
    ) -> "OciRuntimeBuilder":
        self._config = replace(self._config, output_stream_factory=factory)
        return self

    def with_cancellation_factory(
        self, factory: Callable[[], CancellationToken]
    ) -> "OciRuntimeBuilder":
        self._config = replace(self._config, cancellation_factory=factory)
        return self

    def with_binary_resolver_factory(
        self, factory: Callable[[], BinaryResolver]
    ) -> "OciRuntimeBuilder":
        self._config = replace(self._config, binary_resolver_factory=factory)
        return self

    def with_pty_transport_factory(
        self, factory: Callable[..., PtyTransport]
    ) -> "OciRuntimeBuilder":
        self._config = replace(self._config, pty_transport_factory=factory)
        return self

    def with_result_checker_factory(
        self, factory: Callable[..., ResultChecker]
    ) -> "OciRuntimeBuilder":
        self._config = replace(self._config, result_checker_factory=factory)
        return self

    def with_list_executor_factory(
        self, factory: Callable[..., ListExecutor]
    ) -> "OciRuntimeBuilder":
        self._config = replace(self._config, list_executor_factory=factory)
        return self

    def with_providers(
        self, providers: dict[RuntimeKind, RuntimeProvider]
    ) -> "OciRuntimeBuilder":
        self._providers = providers
        return self

    def build(self) -> EngineBuildResult:
        resolved = _resolve_config(self._config)
        factory = RuntimeFactory(config=self._config, providers=self._providers)
        preference = RuntimePreference(kind=self._kind, binary=self._binary)
        engine = factory.create(preference)
        return EngineBuildResult(engine=engine, resolved_config=resolved)
