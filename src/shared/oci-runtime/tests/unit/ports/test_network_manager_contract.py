from abc import ABC, abstractmethod

from oci_runtime.domain.exceptions import NetworkNotFoundError
from oci_runtime.domain.types import NetworkInfo
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.managers import NetworkManager
from oci_runtime.ports.parsers import NetworkParser
from oci_runtime.ports.transport import ExecResult, Transport
from tests.helpers.mock_parsers import MockNetworkParser
from tests.helpers.mock_transport import FailingTransport, RecordingTransport


class NetworkManagerContractTest(ABC):
    @abstractmethod
    def make_manager(self, transport: Transport, parser: NetworkParser, caps: RuntimeCapabilities) -> NetworkManager:
        ...

    def _defaults(self):
        t = RecordingTransport("docker")
        caps = RuntimeCapabilities()
        return self.make_manager(t, MockNetworkParser(), caps), t

    def _failing(self, stderr="No such network: nonexistent"):
        t = FailingTransport("docker", stderr=stderr)
        return self.make_manager(t, MockNetworkParser(), RuntimeCapabilities()), t

    def test_base_is_abstract(self):
        assert NetworkManagerContractTest.make_manager.__isabstractmethod__

    def test_create_returns_str(self):
        mgr, t = self._defaults()
        t._responses["docker network create --driver bridge mynet"] = ExecResult(0, b"mynet\n", b"")
        result = mgr.create("mynet")
        assert isinstance(result, str)

    def test_remove_returns_none(self):
        mgr, t = self._defaults()
        t._responses["docker network rm mynet"] = ExecResult(0, b"", b"")
        result = mgr.remove("mynet")
        assert result is None

    def test_connect_returns_none(self):
        mgr, t = self._defaults()
        t._responses["docker network connect mynet c1"] = ExecResult(0, b"", b"")
        result = mgr.connect("mynet", "c1")
        assert result is None

    def test_disconnect_returns_none(self):
        mgr, t = self._defaults()
        t._responses["docker network disconnect mynet c1"] = ExecResult(0, b"", b"")
        result = mgr.disconnect("mynet", "c1")
        assert result is None

    def test_exists_returns_bool(self):
        mgr, t = self._defaults()
        t._responses["docker network inspect mynet"] = ExecResult(0, b'dummy', b"")
        result = mgr.exists("mynet")
        assert isinstance(result, bool)

    def test_inspect_returns_network_info(self):
        mgr, t = self._defaults()
        t._responses["docker network inspect mynet"] = ExecResult(0, b"dummy", b"")
        result = mgr.inspect("mynet")
        assert isinstance(result, NetworkInfo)

    def test_list_returns_list(self):
        mgr, t = self._defaults()
        t._responses["docker network list"] = ExecResult(0, b"dummy", b"")
        result = mgr.list()
        assert isinstance(result, list)

    def test_prune_returns_dict(self):
        mgr, t = self._defaults()
        t._responses["docker network prune --force"] = ExecResult(0, b"", b"")
        result = mgr.prune()
        assert isinstance(result, dict)

    def test_inspect_nonexistent_raises_not_found(self):
        mgr, _ = self._failing()
        try:
            mgr.inspect("nonexistent")
            assert False, "Expected NetworkNotFoundError"
        except NetworkNotFoundError:
            pass


class TestCliNetworkManagerContract(NetworkManagerContractTest):
    def make_manager(self, transport, parser, caps) -> NetworkManager:
        from oci_runtime.adapters.managers.network import CliNetworkManager
        return CliNetworkManager(transport, parser, caps)
