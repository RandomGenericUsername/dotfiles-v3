from dataclasses import dataclass

from oci_runtime.ports.transport import ExecResult, Transport


@dataclass
class RecordedCall:
    command: list[str]
    kwargs: dict


class RecordingTransport(Transport):
    def __init__(self, binary: str = "docker", responses: dict[str, ExecResult] | None = None,
                 stream_responses: dict[str, list[bytes]] | None = None):
        self._binary = binary
        self._responses = responses or {}
        self._stream_responses = stream_responses or {}
        self.calls: list[RecordedCall] = []
        self._probe_result: bool = True

    def execute(self, command, *, timeout=None, input_data=None, stream=False, on_output=None):
        self.calls.append(RecordedCall(command, {
            "timeout": timeout, "input_data": input_data, "stream": stream,
        }))
        key = " ".join(command)
        if stream and on_output and key in self._stream_responses:
            for chunk in self._stream_responses[key]:
                on_output(chunk, "stdout")
            return ExecResult(returncode=0, stdout=b"", stderr=b"")
        if key in self._responses:
            return self._responses[key]
        return ExecResult(returncode=0, stdout=b"", stderr=b"")

    def probe(self) -> bool:
        return self._probe_result

    def get_runtime_binary(self) -> str:
        return self._binary

    def execute_pty(self, command, on_output=None):
        import subprocess
        return subprocess.CompletedProcess(args=command, returncode=0)


class FailingTransport(Transport):
    def __init__(self, binary: str = "docker", stderr: str = "not found"):
        self._binary = binary
        self._stderr = stderr
        self.calls: list[RecordedCall] = []

    def execute(self, command, *, timeout=None, input_data=None, stream=False, on_output=None):
        self.calls.append(RecordedCall(command, {"timeout": timeout, "input_data": input_data, "stream": stream}))
        return ExecResult(returncode=1, stdout=b"", stderr=self._stderr.encode())

    def probe(self) -> bool:
        return True

    def get_runtime_binary(self) -> str:
        return self._binary

    def execute_pty(self, command, on_output=None):
        import subprocess
        return subprocess.CompletedProcess(args=command, returncode=1)
