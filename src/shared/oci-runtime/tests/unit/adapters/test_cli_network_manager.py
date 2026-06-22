from unittest.mock import MagicMock

from oci_runtime.adapters.managers.network import CliNetworkManager
from oci_runtime.domain.types import NetworkInfo, PruneResult
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.parsers import NetworkParser
from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.transport import Transport


class _MockParser(NetworkParser):
    def parse_inspect(self, raw: str) -> NetworkInfo:
        return NetworkInfo(id="n1", name="net1", driver="bridge", scope="local")
    def parse_list(self, raw: str) -> list[NetworkInfo]:
        return [NetworkInfo(id="n1", name="net1", driver="bridge", scope="local")]
    def parse_prune(self, raw: str) -> PruneResult:
        return PruneResult()
    def is_not_found_error(self, stderr: str) -> bool:
        return "No such network" in stderr



class TestCliNetworkManager:
    def setup_method(self):
        self.transport = MagicMock(spec=Transport)
        self.transport.get_runtime_binary.return_value = "docker"
        self.transport.execute.return_value = RawExecResult(returncode=0, stdout=b"test-network", stderr=b"")
        self.parser = _MockParser()
        self.caps = RuntimeCapabilities()
        self.manager = CliNetworkManager(self.transport, self.parser, self.caps)

    def test_create_returns_str(self):
        name = self.manager.create("my-net")
        assert isinstance(name, str)
        assert name == "test-network"

    def test_create_calls_transport_with_correct_command(self):
        self.manager.create("my-net")
        self.transport.execute.assert_called_once_with(
            ["docker", "network", "create", "--driver", "bridge", "my-net"]
        )

    def test_create_calls_transport_with_custom_driver(self):
        self.manager.create("my-net", driver="nfs")
        self.transport.execute.assert_called_once_with(
            ["docker", "network", "create", "--driver", "nfs", "my-net"]
        )

    def test_create_calls_transport_with_labels(self):
        self.manager.create("my-net", labels={"env": "test", "project": "foo"})
        self.transport.execute.assert_called_once_with(
            ["docker", "network", "create", "--driver", "bridge", "my-net",
             "--label", "env=test", "--label", "project=foo"]
        )

    def test_list_returns_list_of_network_info(self):
        networks = self.manager.list()
        assert isinstance(networks, list)

    def test_list_calls_transport(self):
        self.manager.list()
        self.transport.execute.assert_called_once()

    def test_inspect_returns_network_info(self):
        info = self.manager.inspect("bridge")
        assert info.name == "net1"

    def test_inspect_calls_transport(self):
        self.manager.inspect("bridge")
        self.transport.execute.assert_called_once()
