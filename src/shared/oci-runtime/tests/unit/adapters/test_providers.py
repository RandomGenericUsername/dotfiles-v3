import pytest

from oci_runtime.adapters.provider.docker import DockerRuntimeProvider
from oci_runtime.adapters.provider.podman import PodmanRuntimeProvider
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.factory import Parsers
from oci_runtime.ports.parsers import (
    ContainerParser,
    ImageParser,
    NetworkParser,
    VolumeParser,
)
from oci_runtime.factory import get_provider, register_provider
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
        assert "yaml" in caps.supported_output_formats
        assert "json" in caps.supported_output_formats

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
        assert "json" in caps.supported_output_formats
        assert "yaml" not in caps.supported_output_formats

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


class TestProviderRegistry:
    def setup_method(self):
        from oci_runtime.factory import _PROVIDER_REGISTRY
        _PROVIDER_REGISTRY.clear()
        register_provider(DockerRuntimeProvider())
        register_provider(PodmanRuntimeProvider())

    def teardown_method(self):
        from oci_runtime.factory import _PROVIDER_REGISTRY
        _PROVIDER_REGISTRY.clear()

    def test_get_provider_docker(self):
        provider = get_provider(RuntimeKind.DOCKER)
        assert isinstance(provider, DockerRuntimeProvider)
        assert provider.kind == RuntimeKind.DOCKER

    def test_get_provider_podman(self):
        provider = get_provider(RuntimeKind.PODMAN)
        assert isinstance(provider, PodmanRuntimeProvider)
        assert provider.kind == RuntimeKind.PODMAN

    def test_get_provider_unknown_kind_raises(self):
        class FakeKind:
            value = "fake"
            def __hash__(self): return hash("fake")
            def __eq__(self, other): return False
            def __repr__(self): return "RuntimeKind.FAKE"
        with pytest.raises(NotImplementedError, match="No RuntimeProvider registered"):
            get_provider(FakeKind())

    def test_register_provider_duplicate_raises(self):
        class DuplicateProvider(RuntimeProvider):
            @property
            def kind(self): return RuntimeKind.DOCKER
            def capabilities(self): return RuntimeCapabilities()
            def create_parsers(self):
                from oci_runtime.ports.parsers import ContainerParser, ImageParser, NetworkParser, VolumeParser
                class _Fake:
                    def parse_inspect(self, raw): return None
                    def parse_list(self, raw): return []
                    def parse_prune(self, raw): return {"deleted": 0, "reclaimed_bytes": 0}
                    def is_not_found_error(self, stderr): return False
                return Parsers(container_parser=_Fake(), image_parser=_Fake(), volume_parser=_Fake(), network_parser=_Fake())
        with pytest.raises(ValueError, match="already registered"):
            register_provider(DuplicateProvider())

    def test_get_provider_returns_provider_with_correct_kind(self):
        for kind in [RuntimeKind.DOCKER, RuntimeKind.PODMAN]:
            provider = get_provider(kind)
            assert provider.kind == kind
