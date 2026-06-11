from dataclasses import replace
from typing import Callable

from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.domain.exceptions import RuntimeNotAvailableError
from oci_runtime.ports.capabilities import (
    RuntimeCapabilities,
    RuntimePreference,
)
from oci_runtime.ports.discovery import RuntimeDiscovery
from oci_runtime.ports.engine import ContainerEngine
from oci_runtime.ports.factory import Parsers, RuntimeFactoryConfig
from oci_runtime.ports.parsers import (
    ContainerParser,
    ImageParser,
    NetworkParser,
    VolumeParser,
)
from oci_runtime.ports.provider import RuntimeProvider
from oci_runtime.ports.transport import Transport


_PROVIDER_REGISTRY: dict[RuntimeKind, RuntimeProvider] = {}


def register_provider(provider: RuntimeProvider) -> None:
    kind = provider.kind
    if kind in _PROVIDER_REGISTRY:
        raise ValueError(f"Provider for '{kind.value}' is already registered")
    _PROVIDER_REGISTRY[kind] = provider


def get_provider(kind: RuntimeKind) -> RuntimeProvider:
    try:
        return _PROVIDER_REGISTRY[kind]
    except KeyError:
        raise NotImplementedError(
            f"No RuntimeProvider registered for RuntimeKind: {kind}. "
            f"Registered: {list(_PROVIDER_REGISTRY.keys())}"
        )


# ─── Lazy-loaded default implementations (adapter imports inside functions) ───

def _default_transport_factory(binary: str) -> Transport:
    from oci_runtime.adapters.transport.cli import CliTransport
    return CliTransport(binary)


def _default_runtime_cls() -> type[ContainerEngine]:
    from oci_runtime.adapters.engine.cli import CliRuntime
    return CliRuntime


def _default_parser_provider(kind: RuntimeKind) -> Parsers:
    return get_provider(kind).create_parsers()


def _default_discovery_factory(
    transport_factory: Callable[[str], Transport],
) -> RuntimeDiscovery:
    from oci_runtime.adapters.discovery.cli import CliRuntimeDiscovery
    return CliRuntimeDiscovery(transport_factory)


def _ensure_default_providers() -> None:
    if not _PROVIDER_REGISTRY:
        from oci_runtime.adapters.provider.docker import DockerRuntimeProvider
        from oci_runtime.adapters.provider.podman import PodmanRuntimeProvider

        register_provider(DockerRuntimeProvider())
        register_provider(PodmanRuntimeProvider())


def _resolve_config(cfg: RuntimeFactoryConfig | None) -> RuntimeFactoryConfig:
    if cfg is None:
        cfg = RuntimeFactoryConfig()

    replacements = {}
    if cfg.transport_factory is None:
        replacements["transport_factory"] = _default_transport_factory
    if cfg.runtime_cls is None:
        replacements["runtime_cls"] = _default_runtime_cls()
    if cfg.parser_provider is None:
        replacements["parser_provider"] = _default_parser_provider
    if cfg.discovery_factory is None:
        replacements["discovery_factory"] = _default_discovery_factory

    return replace(cfg, **replacements) if replacements else cfg


# ─── Manager builders ───

def _make_image_manager(t: Transport, p: ImageParser, c: RuntimeCapabilities):
    from oci_runtime.adapters.managers.image import CliImageManager
    return CliImageManager(t, p, c)


def _make_container_manager(t: Transport, p: ContainerParser, c: RuntimeCapabilities):
    from oci_runtime.adapters.managers.container import CliContainerManager
    return CliContainerManager(t, p, c)


def _make_volume_manager(t: Transport, p: VolumeParser, c: RuntimeCapabilities):
    from oci_runtime.adapters.managers.volume import CliVolumeManager
    return CliVolumeManager(t, p, c)


def _make_network_manager(t: Transport, p: NetworkParser, c: RuntimeCapabilities):
    from oci_runtime.adapters.managers.network import CliNetworkManager
    return CliNetworkManager(t, p, c)


class RuntimeFactory:
    """Instance factory with dependency injection.

    Depends on abstractions (ports), not implementations (adapters).
    This is true hexagonal architecture.
    """

    def __init__(
        self,
        config: RuntimeFactoryConfig | None = None,
        providers: dict[RuntimeKind, RuntimeProvider] | None = None,
    ):
        _ensure_default_providers()
        self._cfg = _resolve_config(config)
        self._providers = providers if providers is not None else _PROVIDER_REGISTRY

    def create(self, preference: RuntimePreference) -> ContainerEngine:
        """Create the explicitly requested engine or raise immediately.

        No fallback. No retry. The user asked for X, they get X or an error.
        """
        binary = preference.binary
        transport = self._cfg.transport_factory(binary)
        try:
            provider = self._providers[preference.kind]
        except KeyError:
            raise NotImplementedError(
                f"No RuntimeProvider registered for RuntimeKind: {preference.kind}. "
                f"Registered: {list(self._providers.keys())}"
            )
        caps = provider.capabilities()
        parsers = self._cfg.parser_provider(preference.kind)

        runtime = self._cfg.runtime_cls(
            transport=transport,
            image_manager=_make_image_manager(transport, parsers.image_parser, caps),
            container_manager=_make_container_manager(transport, parsers.container_parser, caps),
            volume_manager=_make_volume_manager(transport, parsers.volume_parser, caps),
            network_manager=_make_network_manager(transport, parsers.network_parser, caps),
            caps=caps,
            binary=binary,
        )

        if not runtime.is_available():
            raise RuntimeNotAvailableError(
                f"Requested engine '{preference.kind.value}' is not available."
            )

        return runtime

    @property
    def discovery(self) -> RuntimeDiscovery:
        return self._cfg.discovery_factory(self._cfg.transport_factory)

    def available(self) -> list[RuntimePreference]:
        """Return all engines that are currently available.

        Informational only. The user still MUST explicitly call create().
        No fallback happens here — purely a helper for the user.
        """
        return self.discovery.available()
