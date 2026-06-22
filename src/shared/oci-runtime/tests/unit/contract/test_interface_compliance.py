from abc import ABC
from dataclasses import FrozenInstanceError, is_dataclass, fields
from unittest.mock import patch

import pytest

from oci_runtime.adapters.engine.cli import CliRuntime
from oci_runtime.adapters.managers.container import CliContainerManager
from oci_runtime.adapters.managers.image import CliImageManager
from oci_runtime.adapters.managers.network import CliNetworkManager
from oci_runtime.adapters.managers.volume import CliVolumeManager
from oci_runtime.adapters.transport.cli import CliTransport
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.parsers import ParsingError
from oci_runtime.domain.exceptions import (
    ContainerError,
    ContainerNotFoundError,
    ContainerRuntimeError,
    ImageError,
    ImageNotFoundError,
    NetworkError,
    NetworkNotFoundError,
    OciError,
    RuntimeNotAvailableError,
    VolumeError,
    VolumeNotFoundError,
)
from oci_runtime.domain.types import RuntimePreference
from oci_runtime.domain.capabilities import RuntimeCapabilities
from oci_runtime.ports.engine import ContainerEngine
from oci_runtime.factory import RuntimeFactoryConfig
from oci_runtime.ports.aggregates import Parsers
from oci_runtime.ports.managers import (
    ContainerManager,
    ImageManager,
    NetworkManager,
    VolumeManager,
)
from oci_runtime.ports.parsers import (
    ContainerParser,
    ImageParser,
    NetworkParser,
    VolumeParser,
)
from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.streaming import StreamingTransport
from oci_runtime.ports.transport import Transport
from oci_runtime.factory import RuntimeFactory
from tests.helpers.mock_transport import RecordingTransport, RecordingStreamingTransport, FakeTtyDetector


class TestTransportContract:
    def test_is_abc(self):
        assert issubclass(Transport, ABC)

    def test_has_all_abstract_methods(self):
        expected = {"execute", "get_runtime_binary", "probe"}
        actual = set(Transport.__abstractmethods__)
        assert actual == expected, f"Missing: {expected - actual}, Extra: {actual - expected}"

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            Transport()

    def test_concrete_subclass_must_implement_all(self):
        with pytest.raises(TypeError):
            type("BadTransport", (Transport,), {})()

    def test_cli_transport_implements_all(self):
        t = CliTransport("docker")
        assert isinstance(t, Transport)
        assert callable(t.execute)
        assert callable(t.get_runtime_binary)
        assert callable(t.probe)

    def test_cli_transport_get_runtime_binary(self):
        with patch("shutil.which", return_value="/usr/bin/docker"):
            t = CliTransport("docker")
            assert t.get_runtime_binary() == "/usr/bin/docker"

    def test_cli_transport_get_runtime_binary_custom(self):
        with patch("shutil.which", return_value="/usr/local/bin/podman"):
            t = CliTransport("/usr/local/bin/podman")
            assert t.get_runtime_binary() == "/usr/local/bin/podman"

    def test_recording_transport_implements_transport(self):
        t = RecordingTransport("docker")
        assert isinstance(t, Transport)
        assert callable(t.execute)
        assert callable(t.get_runtime_binary)
        assert callable(t.probe)

    def test_recording_transport_records_calls(self):
        t = RecordingTransport("docker")
        result = t.execute(["docker", "ps"])
        assert len(t.calls) == 1
        assert t.calls[0].command == ["docker", "ps"]
        assert isinstance(result, RawExecResult)

    def test_exec_result_is_dataclass(self):
        assert is_dataclass(RawExecResult)

    def test_exec_result_has_correct_fields(self):
        fs = {f.name: f.type for f in fields(RawExecResult)}
        assert fs == {"returncode": int, "stdout": bytes, "stderr": bytes}

    def test_exec_result_construct(self):
        r = RawExecResult(returncode=0, stdout=b"out", stderr=b"err")
        assert r.returncode == 0
        assert r.stdout == b"out"
        assert r.stderr == b"err"


class TestStreamingTransportContract:
    def test_is_abc(self):
        assert issubclass(StreamingTransport, ABC)

    def test_has_all_abstract_methods(self):
        expected = {"stream"}
        actual = set(StreamingTransport.__abstractmethods__)
        assert actual == expected, f"Missing: {expected - actual}, Extra: {actual - expected}"

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            StreamingTransport()

    def test_concrete_subclass_must_implement_all(self):
        with pytest.raises(TypeError):
            type("BadStreamingTransport", (StreamingTransport,), {})()

    def test_recording_streaming_transport_implements_all(self):
        s = RecordingStreamingTransport("docker")
        assert isinstance(s, StreamingTransport)
        assert callable(s.stream)

    def test_recording_streaming_transport_records_calls(self):
        s = RecordingStreamingTransport("docker")
        result = s.stream(["docker", "ps"])
        assert len(s.calls) == 1
        assert s.calls[0].command == ["docker", "ps"]
        assert isinstance(result, RawExecResult)


class TestEngineContract:
    def test_is_abc(self):
        assert issubclass(ContainerEngine, ABC)

    def test_has_all_abstract_properties(self):
        expected_props = {"images", "containers", "volumes", "networks", "capabilities"}
        actual = {m for m in ContainerEngine.__abstractmethods__ if isinstance(getattr(ContainerEngine, m, None), property)}
        assert actual == expected_props, f"Missing props: {expected_props - actual}, Extra: {actual - expected_props}"

    def test_has_all_abstract_methods(self):
        expected_methods = {"is_available", "version"}
        actual = {m for m in ContainerEngine.__abstractmethods__ if not isinstance(getattr(ContainerEngine, m, None), property)}
        assert actual == expected_methods, f"Missing methods: {expected_methods - actual}, Extra: {actual - expected_methods}"

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            ContainerEngine()

    def test_cli_runtime_implements_all(self):
        transport = RecordingTransport("docker")
        caps = RuntimeCapabilities()
        from unittest.mock import MagicMock
        runtime = CliRuntime(
            transport=transport,
            image_manager=MagicMock(spec=ImageManager),
            container_manager=MagicMock(spec=ContainerManager),
            volume_manager=MagicMock(spec=VolumeManager),
            network_manager=MagicMock(spec=NetworkManager),
            caps=caps,
        )
        assert isinstance(runtime, ContainerEngine)
        assert runtime.images is not None
        assert runtime.containers is not None
        assert runtime.volumes is not None
        assert runtime.networks is not None
        assert runtime.capabilities is caps
        assert callable(runtime.is_available)
        assert callable(runtime.version)


class TestImageManagerContract:
    def test_is_abc(self):
        assert issubclass(ImageManager, ABC)

    def test_has_all_abstract_methods(self):
        expected = {"build", "tag", "push", "pull", "remove", "exists", "inspect", "list", "prune"}
        actual = set(ImageManager.__abstractmethods__)
        assert actual == expected, f"Missing: {expected - actual}, Extra: {actual - expected}"

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            ImageManager()

    def test_cli_image_manager_implements_all(self):
        transport = RecordingTransport("docker")
        caps = RuntimeCapabilities()
        from oci_runtime.adapters.parser.docker import DockerImageParser
        mgr = CliImageManager(transport, DockerImageParser(), caps)
        assert isinstance(mgr, ImageManager)
        assert callable(mgr.build)
        assert callable(mgr.tag)
        assert callable(mgr.push)
        assert callable(mgr.pull)
        assert callable(mgr.remove)
        assert callable(mgr.exists)
        assert callable(mgr.inspect)
        assert callable(mgr.list)
        assert callable(mgr.prune)


class TestContainerManagerContract:
    def test_is_abc(self):
        assert issubclass(ContainerManager, ABC)

    def test_has_all_abstract_methods(self):
        expected = {"run", "start", "stop", "restart", "remove", "exists", "inspect", "list", "logs", "exec_container", "prune"}
        actual = set(ContainerManager.__abstractmethods__)
        assert actual == expected, f"Missing: {expected - actual}, Extra: {actual - expected}"

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            ContainerManager()

    def test_cli_container_manager_implements_all(self):
        transport = RecordingTransport("docker")
        streaming = RecordingStreamingTransport("docker")
        caps = RuntimeCapabilities()
        from oci_runtime.adapters.parser.docker import DockerContainerParser
        mgr = CliContainerManager(transport, DockerContainerParser(), caps, streaming=streaming, tty_detector=FakeTtyDetector())
        assert isinstance(mgr, ContainerManager)
        assert callable(mgr.run)
        assert callable(mgr.start)
        assert callable(mgr.stop)
        assert callable(mgr.restart)
        assert callable(mgr.remove)
        assert callable(mgr.exists)
        assert callable(mgr.inspect)
        assert callable(mgr.list)
        assert callable(mgr.logs)
        assert callable(mgr.exec_container)
        assert callable(mgr.prune)


class TestVolumeManagerContract:
    def test_is_abc(self):
        assert issubclass(VolumeManager, ABC)

    def test_has_all_abstract_methods(self):
        expected = {"create", "remove", "exists", "inspect", "list", "prune"}
        actual = set(VolumeManager.__abstractmethods__)
        assert actual == expected, f"Missing: {expected - actual}, Extra: {actual - expected}"

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            VolumeManager()

    def test_cli_volume_manager_implements_all(self):
        transport = RecordingTransport("docker")
        caps = RuntimeCapabilities()
        from oci_runtime.adapters.parser.docker import DockerVolumeParser
        mgr = CliVolumeManager(transport, DockerVolumeParser(), caps)
        assert isinstance(mgr, VolumeManager)
        assert callable(mgr.create)
        assert callable(mgr.remove)
        assert callable(mgr.exists)
        assert callable(mgr.inspect)
        assert callable(mgr.list)
        assert callable(mgr.prune)


class TestNetworkManagerContract:
    def test_is_abc(self):
        assert issubclass(NetworkManager, ABC)

    def test_has_all_abstract_methods(self):
        expected = {"create", "remove", "connect", "disconnect", "exists", "inspect", "list", "prune"}
        actual = set(NetworkManager.__abstractmethods__)
        assert actual == expected, f"Missing: {expected - actual}, Extra: {actual - expected}"

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            NetworkManager()

    def test_cli_network_manager_implements_all(self):
        transport = RecordingTransport("docker")
        caps = RuntimeCapabilities()
        from oci_runtime.adapters.parser.docker import DockerNetworkParser
        mgr = CliNetworkManager(transport, DockerNetworkParser(), caps)
        assert isinstance(mgr, NetworkManager)
        assert callable(mgr.create)
        assert callable(mgr.remove)
        assert callable(mgr.connect)
        assert callable(mgr.disconnect)
        assert callable(mgr.exists)
        assert callable(mgr.inspect)
        assert callable(mgr.list)
        assert callable(mgr.prune)


class TestParserContract:
    def test_container_parser_is_abc(self):
        assert issubclass(ContainerParser, ABC)

    def test_container_parser_abstract_methods(self):
        expected = {"parse_inspect", "parse_list", "parse_prune", "is_not_found_error"}
        actual = set(ContainerParser.__abstractmethods__)
        assert actual == expected

    def test_container_parser_cannot_instantiate(self):
        with pytest.raises(TypeError):
            ContainerParser()

    def test_image_parser_is_abc(self):
        assert issubclass(ImageParser, ABC)

    def test_image_parser_abstract_methods(self):
        expected = {"parse_inspect", "parse_list", "parse_build_output", "parse_id_from_pull", "parse_prune", "is_not_found_error"}
        actual = set(ImageParser.__abstractmethods__)
        assert actual == expected

    def test_volume_parser_is_abc(self):
        assert issubclass(VolumeParser, ABC)

    def test_volume_parser_abstract_methods(self):
        expected = {"parse_inspect", "parse_list", "parse_prune", "is_not_found_error"}
        actual = set(VolumeParser.__abstractmethods__)
        assert actual == expected

    def test_network_parser_is_abc(self):
        assert issubclass(NetworkParser, ABC)

    def test_network_parser_abstract_methods(self):
        expected = {"parse_inspect", "parse_list", "parse_prune", "is_not_found_error"}
        actual = set(NetworkParser.__abstractmethods__)
        assert actual == expected

    def test_docker_parsers_implement_all(self):
        from oci_runtime.adapters.parser.docker import (
            DockerContainerParser,
            DockerImageParser,
            DockerNetworkParser,
            DockerVolumeParser,
        )
        for cls in [DockerContainerParser, DockerImageParser, DockerNetworkParser, DockerVolumeParser]:
            assert len(cls.__abstractmethods__) == 0, f"{cls.__name__} still has abstract methods: {cls.__abstractmethods__}"

    def test_podman_parsers_implement_all(self):
        from oci_runtime.adapters.parser.podman import (
            PodmanContainerParser,
            PodmanImageParser,
            PodmanNetworkParser,
            PodmanVolumeParser,
        )
        for cls in [PodmanContainerParser, PodmanImageParser, PodmanNetworkParser, PodmanVolumeParser]:
            assert len(cls.__abstractmethods__) == 0, f"{cls.__name__} still has abstract methods: {cls.__abstractmethods__}"


class TestExceptionHierarchyContract:
    def test_container_error_is_base(self):
        assert issubclass(ContainerError, Exception)

    def test_image_error_chain(self):
        assert issubclass(ImageError, OciError)
        assert not issubclass(ImageError, ContainerError)
        assert issubclass(ImageNotFoundError, ImageError)

    def test_container_not_found_chain(self):
        assert issubclass(ContainerNotFoundError, ContainerError)

    def test_volume_error_chain(self):
        assert issubclass(VolumeError, OciError)
        assert not issubclass(VolumeError, ContainerError)
        assert issubclass(VolumeNotFoundError, VolumeError)

    def test_network_error_chain(self):
        assert issubclass(NetworkError, OciError)
        assert not issubclass(NetworkError, ContainerError)
        assert issubclass(NetworkNotFoundError, NetworkError)

    def test_runtime_not_available_chain(self):
        assert issubclass(RuntimeNotAvailableError, OciError)
        assert not issubclass(RuntimeNotAvailableError, ContainerError)

    def test_container_runtime_error_chain(self):
        assert issubclass(ContainerRuntimeError, ContainerError)

    def test_parsing_error_chain(self):
        assert issubclass(ParsingError, OciError)
        assert not issubclass(ParsingError, ContainerError)

    def test_not_found_includes_entity_name(self):
        err = ImageNotFoundError("my-image")
        assert err.image_name == "my-image"
        assert "my-image" in str(err)

        err = ContainerNotFoundError("my-container")
        assert err.container_id == "my-container"
        assert "my-container" in str(err)

        err = VolumeNotFoundError("my-volume")
        assert err.volume_name == "my-volume"
        assert "my-volume" in str(err)

        err = NetworkNotFoundError("my-network")
        assert err.network_name == "my-network"
        assert "my-network" in str(err)

    def test_container_error_includes_command_and_exit_code(self):
        err = ContainerRuntimeError(
            message="something went wrong",
            command=["docker", "run", "alpine"],
            exit_code=1,
            stderr="Error: something went wrong",
        )
        assert err.command == ["docker", "run", "alpine"]
        assert err.exit_code == 1
        assert err.stderr == "Error: something went wrong"
        assert "docker run alpine" in str(err)
        assert "exit code: 1" in str(err).lower() or "Exit code: 1" in str(err)

    def test_runtime_not_available_includes_runtime_name(self):
        err = RuntimeNotAvailableError("podman")
        assert err.runtime == "podman"
        assert "podman" in str(err)

    def test_parsing_error_includes_raw(self):
        err = ParsingError("bad json", message="could not parse")
        assert err.raw == "bad json"
        assert "could not parse" in str(err)


class TestFactoryContract:
    def test_factory_create_returns_container_engine(self):
        from unittest.mock import patch
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = b"Docker version 24.0.0"
                mock_run.return_value.stderr = b""
                engine = RuntimeFactory().create(RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker"))
                assert isinstance(engine, ContainerEngine)

    def test_factory_available_returns_list(self):
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = b"Docker version 24.0.0"
                mock_run.return_value.stderr = b""
                available = RuntimeFactory().available()
                assert isinstance(available, list)
                if available:
                    assert isinstance(available[0], RuntimePreference)

    def test_factory_config_is_dataclass(self):
        assert is_dataclass(RuntimeFactoryConfig)

    def test_factory_config_defaults_are_none(self):
        cfg = RuntimeFactoryConfig()
        assert cfg.transport_factory is None
        assert cfg.streaming_transport_factory is None
        assert cfg.runtime_cls is None
        assert cfg.discovery_factory is None

    def test_parsers_is_frozen_dataclass(self):
        assert is_dataclass(Parsers)
        from oci_runtime.adapters.parser.docker import DockerContainerParser
        parsers = Parsers(
            container_parser=DockerContainerParser(),
            image_parser=DockerContainerParser(),
            volume_parser=DockerContainerParser(),
            network_parser=DockerContainerParser(),
        )
        with pytest.raises(FrozenInstanceError):
            parsers.container_parser = None
