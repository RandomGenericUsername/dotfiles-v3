from abc import ABC, abstractmethod
from typing import Iterator

from oci_runtime.domain.enums import ContainerState
from oci_runtime.domain.exceptions import ContainerNotFoundError, ImageNotFoundError
from oci_runtime.domain.types import ContainerInfo, ExecOutput, PortMapping, RunConfig, VolumeMount
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.managers import ContainerManager
from oci_runtime.ports.parsers import ContainerParser
from oci_runtime.domain.types import ExecResult
from oci_runtime.ports.transport import Transport
from tests.helpers.mock_parsers import MockContainerParser
from tests.helpers.mock_transport import FailingTransport, RecordingTransport, RecordingStreamingTransport, FakeTtyDetector


class ContainerManagerContractTest(ABC):
    @abstractmethod
    def make_manager(self, transport: Transport, parser: ContainerParser, caps: RuntimeCapabilities, *, streaming, tty_detector) -> ContainerManager:
        ...

    def _defaults(self):
        t = RecordingTransport("docker")
        st = RecordingStreamingTransport("docker")
        caps = RuntimeCapabilities()
        return self.make_manager(t, MockContainerParser(), caps, streaming=st, tty_detector=FakeTtyDetector()), t, st

    def _failing(self, stderr="No such container: nonexistent"):
        t = FailingTransport("docker", stderr=stderr)
        st = RecordingStreamingTransport("docker")
        return self.make_manager(t, MockContainerParser(), RuntimeCapabilities(), streaming=st, tty_detector=FakeTtyDetector()), t

    def test_base_is_abstract(self):
        with_impl = [m for m in dir(ContainerManagerContractTest) if not m.startswith("_")]
        assert "make_manager" in with_impl
        assert ContainerManagerContractTest.make_manager.__isabstractmethod__

    def test_make_manager_returns_container_manager(self):
        mgr, t, st = self._defaults()
        assert isinstance(mgr, ContainerManager)

    def test_run_returns_str(self):
        mgr, t, st = self._defaults()
        st._responses["docker run"] = ExecResult(0, b"abc\n", b"")
        result = mgr.run(RunConfig(image="alpine"))
        assert isinstance(result, str)

    def test_start_returns_none(self):
        mgr, t, st = self._defaults()
        t._responses["docker start c1"] = ExecResult(0, b"", b"")
        result = mgr.start("c1")
        assert result is None

    def test_stop_returns_none(self):
        mgr, t, st = self._defaults()
        t._responses["docker stop -t 10 c1"] = ExecResult(0, b"", b"")
        result = mgr.stop("c1")
        assert result is None

    def test_restart_returns_none(self):
        mgr, t, st = self._defaults()
        t._responses["docker restart -t 10 c1"] = ExecResult(0, b"", b"")
        result = mgr.restart("c1")
        assert result is None

    def test_remove_returns_none(self):
        mgr, t, st = self._defaults()
        t._responses["docker rm c1"] = ExecResult(0, b"", b"")
        result = mgr.remove("c1")
        assert result is None

    def test_exists_returns_bool(self):
        mgr, t, st = self._defaults()
        t._responses["docker container inspect --format json c1"] = ExecResult(0, b'{"Id":"abc"}', b"")
        result = mgr.exists("c1")
        assert isinstance(result, bool)

    def test_inspect_returns_container_info(self):
        mgr, t, st = self._defaults()
        t._responses["docker container inspect --format json c1"] = ExecResult(0, b"dummy", b"")
        result = mgr.inspect("c1")
        assert isinstance(result, ContainerInfo)

    def test_list_returns_list(self):
        mgr, t, st = self._defaults()
        t._responses["docker container list"] = ExecResult(0, b"dummy", b"")
        result = mgr.list()
        assert isinstance(result, list)

    def test_logs_returns_iterator(self):
        mgr, t, st = self._defaults()
        t._responses["docker logs c1"] = ExecResult(0, b"log output\n", b"")
        result = mgr.logs("c1")
        assert isinstance(result, Iterator)

    def test_exec_container_returns_exec_output(self):
        mgr, t, st = self._defaults()
        t._responses["docker exec c1 ls"] = ExecResult(0, b"file1\n", b"")
        result = mgr.exec_container("c1", ["ls"])
        assert isinstance(result, ExecOutput)
        assert result.returncode == 0
        assert result.stdout == "file1\n"
        assert result.stderr == ""

    def test_prune_returns_dict(self):
        mgr, t, st = self._defaults()
        t._responses["docker container prune --force"] = ExecResult(0, b"", b"")
        result = mgr.prune()
        assert isinstance(result, dict)

    def test_inspect_nonexistent_raises_not_found(self):
        mgr, _ = self._failing()
        try:
            mgr.inspect("nonexistent")
            assert False, "Expected ContainerNotFoundError"
        except ContainerNotFoundError:
            pass

    def test_run_delegates_to_streaming(self):
        mgr, t, st = self._defaults()
        st._responses["docker run"] = ExecResult(0, b"abc\n", b"")
        mgr.run(RunConfig(image="alpine"))
        assert len(st.calls) > 0


class TestCliContainerManagerContract(ContainerManagerContractTest):
    def make_manager(self, transport, parser, caps, *, streaming, tty_detector) -> ContainerManager:
        from oci_runtime.adapters.managers.container import CliContainerManager
        return CliContainerManager(transport, parser, caps, streaming=streaming, tty_detector=tty_detector)
