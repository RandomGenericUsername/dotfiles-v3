from dataclasses import dataclass, replace
from typing import Callable

from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.domain.exceptions import RuntimeNotAvailableError
from oci_runtime.domain.types import RuntimePreference
from oci_runtime.ports.discovery import RuntimeDiscovery
from oci_runtime.ports.engine import ContainerEngine
from oci_runtime.ports.provider import RuntimeProvider
from oci_runtime.ports.transport import Transport


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
    runtime_cls: type[ContainerEngine] | None = None
    discovery_factory: Callable[[Callable[[str], Transport]], "RuntimeDiscovery"] | None = None


def _default_providers() -> dict[RuntimeKind, RuntimeProvider]:
    from oci_runtime.adapters.provider.docker import DockerRuntimeProvider
    from oci_runtime.adapters.provider.podman import PodmanRuntimeProvider
    return {
        RuntimeKind.DOCKER: DockerRuntimeProvider(),
        RuntimeKind.PODMAN: PodmanRuntimeProvider(),
    }


def _default_transport_factory(binary: str) -> Transport:
    from oci_runtime.adapters.transport.cli import CliTransport
    return CliTransport(binary)


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
    if cfg.runtime_cls is None:
        replacements["runtime_cls"] = _default_runtime_cls()
    if cfg.discovery_factory is None:
        replacements["discovery_factory"] = _default_discovery_factory

    return replace(cfg, **replacements) if replacements else cfg


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
        self._cfg = _resolve_config(config)
        self._providers = dict(providers) if providers is not None else _default_providers()

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
        managers = provider.create_managers(transport, caps)

        runtime = self._cfg.runtime_cls(
            transport=transport,
            image_manager=managers.image_manager,
            container_manager=managers.container_manager,
            volume_manager=managers.volume_manager,
            network_manager=managers.network_manager,
            caps=caps,
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
