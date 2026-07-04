from io import BytesIO
from unittest.mock import MagicMock

import pytest

from oci_runtime.ports.parsers import ParsingError
from oci_runtime.domain.exceptions import ContainerRuntimeError
from oci_runtime.domain.types import PruneResult, RunConfig
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.parsers import ContainerParser
from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.transport import Transport
from oci_runtime.ports.streaming import StreamingTransport
from tests.helpers.mock_transport import (
    FakeTtyDetector,
)


from tests.helpers.factory_helpers import container_mgr as _container_mgr


class _MockParser(ContainerParser):
    def parse_inspect(self, raw: str):
        raise ParsingError(raw=raw)

    def parse_list(self, raw: str):
        return []

    def parse_prune(self, raw: str) -> PruneResult:
        return PruneResult()

    def is_not_found_error(self, stderr: str):
        return False

    def is_auth_error(self, stderr: str) -> bool:
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
    streaming.stream.return_value = RawExecResult(
        returncode=0, stdout=b"abc123", stderr=b""
    )
    return _container_mgr(
        transport,
        parser,
        caps,
        streaming=streaming,
        output_stream=BytesIO(),
    )


class TestTtyDispatch:
    def test_tty_true_calls_execute_pty(self, manager, transport):
        manager._pty_transport.execute_pty = MagicMock(
            return_value=RawExecResult(returncode=0, stdout=b"", stderr=b"")
        )
        config = RunConfig(image="alpine", command=["bash"], tty=True, detach=False)
        result = manager.run(config)
        manager._pty_transport.execute_pty.assert_called_once()
        args, kwargs = manager._pty_transport.execute_pty.call_args
        assert kwargs["output_stream"] is not None
        assert kwargs["timeout"] is None
        assert result == ""

    def test_tty_false_calls_streaming_stream(self, manager, transport):
        config = RunConfig(
            image="alpine", command=["echo", "hi"], tty=False, detach=True
        )
        result = manager.run(config)
        manager._streaming.stream.assert_called_once()
        assert result == "abc123"

    def test_detach_and_tty_mutually_exclusive(self, manager, transport):
        with pytest.raises(
            ValueError, match="detach=True is mutually exclusive with tty/auto_tty"
        ):
            RunConfig(image="alpine", command=["bash"], tty=True, detach=True)

    def test_auto_tty_true_with_isatty_calls_execute_pty(self, manager, transport):
        tty_detector = FakeTtyDetector(is_tty=True)
        mgr = _container_mgr(
            transport,
            _MockParser(),
            RuntimeCapabilities(),
            streaming=manager._streaming,
            tty_detector=tty_detector,
            output_stream=BytesIO(),
        )
        mgr._pty_transport.execute_pty = MagicMock(
            return_value=RawExecResult(returncode=0, stdout=b"", stderr=b"")
        )
        config = RunConfig(
            image="alpine", command=["bash"], auto_tty=True, detach=False
        )
        result = mgr.run(config)
        mgr._pty_transport.execute_pty.assert_called_once()
        assert result == ""

    def test_auto_tty_true_without_isatty_calls_streaming(self, manager, transport):
        tty_detector = FakeTtyDetector(is_tty=False)
        mgr = _container_mgr(
            transport,
            _MockParser(),
            RuntimeCapabilities(),
            streaming=manager._streaming,
            tty_detector=tty_detector,
        )
        config = RunConfig(
            image="alpine", command=["echo", "hi"], auto_tty=True, detach=False
        )
        result = mgr.run(config)
        manager._streaming.stream.assert_called_once()
        assert result == "abc123"


class TestTtyReturnContract:
    def test_tty_path_returns_empty_string(self, manager, transport):
        manager._pty_transport.execute_pty = MagicMock(
            return_value=RawExecResult(returncode=0, stdout=b"", stderr=b"")
        )
        config = RunConfig(image="alpine", command=["bash"], tty=True, detach=False)
        result = manager.run(config)
        assert result == ""

    def test_non_tty_path_returns_container_id(self, manager, transport):
        config = RunConfig(
            image="alpine", command=["echo", "hi"], tty=False, detach=True
        )
        result = manager.run(config)
        assert result == "abc123"

    def test_stream_output_returns_empty(self, manager, transport):
        streaming = MagicMock(spec=StreamingTransport)
        streaming.stream.return_value = RawExecResult(
            returncode=0, stdout=b"", stderr=b""
        )
        caps = RuntimeCapabilities()
        parser = _MockParser()
        mgr = _container_mgr(transport, parser, caps, streaming=streaming)
        config = RunConfig(image="alpine", stream_output=True, tty=False, detach=True)
        result = mgr.run(config)
        assert result == ""

    def test_stream_output_with_output_stream_writes_chunks(self, transport):
        output_stream = BytesIO()
        streaming = MagicMock(spec=StreamingTransport)

        def _stream(
            cmd,
            *,
            on_stdout=None,
            on_stderr=None,
            timeout=None,
            input_data=None,
            cancel_token=None,
        ):
            if on_stdout:
                on_stdout(b"chunk1 ")
            if on_stdout:
                on_stdout(b"chunk2")
            return RawExecResult(returncode=0, stdout=b"chunk1 chunk2", stderr=b"")

        streaming.stream.side_effect = _stream
        caps = RuntimeCapabilities()
        parser = _MockParser()
        mgr = _container_mgr(
            transport, parser, caps, streaming=streaming, output_stream=output_stream
        )
        config = RunConfig(image="alpine", stream_output=True, tty=False, detach=True)
        result = mgr.run(config)
        assert result == "chunk1 chunk2"
        assert output_stream.getvalue() == b"chunk1 chunk2"

    def test_stream_output_with_none_output_stream_does_not_crash(self, transport):
        streaming = MagicMock(spec=StreamingTransport)
        streaming.stream.return_value = RawExecResult(
            returncode=0, stdout=b"ignored", stderr=b""
        )
        caps = RuntimeCapabilities()
        parser = _MockParser()
        mgr = _container_mgr(
            transport, parser, caps, streaming=streaming, output_stream=None
        )
        config = RunConfig(image="alpine", stream_output=True, tty=False, detach=True)
        result = mgr.run(config)
        assert result == "ignored"

    def test_stream_output_false_returns_stdout(self, transport):
        streaming = MagicMock(spec=StreamingTransport)
        streaming.stream.return_value = RawExecResult(
            returncode=0, stdout=b"abc123", stderr=b""
        )
        caps = RuntimeCapabilities()
        parser = _MockParser()
        mgr = _container_mgr(transport, parser, caps, streaming=streaming)
        config = RunConfig(image="alpine", stream_output=False, tty=False, detach=True)
        result = mgr.run(config)
        assert result == "abc123"


class TestTtyEdgeCases:
    def test_execute_pty_failure_propagates(self, manager, transport):
        manager._pty_transport.execute_pty = MagicMock(
            side_effect=ContainerRuntimeError("PTY failed", command=["docker"])
        )
        config = RunConfig(image="alpine", command=["bash"], tty=True, detach=False)
        with pytest.raises(ContainerRuntimeError, match="PTY failed"):
            manager.run(config)

    def test_effective_tty_with_default_flags(self, manager, transport):
        caps = RuntimeCapabilities(default_run_flags=("--userns=keep-id",))
        parser = _MockParser()
        streaming = MagicMock(spec=StreamingTransport)
        streaming.stream.return_value = RawExecResult(
            returncode=0, stdout=b"abc123", stderr=b""
        )
        m = _container_mgr(
            transport,
            parser,
            caps,
            streaming=streaming,
            output_stream=BytesIO(),
        )
        m._pty_transport.execute_pty = MagicMock(
            return_value=RawExecResult(returncode=0, stdout=b"", stderr=b"")
        )
        config = RunConfig(image="alpine", command=["bash"], tty=True, detach=False)
        m.run(config)
        m._pty_transport.execute_pty.assert_called_once()
        args, kwargs = m._pty_transport.execute_pty.call_args
        assert kwargs["output_stream"] is not None
        assert kwargs["timeout"] is None
