from unittest.mock import MagicMock

from oci_runtime.adapters.managers.volume import CliVolumeManager
from oci_runtime.domain.types import PruneResult, VolumeInfo
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.parsers import VolumeParser
from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.transport import Transport


class _MockParser(VolumeParser):
    def parse_inspect(self, raw: str) -> VolumeInfo:
        return VolumeInfo(name="my-vol", driver="local")
    def parse_list(self, raw: str) -> list[VolumeInfo]:
        return [VolumeInfo(name="my-vol", driver="local")]
    def parse_prune(self, raw: str) -> PruneResult:
        return PruneResult()
    def is_not_found_error(self, stderr: str) -> bool:
        return "No such volume" in stderr


class TestCliVolumeManager:
    def setup_method(self):
        self.transport = MagicMock(spec=Transport)
        self.transport.get_runtime_binary.return_value = "docker"
        self.transport.execute.return_value = RawExecResult(returncode=0, stdout=b"test-volume", stderr=b"")
        self.parser = _MockParser()
        self.caps = RuntimeCapabilities()
        self.manager = CliVolumeManager(self.transport, self.parser, self.caps)

    def test_decode_bytes_converts_bytes_to_str(self):
        result = self.manager._decode_bytes(b"my-vol")
        assert isinstance(result, str)
        assert result == "my-vol"

    def test_decode_bytes_handles_non_utf8(self):
        result = self.manager._decode_bytes(b"valid\xff\xfe")
        assert isinstance(result, str)
        assert "\ufffd" in result

    def test_decode_bytes_strip_preserved(self):
        result = self.manager._decode_bytes(b"my-vol\n").strip()
        assert isinstance(result, str)
        assert result == "my-vol"

    def test_create_returns_str(self):
        name = self.manager.create("my-vol")
        assert isinstance(name, str)
        assert name == "test-volume"

    def test_create_calls_transport_with_correct_command(self):
        self.manager.create("my-vol")
        self.transport.execute.assert_called_once_with(
            ["docker", "volume", "create", "--driver", "local", "my-vol"]
        )

    def test_create_calls_transport_with_custom_driver(self):
        self.manager.create("my-vol", driver="nfs")
        self.transport.execute.assert_called_once_with(
            ["docker", "volume", "create", "--driver", "nfs", "my-vol"]
        )

    def test_create_calls_transport_with_labels(self):
        self.manager.create("my-vol", labels={"env": "test", "project": "foo"})
        self.transport.execute.assert_called_once_with(
            ["docker", "volume", "create", "--driver", "local", "my-vol",
             "--label", "env=test", "--label", "project=foo"]
        )

    def test_list_returns_list_of_volume_info(self):
        volumes = self.manager.list()
        assert isinstance(volumes, list)

    def test_list_calls_transport(self):
        self.manager.list()
        self.transport.execute.assert_called_once()

    def test_inspect_returns_volume_info(self):
        info = self.manager.inspect("my-vol")
        assert info.name == "my-vol"

    def test_inspect_calls_transport(self):
        self.manager.inspect("my-vol")
        self.transport.execute.assert_called_once()
