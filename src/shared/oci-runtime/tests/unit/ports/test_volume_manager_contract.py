from abc import ABC, abstractmethod

from oci_runtime.domain.exceptions import VolumeNotFoundError
from oci_runtime.domain.types import PruneResult, VolumeInfo
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.managers import VolumeManager
from oci_runtime.ports.parsers import VolumeParser
from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.transport import Transport
from tests.helpers.mock_parsers import MockVolumeParser
from tests.helpers.mock_transport import RecordingTransport


class VolumeManagerContractTest(ABC):
    @abstractmethod
    def make_manager(self, transport: Transport, parser: VolumeParser, caps: RuntimeCapabilities) -> VolumeManager:
        ...

    def _defaults(self):
        t = RecordingTransport("docker")
        caps = RuntimeCapabilities()
        return self.make_manager(t, MockVolumeParser(), caps), t

    def _failing(self, stderr="No such volume: nonexistent"):
        cmd = ('docker', 'volume', 'inspect', '--format', 'json', 'nonexistent')
        t = RecordingTransport("docker", responses={
            cmd: RawExecResult(returncode=1, stdout=b"", stderr=stderr.encode()),
        })
        return self.make_manager(t, MockVolumeParser(), RuntimeCapabilities()), t

    def test_base_is_abstract(self):
        assert VolumeManagerContractTest.make_manager.__isabstractmethod__

    def test_create_returns_str(self):
        mgr, t = self._defaults()
        t._responses[("docker", "volume", "create", "--driver", "local", "myvol")] = RawExecResult(0, b"myvol\n", b"")
        result = mgr.create("myvol")
        assert isinstance(result, str)

    def test_remove_returns_none(self):
        mgr, t = self._defaults()
        t._responses[("docker", "volume", "rm", "myvol")] = RawExecResult(0, b"", b"")
        result = mgr.remove("myvol")
        assert result is None

    def test_exists_returns_bool(self):
        mgr, t = self._defaults()
        t._responses[("docker", "volume", "inspect", "--format", "json", "myvol")] = RawExecResult(0, b'dummy', b"")
        result = mgr.exists("myvol")
        assert isinstance(result, bool)

    def test_inspect_returns_volume_info(self):
        mgr, t = self._defaults()
        t._responses[("docker", "volume", "inspect", "--format", "json", "myvol")] = RawExecResult(0, b"dummy", b"")
        result = mgr.inspect("myvol")
        assert isinstance(result, VolumeInfo)

    def test_list_returns_list(self):
        mgr, t = self._defaults()
        t._responses[("docker", "volume", "list")] = RawExecResult(0, b"dummy", b"")
        result = mgr.list()
        assert isinstance(result, list)

    def test_prune_returns_dict(self):
        mgr, t = self._defaults()
        t._responses[("docker", "volume", "prune", "--force")] = RawExecResult(0, b"", b"")
        result = mgr.prune()
        assert isinstance(result, PruneResult)

    def test_inspect_nonexistent_raises_not_found(self):
        mgr, _ = self._failing()
        try:
            mgr.inspect("nonexistent")
            assert False, "Expected VolumeNotFoundError"
        except VolumeNotFoundError:
            pass


class TestCliVolumeManagerContract(VolumeManagerContractTest):
    def make_manager(self, transport, parser, caps) -> VolumeManager:
        from oci_runtime.adapters.managers.volume import CliVolumeManager
        return CliVolumeManager(transport, parser, caps)
