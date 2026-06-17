import pytest

from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.aggregates import Managers, Parsers
from oci_runtime.ports.provider import RuntimeProvider
from oci_runtime.ports.transport import Transport


class TestRuntimeProviderIsABC:
    def test_cannot_be_instantiated_directly(self):
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            RuntimeProvider()

    def test_has_kind_abstract_property(self):
        assert "kind" in RuntimeProvider.__abstractmethods__

    def test_has_capabilities_abstract_method(self):
        assert "capabilities" in RuntimeProvider.__abstractmethods__

    def test_has_create_parsers_abstract_method(self):
        assert "create_parsers" in RuntimeProvider.__abstractmethods__

    def test_has_create_managers_abstract_method(self):
        assert "create_managers" in RuntimeProvider.__abstractmethods__

    def test_has_exactly_four_abstract_methods(self):
        assert len(RuntimeProvider.__abstractmethods__) == 4


class TestProviderImportable:
    def test_importable_from_port(self):
        from oci_runtime.ports.provider import RuntimeProvider
        assert RuntimeProvider is not None

    def test_method_signatures_exist(self):
        import inspect
        sig = inspect.signature(RuntimeProvider.capabilities)
        assert list(sig.parameters.keys()) == ["self"]
        sig = inspect.signature(RuntimeProvider.create_parsers)
        assert list(sig.parameters.keys()) == ["self"]


class TestConcreteProviderContract:
    def test_concrete_provider_must_implement_all_abstract_methods(self):
        class IncompleteProvider(RuntimeProvider):
            pass
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteProvider()

    def test_concrete_provider_with_all_methods_can_be_instantiated(self):
        class CompleteProvider(RuntimeProvider):
            @property
            def kind(self) -> RuntimeKind:
                return RuntimeKind.DOCKER

            def capabilities(self) -> RuntimeCapabilities:
                return RuntimeCapabilities()

            def create_parsers(self) -> Parsers:
                from oci_runtime.ports.parsers import ParsingError
                from oci_runtime.ports.parsers import ContainerParser, ImageParser, NetworkParser, VolumeParser
                class FakeCP(ContainerParser):
                    def parse_inspect(self, raw): raise ParsingError(raw)
                    def parse_list(self, raw): return []
                    def parse_prune(self, raw): return {"deleted": 0, "reclaimed_bytes": 0}
                    def is_not_found_error(self, stderr): return False
                class FakeIP(ImageParser):
                    def parse_inspect(self, raw): raise ParsingError(raw)
                    def parse_list(self, raw): return []
                    def parse_build_output(self, raw): return ""
                    def parse_id_from_pull(self, raw): return ""
                    def parse_prune(self, raw): return {"deleted": 0, "reclaimed_bytes": 0}
                    def is_not_found_error(self, stderr): return False
                class FakeVP(VolumeParser):
                    def parse_inspect(self, raw): raise ParsingError(raw)
                    def parse_list(self, raw): return []
                    def parse_prune(self, raw): return {"deleted": 0, "reclaimed_bytes": 0}
                    def is_not_found_error(self, stderr): return False
                class FakeNP(NetworkParser):
                    def parse_inspect(self, raw): raise ParsingError(raw)
                    def parse_list(self, raw): return []
                    def parse_prune(self, raw): return {"deleted": 0, "reclaimed_bytes": 0}
                    def is_not_found_error(self, stderr): return False
                return Parsers(container_parser=FakeCP(), image_parser=FakeIP(), volume_parser=FakeVP(), network_parser=FakeNP())

            def create_managers(self, transport, streaming_transport, caps):
                from unittest.mock import MagicMock
                from oci_runtime.ports.managers import ContainerManager, ImageManager, NetworkManager, VolumeManager
                return Managers(
                    image_manager=MagicMock(spec=ImageManager),
                    container_manager=MagicMock(spec=ContainerManager),
                    volume_manager=MagicMock(spec=VolumeManager),
                    network_manager=MagicMock(spec=NetworkManager),
                )

        provider = CompleteProvider()
        assert provider.kind == RuntimeKind.DOCKER
        assert isinstance(provider.capabilities(), RuntimeCapabilities)
        assert isinstance(provider.create_parsers(), Parsers)
        from oci_runtime.ports.streaming import StreamingTransport
        from oci_runtime.ports.transport import Transport
        from unittest.mock import MagicMock
        managers = provider.create_managers(MagicMock(spec=Transport), MagicMock(spec=StreamingTransport), RuntimeCapabilities())
        assert isinstance(managers, Managers)
