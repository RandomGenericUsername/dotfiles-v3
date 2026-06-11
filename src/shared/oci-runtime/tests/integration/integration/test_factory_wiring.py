from unittest.mock import patch, MagicMock

import pytest

from oci_runtime import engines
from oci_runtime.adapters.engine.cli import CliRuntime
from oci_runtime.adapters.managers.container import CliContainerManager
from oci_runtime.adapters.managers.image import CliImageManager
from oci_runtime.adapters.managers.network import CliNetworkManager
from oci_runtime.adapters.managers.volume import CliVolumeManager
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
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.domain.exceptions import RuntimeNotAvailableError
from oci_runtime.factory import RuntimeFactory
from oci_runtime.ports.capabilities import RuntimeCapabilities, RuntimePreference
from oci_runtime.ports.engine import ContainerEngine
from oci_runtime.ports.factory import Parsers, RuntimeFactoryConfig
from oci_runtime.ports.parsers import (
    ContainerParser,
    ImageParser,
    NetworkParser,
    VolumeParser,
)
from oci_runtime.ports.transport import ExecResult, Transport
from tests.helpers.mock_transport import RecordingTransport


class TestFactoryCreateEngine:
    @patch("shutil.which", return_value="/usr/bin/docker")
    @patch("subprocess.run")
    def test_create_docker_returns_cli_runtime(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0, stdout=b"Docker version 24.0.0", stderr=b"")
        runtime = RuntimeFactory().create(engines.docker_pref)
        assert isinstance(runtime, CliRuntime)
        assert isinstance(runtime, ContainerEngine)

    @patch("shutil.which", return_value="/usr/bin/podman")
    @patch("subprocess.run")
    def test_create_podman_returns_cli_runtime(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0, stdout=b"podman version 4.0.0", stderr=b"")
        runtime = RuntimeFactory().create(engines.podman_pref)
        assert isinstance(runtime, CliRuntime)

    @patch("shutil.which", return_value="/usr/bin/docker")
    @patch("subprocess.run")
    def test_create_docker_wires_docker_managers(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0, stdout=b"Docker version 24.0.0", stderr=b"")
        runtime = RuntimeFactory().create(engines.docker_pref)
        assert isinstance(runtime.images, CliImageManager)
        assert isinstance(runtime.containers, CliContainerManager)
        assert isinstance(runtime.volumes, CliVolumeManager)
        assert isinstance(runtime.networks, CliNetworkManager)

    @patch("shutil.which", return_value="/usr/bin/podman")
    @patch("subprocess.run")
    def test_create_podman_wires_podman_managers(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0, stdout=b"podman version 4.0.0", stderr=b"")
        runtime = RuntimeFactory().create(engines.podman_pref)
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

    def test_create_unavailable_engine_raises(self):
        bogus = RuntimePreference(kind=RuntimeKind.DOCKER, binary="nonexistent-runtime-xyz")
        with pytest.raises(RuntimeNotAvailableError):
            RuntimeFactory().create(bogus)


class TestFactoryConfigInjection:
    def test_custom_transport_factory_is_used(self):
        transport = RecordingTransport("docker", {
            "docker --version": ExecResult(returncode=0, stdout=b"Docker", stderr=b""),
        })
        config = RuntimeFactoryConfig(
            transport_factory=lambda _: transport,
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
            transport_factory=lambda _: transport,
            runtime_cls=MockEngine,
        )
        factory = RuntimeFactory(config)
        engine = factory.create(RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker"))
        assert isinstance(engine, MockEngine)

    def test_custom_parsers_are_used(self):
        class FakeContainerParser(ContainerParser):
            def parse_inspect(self, raw): return None
            def parse_list(self, raw): return []
            def parse_prune(self, raw): return {"deleted": 0, "reclaimed_bytes": 0}
            def is_not_found_error(self, stderr): return False

        class FakeImageParser(ImageParser):
            def parse_inspect(self, raw): return None
            def parse_list(self, raw): return []
            def parse_build_output(self, raw): return ""
            def parse_id_from_pull(self, raw): return ""
            def parse_prune(self, raw): return {"deleted": 0, "reclaimed_bytes": 0}
            def is_not_found_error(self, stderr): return False
        transport = RecordingTransport("docker", {
            "docker --version": ExecResult(returncode=0, stdout=b"Docker", stderr=b""),
        })
        config = RuntimeFactoryConfig(
            transport_factory=lambda _: transport,
            parser_provider=lambda kind: Parsers(
                container_parser=FakeContainerParser(),
                image_parser=FakeImageParser(),
                volume_parser=FakeContainerParser(),
                network_parser=FakeContainerParser(),
            ),
        )
        factory = RuntimeFactory(config)
        engine = factory.create(RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker"))
        assert engine.is_available() is True


class TestFactoryAvailable:
    @patch("shutil.which", return_value="/usr/bin/docker")
    @patch("subprocess.run")
    def test_available_returns_list_of_preferences(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0, stdout=b"Docker version 24.0.0", stderr=b"")
        available = RuntimeFactory().available()
        assert isinstance(available, list)
        assert all(isinstance(p, RuntimePreference) for p in available)

    @patch("subprocess.run")
    def test_available_only_returns_available_runtimes(self, mock_run):
        def run_side_effect(cmd, *args, **kwargs):
            if cmd[0] == "podman":
                raise FileNotFoundError("podman not found")
            return MagicMock(returncode=0, stdout=b"Docker", stderr=b"")
        mock_run.side_effect = run_side_effect
        available = RuntimeFactory().available()
        kinds = {p.kind for p in available}
        assert RuntimeKind.DOCKER in kinds
        assert RuntimeKind.PODMAN not in kinds
