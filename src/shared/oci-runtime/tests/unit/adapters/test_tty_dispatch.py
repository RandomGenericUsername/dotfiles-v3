from unittest.mock import MagicMock, patch

import pytest

from oci_runtime.adapters.managers.container import CliContainerManager
from oci_runtime.ports.parsers import ParsingError
from oci_runtime.domain.exceptions import ContainerRuntimeError
from oci_runtime.domain.types import PruneResult, RunConfig
from oci_runtime.domain.capabilities import RuntimeCapabilities
from oci_runtime.ports.parsers import ContainerParser
from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.transport import Transport
from oci_runtime.ports.streaming import StreamingTransport
from tests.helpers.mock_transport import FakeTtyDetector


class _MockParser(ContainerParser):
    def parse_inspect(self, raw: str):
        raise ParsingError(raw=raw)
    def parse_list(self, raw: str):
        return []
    def parse_prune(self, raw: str) -> PruneResult:
        return PruneResult()
    def is_not_found_error(self, stderr: str):
        return False


@pytest.fixture
def transport():
    t = MagicMock(spec=Transport)
    t.execute.return_value = RawExecResult(returncode=0, stdout=b"abc123", stderr=b"")
    t.get_runtime_binary.return_value = "docker"
    return t


@pytest.fixture
def manager(transport):
    caps = RuntimeCapabilities()
    parser = _MockParser()
    streaming = MagicMock(spec=StreamingTransport)
    streaming.stream.return_value = RawExecResult(returncode=0, stdout=b"abc123", stderr=b"")
    return CliContainerManager(transport, parser, caps, streaming=streaming, tty_detector=FakeTtyDetector())


class TestTtyDispatch:
    @patch("oci_runtime.adapters.managers.container.run_pty")
    def test_tty_true_calls_execute_pty(self, mock_run_pty, manager, transport):
        mock_run_pty.return_value.returncode = 0
        config = RunConfig(image="alpine", command=["bash"], tty=True, detach=False)
        result = manager.run(config)
        mock_run_pty.assert_called_once_with(
            ["docker", "run", "-t", "alpine", "bash"],
            output_stream=None,
        )
        assert result == ""

    def test_tty_false_calls_streaming_stream(self, manager, transport):
        config = RunConfig(image="alpine", command=["echo", "hi"], tty=False, detach=True)
        result = manager.run(config)
        manager._streaming.stream.assert_called_once()
        assert result == "abc123"

    def test_detach_and_tty_mutually_exclusive(self, manager, transport):
        with pytest.raises(ValueError, match="detach=True is mutually exclusive with tty/auto_tty"):
            RunConfig(image="alpine", command=["bash"], tty=True, detach=True)

    @patch("oci_runtime.adapters.managers.container.run_pty")
    def test_auto_tty_true_with_isatty_calls_execute_pty(self, mock_run_pty, manager, transport):
        mock_run_pty.return_value.returncode = 0
        tty_detector = FakeTtyDetector(is_tty=True)
        mgr = CliContainerManager(transport, _MockParser(), RuntimeCapabilities(), streaming=manager._streaming, tty_detector=tty_detector)
        config = RunConfig(image="alpine", command=["bash"], auto_tty=True, detach=False)
        result = mgr.run(config)
        mock_run_pty.assert_called_once()
        assert result == ""

    def test_auto_tty_true_without_isatty_calls_streaming(self, manager, transport):
        tty_detector = FakeTtyDetector(is_tty=False)
        mgr = CliContainerManager(transport, _MockParser(), RuntimeCapabilities(), streaming=manager._streaming, tty_detector=tty_detector)
        config = RunConfig(image="alpine", command=["echo", "hi"], auto_tty=True, detach=False)
        result = mgr.run(config)
        manager._streaming.stream.assert_called_once()
        assert result == "abc123"


class TestTtyReturnContract:
    @patch("oci_runtime.adapters.managers.container.run_pty")
    def test_tty_path_returns_empty_string(self, mock_run_pty, manager, transport):
        mock_run_pty.return_value.returncode = 0
        config = RunConfig(image="alpine", command=["bash"], tty=True, detach=False)
        result = manager.run(config)
        assert result == ""

    def test_non_tty_path_returns_container_id(self, manager, transport):
        config = RunConfig(image="alpine", command=["echo", "hi"], tty=False, detach=True)
        result = manager.run(config)
        assert result == "abc123"

    def test_stream_output_returns_empty(self, manager, transport):
        streaming = MagicMock(spec=StreamingTransport)
        streaming.stream.return_value = RawExecResult(returncode=0, stdout=b"", stderr=b"")
        caps = RuntimeCapabilities()
        parser = _MockParser()
        mgr = CliContainerManager(transport, parser, caps, streaming=streaming, tty_detector=FakeTtyDetector())
        config = RunConfig(image="alpine", stream_output=True, tty=False, detach=True)
        result = mgr.run(config)
        assert result == ""


class TestTtyEdgeCases:
    @patch("oci_runtime.adapters.managers.container.run_pty")
    def test_execute_pty_failure_propagates(self, mock_run_pty, manager, transport):
        mock_run_pty.side_effect = ContainerRuntimeError("PTY failed", command=["docker"])
        config = RunConfig(image="alpine", command=["bash"], tty=True, detach=False)
        with pytest.raises(ContainerRuntimeError, match="PTY failed"):
            manager.run(config)

    @patch("oci_runtime.adapters.managers.container.run_pty")
    def test_effective_tty_with_default_flags(self, mock_run_pty, manager, transport):
        caps = RuntimeCapabilities(default_run_flags=("--userns=keep-id",))
        parser = _MockParser()
        streaming = MagicMock(spec=StreamingTransport)
        streaming.stream.return_value = RawExecResult(returncode=0, stdout=b"abc123", stderr=b"")
        m = CliContainerManager(transport, parser, caps, streaming=streaming, tty_detector=FakeTtyDetector())
        mock_run_pty.return_value.returncode = 0
        config = RunConfig(image="alpine", command=["bash"], tty=True, detach=False)
        m.run(config)
        mock_run_pty.assert_called_once_with(
            ["docker", "run", "--userns=keep-id", "-t", "alpine", "bash"],
            output_stream=None,
        )
