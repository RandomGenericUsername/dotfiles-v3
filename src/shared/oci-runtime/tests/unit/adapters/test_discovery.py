from unittest.mock import MagicMock, patch

import pytest

from oci_runtime.adapters.discovery.cli import CliRuntimeDiscovery
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.domain.exceptions import RuntimeNotAvailableError
from oci_runtime.factory import RuntimeFactory
from oci_runtime.domain.types import RuntimePreference
from oci_runtime.ports.discovery import RuntimeDiscovery
from oci_runtime.ports.factory import RuntimeFactoryConfig
from oci_runtime.ports.transport import Transport


class TestRuntimeDiscoveryPort:
    def test_abc_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            RuntimeDiscovery()

    def test_abc_has_abstract_available_method(self):
        assert hasattr(RuntimeDiscovery, "available")
        assert getattr(RuntimeDiscovery.available, "__isabstractmethod__", False)


class TestCliRuntimeDiscovery:
    def test_available_returns_all_when_all_probe_true(self):
        docker_transport = MagicMock(spec=Transport)
        docker_transport.probe.return_value = True
        podman_transport = MagicMock(spec=Transport)
        podman_transport.probe.return_value = True

        def factory(binary: str):
            return {"docker": docker_transport, "podman": podman_transport}[binary]

        discovery = CliRuntimeDiscovery(factory)
        result = discovery.available()

        assert len(result) == 2
        kinds = {p.kind for p in result}
        assert kinds == {RuntimeKind.DOCKER, RuntimeKind.PODMAN}

    def test_available_returns_only_probe_true(self):
        docker_transport = MagicMock(spec=Transport)
        docker_transport.probe.return_value = True
        podman_transport = MagicMock(spec=Transport)
        podman_transport.probe.return_value = False

        def factory(binary: str):
            return {"docker": docker_transport, "podman": podman_transport}[binary]

        discovery = CliRuntimeDiscovery(factory)
        result = discovery.available()

        assert len(result) == 1
        assert result[0].kind == RuntimeKind.DOCKER

    def test_available_returns_empty_when_none_probe_true(self):
        docker_transport = MagicMock(spec=Transport)
        docker_transport.probe.return_value = False
        podman_transport = MagicMock(spec=Transport)
        podman_transport.probe.return_value = False

        def factory(binary: str):
            return {"docker": docker_transport, "podman": podman_transport}[binary]

        discovery = CliRuntimeDiscovery(factory)
        result = discovery.available()

        assert result == []

    def test_available_skips_on_transport_factory_failure(self):
        def factory(binary: str):
            if binary == "docker":
                return MagicMock(spec=Transport, probe=lambda: True)
            raise FileNotFoundError(f"{binary} not found")

        discovery = CliRuntimeDiscovery(factory)
        result = discovery.available()

        assert len(result) == 1
        assert result[0].kind == RuntimeKind.DOCKER

    def test_available_skips_on_transport_probe_exception(self):
        transport = MagicMock(spec=Transport)
        transport.probe.side_effect = RuntimeNotAvailableError("boom")

        def factory(binary: str):
            return transport

        discovery = CliRuntimeDiscovery(factory)
        result = discovery.available()

        assert result == []

    def test_available_returns_runtime_preference_objects(self):
        transport = MagicMock(spec=Transport)
        transport.probe.return_value = True

        def factory(binary: str):
            return transport

        discovery = CliRuntimeDiscovery(factory)
        result = discovery.available()

        assert all(isinstance(p, RuntimePreference) for p in result)
        assert all(p.binary == p.kind.value for p in result)

    def test_available_probe_called_with_correct_binary(self):
        docker_t = MagicMock(spec=Transport)
        podman_t = MagicMock(spec=Transport)
        docker_t.probe.return_value = True
        podman_t.probe.return_value = True

        called_binaries = []

        def factory(binary: str):
            called_binaries.append(binary)
            return {"docker": docker_t, "podman": podman_t}[binary]

        discovery = CliRuntimeDiscovery(factory)
        discovery.available()

        assert "docker" in called_binaries
        assert "podman" in called_binaries


class TestDiscoveryViaFactory:
    def test_factory_discovery_returns_runtime_discovery(self):
        factory = RuntimeFactory()
        assert isinstance(factory.discovery, RuntimeDiscovery)

    def test_factory_available_delegates_to_discovery(self):
        mock_discovery = MagicMock(spec=RuntimeDiscovery)
        mock_discovery.available.return_value = [
            RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker"),
        ]

        config = RuntimeFactoryConfig(
            discovery_factory=lambda tf: mock_discovery,
            transport_factory=lambda b: MagicMock(spec=Transport),
        )
        factory = RuntimeFactory(config=config)

        result = factory.available()

        mock_discovery.available.assert_called_once()
        assert len(result) == 1
        assert result[0].kind == RuntimeKind.DOCKER

    def test_factory_available_still_works_with_default_discovery(self):
        with patch("subprocess.run", return_value=MagicMock(returncode=1)):
            factory = RuntimeFactory()
            result = factory.available()
            assert result == []
