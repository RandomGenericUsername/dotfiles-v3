from dataclasses import dataclass, replace
from collections.abc import Callable

from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.adapters.helpers.result_checker import CliResultChecker
from oci_runtime.adapters.helpers.list_executor import CliListExecutor
from oci_runtime.domain.exceptions import (
    ContainerNotFoundError,
    ContainerRuntimeError,
    ImageNotFoundError,
    ImagePullAccessDeniedError,
    ImageRuntimeError,
    NetworkNotFoundError,
    NetworkRuntimeError,
    VolumeNotFoundError,
    VolumeRuntimeError,
)
from oci_runtime.ports.binary_resolver import BinaryResolver
from oci_runtime.ports.cancellation import CancellationToken
from oci_runtime.ports.list_executor import ListExecutor
from oci_runtime.ports.result_checker import ResultChecker
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

    transport_factory: Callable[[str, BinaryResolver], Transport] | None = None
    streaming_transport_factory: (
        Callable[[str, BinaryResolver], StreamingTransport] | None
    ) = None
    runtime_cls: type[ContainerEngine] | None = None
    discovery_factory: (
        Callable[[Callable[[str], Transport]], "RuntimeDiscovery"] | None
    ) = None
    tty_detector_factory: Callable[[], TtyDetector] | None = None
    output_stream_factory: Callable[[], OutputStream] | None = None
    cancellation_factory: Callable[[], CancellationToken] | None = None
    binary_resolver_factory: Callable[[], BinaryResolver] | None = None
    pty_transport_factory: Callable[[BinaryResolver], PtyTransport] | None = None
    result_checker_factory: Callable[..., ResultChecker] | None = None
    list_executor_factory: Callable[..., ListExecutor] | None = None
    container_manager_cls: type | None = None
    image_manager_cls: type | None = None
    volume_manager_cls: type | None = None
    network_manager_cls: type | None = None


def _default_providers() -> dict[RuntimeKind, RuntimeProvider]:
    from oci_runtime.adapters.parser.docker import (
        DockerContainerParser,
        DockerImageParser,
        DockerNetworkParser,
        DockerVolumeParser,
    )
    from oci_runtime.adapters.parser.podman import (
        PodmanContainerParser,
        PodmanImageParser,
        PodmanNetworkParser,
        PodmanVolumeParser,
    )
    from oci_runtime.adapters.provider.docker import (
        _DOCKER_CAPABILITIES,
        DockerRuntimeProvider,
    )
    from oci_runtime.adapters.provider.podman import (
        _PODMAN_CAPABILITIES,
        PodmanRuntimeProvider,
    )

    return {
        RuntimeKind.DOCKER: DockerRuntimeProvider(
            container_parser_cls=DockerContainerParser,
            image_parser_cls=DockerImageParser,
            volume_parser_cls=DockerVolumeParser,
            network_parser_cls=DockerNetworkParser,
            capabilities=_DOCKER_CAPABILITIES,
        ),
        RuntimeKind.PODMAN: PodmanRuntimeProvider(
            container_parser_cls=PodmanContainerParser,
            image_parser_cls=PodmanImageParser,
            volume_parser_cls=PodmanVolumeParser,
            network_parser_cls=PodmanNetworkParser,
            capabilities=_PODMAN_CAPABILITIES,
        ),
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


def _default_container_manager_cls() -> type:
    from oci_runtime.adapters.managers.container import CliContainerManager

    return CliContainerManager


def _default_image_manager_cls() -> type:
    from oci_runtime.adapters.managers.image import CliImageManager

    return CliImageManager


def _default_volume_manager_cls() -> type:
    from oci_runtime.adapters.managers.volume import CliVolumeManager

    return CliVolumeManager


def _default_network_manager_cls() -> type:
    from oci_runtime.adapters.managers.network import CliNetworkManager

    return CliNetworkManager


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
        from oci_runtime.ports.cancellation import ThreadCancellationToken

        replacements["cancellation_factory"] = lambda: ThreadCancellationToken()
    if cfg.binary_resolver_factory is None:
        from oci_runtime.adapters.binary import CliBinaryResolver

        replacements["binary_resolver_factory"] = lambda: CliBinaryResolver()
    if cfg.pty_transport_factory is None:
        from oci_runtime.adapters.transport.pty import CliPtyTransport

        replacements["pty_transport_factory"] = lambda resolver: CliPtyTransport(
            resolver
        )
    if cfg.container_manager_cls is None:
        replacements["container_manager_cls"] = _default_container_manager_cls()
    if cfg.image_manager_cls is None:
        replacements["image_manager_cls"] = _default_image_manager_cls()
    if cfg.volume_manager_cls is None:
        replacements["volume_manager_cls"] = _default_volume_manager_cls()
    if cfg.network_manager_cls is None:
        replacements["network_manager_cls"] = _default_network_manager_cls()
    if cfg.result_checker_factory is None:
        replacements["result_checker_factory"] = CliResultChecker
    if cfg.list_executor_factory is None:
        replacements["list_executor_factory"] = CliListExecutor

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
        parsers = provider.create_parsers()

        image_checker = self._cfg.result_checker_factory(
            generic_error=ImageRuntimeError,
            not_found_error=ImageNotFoundError,
            is_not_found=parsers.image_parser.is_not_found_error,
            auth_error=ImagePullAccessDeniedError,
            is_auth=parsers.image_parser.is_auth_error,
        )
        container_checker = self._cfg.result_checker_factory(
            generic_error=ContainerRuntimeError,
            not_found_error=ContainerNotFoundError,
            is_not_found=parsers.container_parser.is_not_found_error,
        )
        volume_checker = self._cfg.result_checker_factory(
            generic_error=VolumeRuntimeError,
            not_found_error=VolumeNotFoundError,
            is_not_found=parsers.volume_parser.is_not_found_error,
        )
        network_checker = self._cfg.result_checker_factory(
            generic_error=NetworkRuntimeError,
            not_found_error=NetworkNotFoundError,
            is_not_found=parsers.network_parser.is_not_found_error,
        )

        image_manager = self._cfg.image_manager_cls(
            transport,
            parsers.image_parser,
            caps,
            result_checker=image_checker,
            list_executor=self._cfg.list_executor_factory(
                transport,
                caps,
                image_checker,
                parse_list=parsers.image_parser.parse_list,
            ),
        )
        container_manager = self._cfg.container_manager_cls(
            transport,
            parsers.container_parser,
            caps,
            streaming=streaming_transport,
            tty_detector=self._cfg.tty_detector_factory(),
            pty_transport=pty_transport,
            cancellation_factory=self._cfg.cancellation_factory,
            output_stream=self._cfg.output_stream_factory(),
            result_checker=container_checker,
            list_executor=self._cfg.list_executor_factory(
                transport,
                caps,
                container_checker,
                parse_list=parsers.container_parser.parse_list,
            ),
        )
        volume_manager = self._cfg.volume_manager_cls(
            transport,
            parsers.volume_parser,
            caps,
            result_checker=volume_checker,
            list_executor=self._cfg.list_executor_factory(
                transport,
                caps,
                volume_checker,
                parse_list=parsers.volume_parser.parse_list,
            ),
        )
        network_manager = self._cfg.network_manager_cls(
            transport,
            parsers.network_parser,
            caps,
            result_checker=network_checker,
            list_executor=self._cfg.list_executor_factory(
                transport,
                caps,
                network_checker,
                parse_list=parsers.network_parser.parse_list,
            ),
        )

        return self._cfg.runtime_cls(
            transport=transport,
            image_manager=image_manager,
            container_manager=container_manager,
            volume_manager=volume_manager,
            network_manager=network_manager,
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
