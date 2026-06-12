import pytest

from oci_runtime.adapters.provider.docker import DockerRuntimeProvider
from oci_runtime.adapters.provider.podman import PodmanRuntimeProvider
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.capabilities import RuntimeCapabilities, RuntimePreference
from oci_runtime.ports.factory import Managers, Parsers
from oci_runtime.ports.parsers import (
    ContainerParser,
    ImageParser,
    NetworkParser,
    VolumeParser,
)

from oci_runtime.factory import RuntimeFactory
from oci_runtime.ports.provider import RuntimeProvider


class TestDockerRuntimeProvider:
    def setup_method(self):
        self.provider = DockerRuntimeProvider()

    def test_is_runtime_provider(self):
        assert isinstance(self.provider, RuntimeProvider)

    def test_kind_is_docker(self):
        assert self.provider.kind == RuntimeKind.DOCKER

    def test_capabilities_returns_runtime_capabilities(self):
        assert isinstance(self.provider.capabilities(), RuntimeCapabilities)

    def test_capabilities_values(self):
        caps = self.provider.capabilities()
        assert caps.needs_userns_keep_id is False
        assert caps.supports_log_drivers is True
        assert caps.tar_entry_name == "Dockerfile"
        assert caps.default_run_flags == []
        assert caps.default_build_flags == ["--quiet"]
        assert caps.list_format_flags == ["--format", "{{json .}}"]

    def test_create_parsers_returns_parsers(self):
        parsers = self.provider.create_parsers()
        assert isinstance(parsers, Parsers)

    def test_create_parsers_returns_container_parser(self):
        assert isinstance(self.provider.create_parsers().container_parser, ContainerParser)

    def test_create_parsers_returns_image_parser(self):
        assert isinstance(self.provider.create_parsers().image_parser, ImageParser)

    def test_create_parsers_returns_volume_parser(self):
        assert isinstance(self.provider.create_parsers().volume_parser, VolumeParser)

    def test_create_parsers_returns_network_parser(self):
        assert isinstance(self.provider.create_parsers().network_parser, NetworkParser)

    def test_callables_are_idempotent(self):
        p1 = self.provider.create_parsers()
        p2 = self.provider.create_parsers()
        assert p1 is not p2

    def test_create_managers_returns_managers(self):
        from oci_runtime.ports.transport import Transport
        from unittest.mock import MagicMock
        transport = MagicMock(spec=Transport)
        managers = self.provider.create_managers(transport, RuntimeCapabilities())
        assert isinstance(managers, Managers)


class TestPodmanRuntimeProvider:
    def setup_method(self):
        self.provider = PodmanRuntimeProvider()

    def test_is_runtime_provider(self):
        assert isinstance(self.provider, RuntimeProvider)

    def test_kind_is_podman(self):
        assert self.provider.kind == RuntimeKind.PODMAN

    def test_capabilities_returns_runtime_capabilities(self):
        assert isinstance(self.provider.capabilities(), RuntimeCapabilities)

    def test_capabilities_values(self):
        caps = self.provider.capabilities()
        assert caps.needs_userns_keep_id is True
        assert caps.supports_log_drivers is False
        assert caps.tar_entry_name == "Containerfile"
        assert caps.default_run_flags == ["--userns=keep-id"]
        assert caps.default_build_flags == ["--quiet"]
        assert caps.list_format_flags == ["--format", "json"]

    def test_create_parsers_returns_parsers(self):
        parsers = self.provider.create_parsers()
        assert isinstance(parsers, Parsers)

    def test_create_parsers_returns_container_parser(self):
        assert isinstance(self.provider.create_parsers().container_parser, ContainerParser)

    def test_create_parsers_returns_image_parser(self):
        assert isinstance(self.provider.create_parsers().image_parser, ImageParser)

    def test_create_parsers_returns_volume_parser(self):
        assert isinstance(self.provider.create_parsers().volume_parser, VolumeParser)

    def test_create_parsers_returns_network_parser(self):
        assert isinstance(self.provider.create_parsers().network_parser, NetworkParser)

    def test_callables_are_idempotent(self):
        p1 = self.provider.create_parsers()
        p2 = self.provider.create_parsers()
        assert p1 is not p2

    def test_create_managers_returns_managers(self):
        from oci_runtime.ports.transport import Transport
        from unittest.mock import MagicMock
        transport = MagicMock(spec=Transport)
        managers = self.provider.create_managers(transport, RuntimeCapabilities())
        assert isinstance(managers, Managers)


class TestDockerProviderParserTypes:
    def test_container_parser_is_docker(self):
        from oci_runtime.adapters.parser.docker import DockerContainerParser
        assert isinstance(
            DockerRuntimeProvider().create_parsers().container_parser,
            DockerContainerParser,
        )

    def test_image_parser_is_docker(self):
        from oci_runtime.adapters.parser.docker import DockerImageParser
        assert isinstance(
            DockerRuntimeProvider().create_parsers().image_parser,
            DockerImageParser,
        )

    def test_volume_parser_is_docker(self):
        from oci_runtime.adapters.parser.docker import DockerVolumeParser
        assert isinstance(
            DockerRuntimeProvider().create_parsers().volume_parser,
            DockerVolumeParser,
        )

    def test_network_parser_is_docker(self):
        from oci_runtime.adapters.parser.docker import DockerNetworkParser
        assert isinstance(
            DockerRuntimeProvider().create_parsers().network_parser,
            DockerNetworkParser,
        )


class TestPodmanProviderParserTypes:
    def test_container_parser_is_podman(self):
        from oci_runtime.adapters.parser.podman import PodmanContainerParser
        assert isinstance(
            PodmanRuntimeProvider().create_parsers().container_parser,
            PodmanContainerParser,
        )

    def test_image_parser_is_podman(self):
        from oci_runtime.adapters.parser.podman import PodmanImageParser
        assert isinstance(
            PodmanRuntimeProvider().create_parsers().image_parser,
            PodmanImageParser,
        )

    def test_volume_parser_is_podman(self):
        from oci_runtime.adapters.parser.podman import PodmanVolumeParser
        assert isinstance(
            PodmanRuntimeProvider().create_parsers().volume_parser,
            PodmanVolumeParser,
        )

    def test_network_parser_is_podman(self):
        from oci_runtime.adapters.parser.podman import PodmanNetworkParser
        assert isinstance(
            PodmanRuntimeProvider().create_parsers().network_parser,
            PodmanNetworkParser,
        )


class TestDefaultProviders:
    def test_default_providers_contains_docker(self):
        from oci_runtime.factory import _default_providers
        providers = _default_providers()
        assert RuntimeKind.DOCKER in providers
        assert isinstance(providers[RuntimeKind.DOCKER], DockerRuntimeProvider)
        assert providers[RuntimeKind.DOCKER].kind == RuntimeKind.DOCKER

    def test_default_providers_contains_podman(self):
        from oci_runtime.factory import _default_providers
        providers = _default_providers()
        assert RuntimeKind.PODMAN in providers
        assert isinstance(providers[RuntimeKind.PODMAN], PodmanRuntimeProvider)
        assert providers[RuntimeKind.PODMAN].kind == RuntimeKind.PODMAN

    def test_runtime_factory_uses_default_providers(self):
        factory = RuntimeFactory()
        pref = RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker")
        # Should not raise — default providers are used
        providers = factory._providers
        assert RuntimeKind.DOCKER in providers
        assert RuntimeKind.PODMAN in providers

    def test_runtime_factory_empty_providers_raises(self):
        factory = RuntimeFactory(providers={})
        with pytest.raises(NotImplementedError):
            factory.create(RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker"))
