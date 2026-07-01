import pytest

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
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.domain.exceptions import ProviderNotRegisteredError
from oci_runtime.domain.types import RuntimePreference
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.aggregates import Parsers
from oci_runtime.ports.parsers import (
    ContainerParser,
    ImageParser,
    NetworkParser,
    VolumeParser,
)

from oci_runtime.factory import RuntimeFactory
from oci_runtime.ports.provider import RuntimeProvider


_DOCKER_PARSER_KWARGS = dict(
    container_parser_cls=DockerContainerParser,
    image_parser_cls=DockerImageParser,
    volume_parser_cls=DockerVolumeParser,
    network_parser_cls=DockerNetworkParser,
    capabilities=_DOCKER_CAPABILITIES,
)

_PODMAN_PARSER_KWARGS = dict(
    container_parser_cls=PodmanContainerParser,
    image_parser_cls=PodmanImageParser,
    volume_parser_cls=PodmanVolumeParser,
    network_parser_cls=PodmanNetworkParser,
    capabilities=_PODMAN_CAPABILITIES,
)


class TestDockerRuntimeProvider:
    def setup_method(self):
        self.provider = DockerRuntimeProvider(**_DOCKER_PARSER_KWARGS)

    def test_is_runtime_provider(self):
        assert isinstance(self.provider, RuntimeProvider)

    def test_kind_is_docker(self):
        assert self.provider.kind == RuntimeKind.DOCKER

    def test_capabilities_returns_runtime_capabilities(self):
        assert isinstance(self.provider.capabilities, RuntimeCapabilities)

    def test_capabilities_values(self):
        caps = self.provider.capabilities
        assert caps.needs_userns_keep_id is False
        assert caps.supports_log_drivers is True
        assert caps.tar_entry_name == "Dockerfile"
        assert caps.default_run_flags == ()
        assert caps.default_build_flags == ("--quiet",)
        assert caps.list_format_flags == ("--format", "{{json .}}")

    def test_create_parsers_returns_parsers(self):
        parsers = self.provider.create_parsers()
        assert isinstance(parsers, Parsers)

    def test_create_parsers_returns_container_parser(self):
        assert isinstance(
            self.provider.create_parsers().container_parser, ContainerParser
        )

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


class TestPodmanRuntimeProvider:
    def setup_method(self):
        self.provider = PodmanRuntimeProvider(**_PODMAN_PARSER_KWARGS)

    def test_is_runtime_provider(self):
        assert isinstance(self.provider, RuntimeProvider)

    def test_kind_is_podman(self):
        assert self.provider.kind == RuntimeKind.PODMAN

    def test_capabilities_returns_runtime_capabilities(self):
        assert isinstance(self.provider.capabilities, RuntimeCapabilities)

    def test_capabilities_values(self):
        caps = self.provider.capabilities
        assert caps.needs_userns_keep_id is True
        assert caps.supports_log_drivers is False
        assert caps.tar_entry_name == "Containerfile"
        assert caps.default_run_flags == ("--userns=keep-id",)
        assert caps.default_build_flags == ("--quiet",)
        assert caps.list_format_flags == ("--format", "json")

    def test_create_parsers_returns_parsers(self):
        parsers = self.provider.create_parsers()
        assert isinstance(parsers, Parsers)

    def test_create_parsers_returns_container_parser(self):
        assert isinstance(
            self.provider.create_parsers().container_parser, ContainerParser
        )

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


class TestDockerProviderParserTypes:
    def test_container_parser_is_docker(self):
        assert isinstance(
            DockerRuntimeProvider(**_DOCKER_PARSER_KWARGS)
            .create_parsers()
            .container_parser,
            DockerContainerParser,
        )

    def test_image_parser_is_docker(self):
        assert isinstance(
            DockerRuntimeProvider(**_DOCKER_PARSER_KWARGS)
            .create_parsers()
            .image_parser,
            DockerImageParser,
        )

    def test_volume_parser_is_docker(self):
        assert isinstance(
            DockerRuntimeProvider(**_DOCKER_PARSER_KWARGS)
            .create_parsers()
            .volume_parser,
            DockerVolumeParser,
        )

    def test_network_parser_is_docker(self):
        assert isinstance(
            DockerRuntimeProvider(**_DOCKER_PARSER_KWARGS)
            .create_parsers()
            .network_parser,
            DockerNetworkParser,
        )


class TestPodmanProviderParserTypes:
    def test_container_parser_is_podman(self):
        assert isinstance(
            PodmanRuntimeProvider(**_PODMAN_PARSER_KWARGS)
            .create_parsers()
            .container_parser,
            PodmanContainerParser,
        )

    def test_image_parser_is_podman(self):
        assert isinstance(
            PodmanRuntimeProvider(**_PODMAN_PARSER_KWARGS)
            .create_parsers()
            .image_parser,
            PodmanImageParser,
        )

    def test_volume_parser_is_podman(self):
        assert isinstance(
            PodmanRuntimeProvider(**_PODMAN_PARSER_KWARGS)
            .create_parsers()
            .volume_parser,
            PodmanVolumeParser,
        )

    def test_network_parser_is_podman(self):
        assert isinstance(
            PodmanRuntimeProvider(**_PODMAN_PARSER_KWARGS)
            .create_parsers()
            .network_parser,
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
        # Should not raise — default providers are used
        providers = factory._providers
        assert RuntimeKind.DOCKER in providers
        assert RuntimeKind.PODMAN in providers

    def test_runtime_factory_empty_providers_raises(self):
        factory = RuntimeFactory(providers={})
        with pytest.raises(ProviderNotRegisteredError):
            factory.create(RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker"))
