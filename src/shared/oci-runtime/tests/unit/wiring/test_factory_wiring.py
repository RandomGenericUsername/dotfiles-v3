from unittest.mock import patch, MagicMock


from oci_runtime.adapters.engine.cli import CliRuntime
from oci_runtime.adapters.managers.container import CliContainerManager
from oci_runtime.adapters.managers.image import CliImageManager
from oci_runtime.adapters.managers.network import CliNetworkManager
from oci_runtime.adapters.managers.volume import CliVolumeManager
from oci_runtime.ports.parsers import ParsingError
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.factory import RuntimeFactory
from oci_runtime.domain.types import RuntimePreference
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.engine import ContainerEngine
from oci_runtime.factory import RuntimeFactoryConfig
from oci_runtime.ports.aggregates import Managers, Parsers
from oci_runtime.ports.parsers import ContainerParser, ImageParser
from oci_runtime.ports.provider import RuntimeProvider
from oci_runtime.domain.types import PruneResult, RawExecResult
from oci_runtime.adapters._cancellation import ThreadCancellationToken
from tests.helpers.mock_transport import FakeTtyDetector, MockPtyTransport, RecordingTransport


class TestFactoryCreateEngine:
    @patch("shutil.which", return_value="/usr/bin/docker")
    @patch("subprocess.run")
    def test_create_docker_returns_cli_runtime(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0, stdout=b"Docker version 24.0.0", stderr=b"")
        runtime = RuntimeFactory().create(RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker"))
        assert isinstance(runtime, CliRuntime)
        assert isinstance(runtime, ContainerEngine)

    @patch("shutil.which", return_value="/usr/bin/podman")
    @patch("subprocess.run")
    def test_create_podman_returns_cli_runtime(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0, stdout=b"podman version 4.0.0", stderr=b"")
        runtime = RuntimeFactory().create(RuntimePreference(kind=RuntimeKind.PODMAN, binary="podman"))
        assert isinstance(runtime, CliRuntime)

    @patch("shutil.which", return_value="/usr/bin/docker")
    @patch("subprocess.run")
    def test_create_docker_wires_docker_managers(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0, stdout=b"Docker version 24.0.0", stderr=b"")
        runtime = RuntimeFactory().create(RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker"))
        assert isinstance(runtime.images, CliImageManager)
        assert isinstance(runtime.containers, CliContainerManager)
        assert isinstance(runtime.volumes, CliVolumeManager)
        assert isinstance(runtime.networks, CliNetworkManager)

    @patch("shutil.which", return_value="/usr/bin/podman")
    @patch("subprocess.run")
    def test_create_podman_wires_podman_managers(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0, stdout=b"podman version 4.0.0", stderr=b"")
        runtime = RuntimeFactory().create(RuntimePreference(kind=RuntimeKind.PODMAN, binary="podman"))
        assert isinstance(runtime.images, CliImageManager)
        assert isinstance(runtime.containers, CliContainerManager)
        assert isinstance(runtime.volumes, CliVolumeManager)
        assert isinstance(runtime.networks, CliNetworkManager)

    @patch("shutil.which", return_value="/usr/bin/docker")
    @patch("subprocess.run")
    def test_create_with_custom_binary(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0, stdout=b"Docker version 24.0.0", stderr=b"")
        pref = RuntimePreference(kind=RuntimeKind.DOCKER, binary="/usr/local/bin/docker")
        runtime = RuntimeFactory().create(pref)
        assert isinstance(runtime, CliRuntime)

    def test_create_unavailable_engine_not_probed(self):
        bogus = RuntimePreference(kind=RuntimeKind.DOCKER, binary="nonexistent-runtime-xyz")
        engine = RuntimeFactory().create(bogus)
        assert engine.is_available() is False


class TestFactoryConfigInjection:
    def test_custom_transport_factory_is_used(self):
        transport = RecordingTransport("docker", {
            "docker --version": RawExecResult(returncode=0, stdout=b"Docker", stderr=b""),
        })
        config = RuntimeFactoryConfig(
            transport_factory=lambda _, **kwargs: transport,
        )
        factory = RuntimeFactory(config)
        engine = factory.create(RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker"))
        assert engine.is_available() is True

    def test_custom_runtime_cls_is_used(self):
        class MockEngine(ContainerEngine):
            def __init__(self, **kwargs):
                pass
            @property
            def images(self): return None
            @property
            def containers(self): return None
            @property
            def volumes(self): return None
            @property
            def networks(self): return None
            @property
            def capabilities(self): return RuntimeCapabilities()
            def is_available(self): return True
            def version(self): return ""
        transport = RecordingTransport("docker")
        config = RuntimeFactoryConfig(
            transport_factory=lambda _, **kwargs: transport,
            runtime_cls=MockEngine,
        )
        factory = RuntimeFactory(config)
        engine = factory.create(RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker"))
        assert isinstance(engine, MockEngine)

    def test_custom_provider_is_used(self):
        class FakeContainerParser(ContainerParser):
            def parse_inspect(self, raw): raise ParsingError(raw)
            def parse_list(self, raw): return []
            def parse_prune(self, raw): return PruneResult()
            def is_not_found_error(self, stderr): return False
    
        class FakeImageParser(ImageParser):
            def parse_inspect(self, raw): raise ParsingError(raw)
            def parse_list(self, raw): return []
            def parse_build_output(self, raw): return ""
            def parse_digest_from_pull(self, raw): return ""
            def parse_prune(self, raw): return PruneResult()
            def is_not_found_error(self, stderr): return False

        class FakeProvider(RuntimeProvider):
            @property
            def kind(self): return RuntimeKind.DOCKER
            def capabilities(self): return RuntimeCapabilities()
            def create_parsers(self):
                return Parsers(
                    container_parser=FakeContainerParser(),
                    image_parser=FakeImageParser(),
                    volume_parser=FakeContainerParser(),
                    network_parser=FakeContainerParser(),
                )
            def create_managers(self, transport, streaming_transport, caps, *, tty_detector_factory=None, output_stream_factory=None, cancellation_factory=None, pty_transport=None):
                parsers = self.create_parsers()
                return Managers(
                    image_manager=CliImageManager(transport, parsers.image_parser, caps),
                    container_manager=CliContainerManager(transport, parsers.container_parser, caps, streaming=streaming_transport, tty_detector=FakeTtyDetector(),
                        pty_transport=pty_transport or MockPtyTransport(), cancellation_factory=lambda: ThreadCancellationToken()),
                    volume_manager=CliVolumeManager(transport, parsers.volume_parser, caps),
                    network_manager=CliNetworkManager(transport, parsers.network_parser, caps),
                )

        transport = RecordingTransport("docker", {
            "docker --version": RawExecResult(returncode=0, stdout=b"Docker", stderr=b""),
        })
        config = RuntimeFactoryConfig(
            transport_factory=lambda _, **kwargs: transport,
        )
        factory = RuntimeFactory(config, providers={RuntimeKind.DOCKER: FakeProvider()})
        engine = factory.create(RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker"))
        assert engine.is_available() is True
        parsers = engine.containers._parser
        assert isinstance(parsers, FakeContainerParser)


class TestFactoryAvailable:
    @patch("shutil.which", return_value="/usr/bin/docker")
    @patch("subprocess.run")
    def test_available_returns_list_of_preferences(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0, stdout=b"Docker version 24.0.0", stderr=b"")
        available = RuntimeFactory().available()
        assert isinstance(available, list)
        assert all(isinstance(p, RuntimePreference) for p in available)

    @patch("shutil.which")
    def test_available_only_returns_available_runtimes(self, mock_which):
        def which_side_effect(cmd, *args, **kwargs):
            if cmd == "podman":
                return None
            return f"/usr/bin/{cmd}"
        mock_which.side_effect = which_side_effect
        available = RuntimeFactory().available()
        kinds = {p.kind for p in available}
        assert RuntimeKind.DOCKER in kinds
        assert RuntimeKind.PODMAN not in kinds


class TestFactoryCustomInjection:
    def test_custom_tty_detector_factory_is_used(self):
        from oci_runtime.factory import RuntimeFactoryConfig
        from oci_runtime.domain.enums import RuntimeKind
        from oci_runtime.domain.types import RuntimePreference
        from oci_runtime.ports.capabilities import RuntimeCapabilities
        from oci_runtime.ports.aggregates import Managers, Parsers
        from oci_runtime.ports.parsers import ContainerParser, ImageParser
        from oci_runtime.ports.parsers import ParsingError
        from oci_runtime.ports.provider import RuntimeProvider
        from oci_runtime.adapters.managers.container import CliContainerManager
        from oci_runtime.adapters.managers.image import CliImageManager
        from oci_runtime.adapters.managers.volume import CliVolumeManager
        from oci_runtime.adapters.managers.network import CliNetworkManager
        from tests.helpers.mock_transport import FakeTtyDetector, MockPtyTransport, RecordingTransport
        from oci_runtime.domain.types import RawExecResult

        class FakeCP(ContainerParser):
            def parse_inspect(self, raw): raise ParsingError(raw)
            def parse_list(self, raw): return []
            def parse_prune(self, raw): return PruneResult()
            def is_not_found_error(self, stderr): return False

        class FakeIP(ImageParser):
            def parse_inspect(self, raw): raise ParsingError(raw)
            def parse_list(self, raw): return []
            def parse_build_output(self, raw): return ""
            def parse_digest_from_pull(self, raw): return ""
            def parse_prune(self, raw): return PruneResult()
            def is_not_found_error(self, stderr): return False

        custom_tty = FakeTtyDetector(is_tty=True)
        config = RuntimeFactoryConfig(
            tty_detector_factory=lambda: custom_tty,
            output_stream_factory=lambda: __import__("io").BytesIO(),
        )
        factory = RuntimeFactory(config)
        engine = factory.create(RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker"))
        assert engine.containers._tty_detector is custom_tty

    def test_custom_output_stream_factory_is_used(self):
        import io
        from oci_runtime.factory import RuntimeFactoryConfig
        from oci_runtime.domain.enums import RuntimeKind
        from oci_runtime.domain.types import RuntimePreference
        custom_stream = io.BytesIO()
        config = RuntimeFactoryConfig(
            tty_detector_factory=lambda: FakeTtyDetector(),
            output_stream_factory=lambda: custom_stream,
        )
        factory = RuntimeFactory(config)
        engine = factory.create(RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker"))
        assert engine.containers._output_stream is custom_stream
