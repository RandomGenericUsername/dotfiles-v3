from dataclasses import dataclass, replace
from collections.abc import Callable

from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.binary_resolver import BinaryResolver
from oci_runtime.ports.cancellation import CancellationToken
from oci_runtime.domain.types import RuntimePreference
from oci_runtime.ports.discovery import RuntimeDiscovery
from oci_runtime.ports.engine import ContainerEngine
from oci_runtime.ports.output_stream import OutputStream
from oci_runtime.ports.provider import RuntimeProvider
from oci_runtime.ports.pty_transport import PtyTransport
from oci_runtime.ports.streaming import StreamingTransport
from oci_runtime.ports.transport import Transport
from oci_runtime.ports.tty import TtyDetector


@dataclass(frozen=True)
class RuntimeFactoryConfig:
    """Composition root configuration.

    This is the ONLY place where adapter implementations are wired.
    Allows injection of mock implementations for testing.
    All fields default to None — the factory resolves them to production
    implementations on first use (lazy loading).

    Parsers are owned by RuntimeProvider — the factory delegates to
    providers for parser resolution, not to a separate callback.
    """

    transport_factory: Callable[[str], Transport] | None = None
    streaming_transport_factory: Callable[[str], StreamingTransport] | None = None
    runtime_cls: type[ContainerEngine] | None = None
    discovery_factory: (
        Callable[[Callable[[str], Transport]], "RuntimeDiscovery"] | None
    ) = None
    tty_detector_factory: Callable[[], TtyDetector] | None = None
    output_stream_factory: Callable[[], OutputStream] | None = None
    cancellation_factory: Callable[[], CancellationToken] | None = None
    binary_resolver_factory: Callable[[], BinaryResolver] | None = None
    pty_transport_factory: Callable[[BinaryResolver], PtyTransport] | None = None


def _default_providers() -> dict[RuntimeKind, RuntimeProvider]:
    from oci_runtime.adapters.provider.docker import DockerRuntimeProvider
    from oci_runtime.adapters.provider.podman import PodmanRuntimeProvider

    return {
        RuntimeKind.DOCKER: DockerRuntimeProvider(),
        RuntimeKind.PODMAN: PodmanRuntimeProvider(),
    }


def _default_transport_factory(
    binary: str, binary_resolver: BinaryResolver | None = None
) -> Transport:
    from oci_runtime.adapters.transport.cli import CliTransport

    return CliTransport(binary, binary_resolver=binary_resolver)


def _default_streaming_transport_factory(
    binary: str, binary_resolver: BinaryResolver | None = None
) -> StreamingTransport:
    from oci_runtime.adapters.transport.streaming import CliStreamingTransport

    return CliStreamingTransport(binary, binary_resolver=binary_resolver)


def _default_runtime_cls() -> type[ContainerEngine]:
    from oci_runtime.adapters.engine.cli import CliRuntime

    return CliRuntime


def _default_discovery_factory(
    transport_factory: Callable[[str], Transport],
) -> RuntimeDiscovery:
    from oci_runtime.adapters.discovery.cli import CliRuntimeDiscovery

    return CliRuntimeDiscovery(transport_factory)


def _resolve_config(cfg: RuntimeFactoryConfig | None) -> RuntimeFactoryConfig:
    if cfg is None:
        cfg = RuntimeFactoryConfig()

    replacements = {}
    if cfg.transport_factory is None:
        replacements["transport_factory"] = _default_transport_factory
    if cfg.streaming_transport_factory is None:
        replacements["streaming_transport_factory"] = (
            _default_streaming_transport_factory
        )
    if cfg.runtime_cls is None:
        replacements["runtime_cls"] = _default_runtime_cls()
    if cfg.discovery_factory is None:
        replacements["discovery_factory"] = _default_discovery_factory
    if cfg.tty_detector_factory is None:
        from oci_runtime.adapters.tty import StdoutTtyDetector

        replacements["tty_detector_factory"] = lambda: StdoutTtyDetector()
    if cfg.output_stream_factory is None:
        from oci_runtime.adapters.output_stream import StdoutBufferStream

        replacements["output_stream_factory"] = lambda: StdoutBufferStream()
    if cfg.cancellation_factory is None:
        from oci_runtime.adapters._cancellation import ThreadCancellationToken

        replacements["cancellation_factory"] = lambda: ThreadCancellationToken()
    if cfg.binary_resolver_factory is None:
        from oci_runtime.adapters.binary import CliBinaryResolver

        replacements["binary_resolver_factory"] = lambda: CliBinaryResolver()
    if cfg.pty_transport_factory is None:
        from oci_runtime.adapters.transport.pty import CliPtyTransport

        replacements["pty_transport_factory"] = lambda resolver: CliPtyTransport(
            resolver
        )

    return replace(cfg, **replacements) if replacements else cfg


class RuntimeFactory:
    """Instance factory with dependency injection.

    Depends on abstractions (ports), not implementations (adapters).
    This is true hexagonal architecture.
    """

    def create(self, preference: RuntimePreference) -> ContainerEngine:
        """Create the explicitly requested engine or raise immediately.

        No fallback. No retry. The user asked for X, they get X or an error.

        Note: This method does NOT probe availability. Callers who need
        to verify the engine is reachable should call
        ``engine.is_available()`` themselves after creation.
        """
        binary = preference.binary
        binary_resolver = self._cfg.binary_resolver_factory()
        transport = self._cfg.transport_factory(binary, binary_resolver=binary_resolver)
        streaming_transport = self._cfg.streaming_transport_factory(
            binary, binary_resolver=binary_resolver
        )
        pty_transport = self._cfg.pty_transport_factory(binary_resolver)
        try:
            provider = self._providers[preference.kind]
        except KeyError:
            raise NotImplementedError(
                f"No RuntimeProvider registered for RuntimeKind: {preference.kind}. "
                f"Registered: {list(self._providers.keys())}"
            )
        caps = provider.capabilities()
        managers = provider.create_managers(
            transport,
            streaming_transport,
            caps,
            tty_detector_factory=self._cfg.tty_detector_factory,
            output_stream_factory=self._cfg.output_stream_factory,
            cancellation_factory=self._cfg.cancellation_factory,
            pty_transport=pty_transport,
        )

        return self._cfg.runtime_cls(
            transport=transport,
            image_manager=managers.image_manager,
            container_manager=managers.container_manager,
            volume_manager=managers.volume_manager,
            network_manager=managers.network_manager,
            caps=caps,
        )

    def __init__(
        self,
        config: RuntimeFactoryConfig | None = None,
        providers: dict[RuntimeKind, RuntimeProvider] | None = None,
    ):
        self._cfg = _resolve_config(config)
        self._providers = (
            dict(providers) if providers is not None else _default_providers()
        )
        self._discovery: RuntimeDiscovery | None = None

    @property
    def discovery(self) -> RuntimeDiscovery:
        if self._discovery is None:
            binary_resolver = self._cfg.binary_resolver_factory()

            def _resolving_factory(b: str) -> Transport:
                return self._cfg.transport_factory(b, binary_resolver=binary_resolver)

            self._discovery = self._cfg.discovery_factory(_resolving_factory)
        return self._discovery

    def available(self) -> list[RuntimePreference]:
        """Return all engines that are currently available.

        Informational only. The user still MUST explicitly call create().
        No fallback happens here — purely a helper for the user.
        """
        return self.discovery.available()
