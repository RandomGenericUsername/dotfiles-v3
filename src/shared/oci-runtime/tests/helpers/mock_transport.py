from dataclasses import dataclass

from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.streaming import StreamingTransport
from oci_runtime.ports.transport import Transport
from oci_runtime.ports.tty import TtyDetector


@dataclass
class RecordedCall:
    command: list[str]
    kwargs: dict


class RecordingTransport(Transport):
    """Mock transport that records calls and returns canned responses.

    Note: ``self.calls`` is a plain ``list``, not a thread-safe data
    structure.  For concurrent test scenarios, wrap access to
    ``self.calls`` with a ``threading.Lock`` or use a ``queue.Queue``.
    """

    def __init__(
        self,
        binary: str = "docker",
        responses: dict[tuple[str, ...], RawExecResult] | None = None,
    ):
        self._binary = binary
        self._responses = responses or {}
        self.calls: list[RecordedCall] = []
        self._probe_result: bool = True

    def execute(self, command, *, timeout=None, input_data=None):
        self.calls.append(
            RecordedCall(
                command,
                {
                    "timeout": timeout,
                    "input_data": input_data,
                },
            )
        )
        key = tuple(command)
        if key in self._responses:
            return self._responses[key]
        return RawExecResult(returncode=0, stdout=b"", stderr=b"")

    def probe(self) -> bool:
        return self._probe_result

    def get_runtime_binary(self) -> str:
        return self._binary


class RecordingStreamingTransport(StreamingTransport):
    def __init__(
        self,
        binary: str = "docker",
        responses: dict[tuple[str, ...], RawExecResult] | None = None,
        stream_responses: dict[tuple[str, ...], list[bytes]] | None = None,
    ):
        self._binary = binary
        self._responses = responses or {}
        self._stream_responses = stream_responses or {}
        self.calls: list[RecordedCall] = []

    def stream(
        self,
        command,
        *,
        timeout=None,
        input_data=None,
        on_stdout=None,
        on_stderr=None,
        cancel_token=None,
    ):
        self.calls.append(
            RecordedCall(
                command,
                {
                    "timeout": timeout,
                    "input_data": input_data,
                },
            )
        )
        key = tuple(command)
        if on_stdout and key in self._stream_responses:
            for chunk in self._stream_responses[key]:
                on_stdout(chunk)
            return RawExecResult(returncode=0, stdout=b"", stderr=b"")
        if key in self._responses:
            return self._responses[key]
        return RawExecResult(returncode=0, stdout=b"", stderr=b"")


class MockPtyTransport:
    """Minimal mock that satisfies the PtyTransport interface."""

    def execute_pty(
        self, command, *, output_stream=None, timeout=None, cancel_token=None
    ):
        return RawExecResult(returncode=0, stdout=b"", stderr=b"")


class FakeTtyDetector(TtyDetector):
    def __init__(self, is_tty: bool = False):
        self._is_tty = is_tty

    def is_tty(self) -> bool:
        return self._is_tty


class MockResultChecker:
    """Minimal no-op mock that satisfies ResultChecker interface."""

    def check(
        self,
        result,
        cmd,
        *,
        operation="execute",
        entity="",
        not_found_error=None,
    ):
        pass


class MockListExecutor:
    """Minimal mock that satisfies ListExecutor interface."""

    def __init__(self, return_value=None):
        self._return_value = return_value or []

    def execute_list(
        self,
        subcommand,
        entity_type,
        *,
        show_all=False,
        filters=None,
    ):
        return self._return_value
