import concurrent.futures


from oci_runtime.adapters.engine.cli import CliRuntime
from oci_runtime.adapters.managers.container import CliContainerManager
from oci_runtime.factory import RuntimeFactory
from oci_runtime.domain.types import RuntimePreference
from oci_runtime.domain.capabilities import RuntimeCapabilities
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.domain.types import RawExecResult
from tests.helpers.mock_parsers import MockContainerParser
from tests.helpers.mock_transport import RecordingTransport, RecordingStreamingTransport, FakeTtyDetector


INSPECT_JSON = b'[{"Id":"abc123","Name":"/c1","Config":{"Image":"alpine"},"State":{"Status":"running","ExitCode":0,"Running":true},"Created":"2024-01-01T00:00:00Z","HostConfig":{},"NetworkSettings":{"Ports":{}}}]'


class TestConcurrency:
    def test_concurrent_factory_create(self):
        pref = RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker")
        factory = RuntimeFactory()
        n = 20
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            engines = list(ex.map(lambda _: factory.create(pref), range(n)))
        assert len(engines) == n
        for engine in engines:
            assert isinstance(engine, CliRuntime)

    def test_concurrent_manager_calls(self):
        t = RecordingTransport("docker", {
            ("docker", "container", "inspect", "--format", "json", "ctr1"): RawExecResult(0, INSPECT_JSON, b""),
        })
        st = RecordingStreamingTransport("docker", {
            ("docker", "container", "inspect", "--format", "json", "ctr1"): RawExecResult(0, INSPECT_JSON, b""),
        })
        caps = RuntimeCapabilities()
        parser = MockContainerParser()
        mgr = CliContainerManager(t, parser, caps, streaming=st, tty_detector=FakeTtyDetector())
        n = 30
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            results = list(ex.map(lambda _: mgr.inspect("ctr1"), range(n)))
        assert len(results) == n
        for info in results:
            assert info.id == "abc"
        assert len(t.calls) == n

    def test_recording_transport_thread_safety(self):
        t = RecordingTransport("docker")
        n = 50
        def execute(_):
            return t.execute(["docker", "version"])
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(execute, range(n)))
        assert len(t.calls) == n
