import subprocess
import threading
from unittest.mock import MagicMock, patch, MagicMock

import pytest

from oci_runtime.ports.pipe_reader import ProcessPipeReader
from oci_runtime.adapters.transport.streaming import CliStreamingTransport
from oci_runtime.domain.exceptions import (
    OperationTimeoutError,
    RuntimeNotAvailableError,
)


class _MockSelectorKey:
    def __init__(self, fileobj, fd=None):
        self.fileobj = fileobj
        self.fd = fd if fd is not None else id(fileobj)


class _MockSelector:
    def __init__(self):
        self._registered: dict[int, tuple] = {}
        self.select_calls: list = []
        self.select_on_empty_count = 0

    def register(self, fileobj, events):
        self._registered[fileobj] = (fileobj, fileobj)

    def unregister(self, fileobj):
        self._registered.pop(fileobj, None)

    def get_map(self):
        return dict(self._registered)

    def select(self, timeout=None):
        self.select_calls.append(timeout)
        if not self._registered:
            self.select_on_empty_count += 1
            return []
        return [
            (_MockSelectorKey(fobj, fd=fd), 1) for fd, fobj in self._registered.values()
        ]

    def close(self):
        pass


class TestCliStreamingTransport:
    def test_stores_binary(self):
        s = CliStreamingTransport("docker", binary_resolver=MagicMock())
        assert s.binary == "docker"

    def test_stream_normal_execution(self):
        s = CliStreamingTransport("docker", binary_resolver=MagicMock())

        process = MagicMock()
        process.wait.return_value = 0

        with (
            patch("shutil.which", return_value="/usr/bin/docker"),
            patch("subprocess.Popen", return_value=process),
            patch(
                "oci_runtime.adapters.transport.streaming.ProcessPipeReader"
            ) as mock_reader,
        ):
            mock_reader.from_process.return_value.read.return_value = (
                [b"line1\n", b"line2\n"],
                [b""],
            )
            result = s.stream(["docker", "ps"])

        assert result.returncode == 0
        assert result.stdout == b"line1\nline2\n"
        assert result.stderr == b""

    def test_stream_raises_runtime_not_available(self):
        from oci_runtime.adapters.binary import CliBinaryResolver
        s = CliStreamingTransport("nonexistent-runtime", binary_resolver=CliBinaryResolver())
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeNotAvailableError, match="nonexistent-runtime"):
                s.stream(["nonexistent-runtime", "ps"])

    def test_stream_on_stdout_callback(self):
        s = CliStreamingTransport("docker", binary_resolver=MagicMock())

        process = MagicMock()
        process.wait.return_value = 0

        selector = _MockSelector()
        received_stdout = []
        received_stderr = []

        def on_stdout(data):
            received_stdout.append(data)

        def on_stderr(data):
            received_stderr.append(data)

        with (
            patch("shutil.which", return_value="/usr/bin/docker"),
            patch("subprocess.Popen", return_value=process),
            patch(
                "oci_runtime.adapters.transport.streaming.ProcessPipeReader"
            ) as mock_reader,
        ):

            def _mock_read(on_stdout=None, on_stderr=None, cancel_token=None):
                if on_stdout:
                    on_stdout(b"chunk1\n")
                return ([b"chunk1\n"], [b""])

            mock_reader.from_process.return_value.read.side_effect = _mock_read
            result = s.stream(
                ["docker", "ps"], on_stdout=on_stdout, on_stderr=on_stderr
            )

        assert result.returncode == 0
        assert len(received_stdout) >= 1
        all_output = b"".join(received_stdout)
        assert b"chunk1" in all_output

    def test_stream_no_spin_on_empty_selector_map(self):
        s = CliStreamingTransport("docker", binary_resolver=MagicMock())

        process = MagicMock()
        process.wait.return_value = 0

        with (
            patch("shutil.which", return_value="/usr/bin/docker"),
            patch("subprocess.Popen", return_value=process),
            patch(
                "oci_runtime.adapters.transport.streaming.ProcessPipeReader"
            ) as mock_reader,
        ):
            mock_reader.from_process.return_value.read.return_value = ([b""], [b""])
            s.stream(["docker", "ps"])

    def test_stream_stdin_in_daemon_thread(self):
        s = CliStreamingTransport("docker", binary_resolver=MagicMock())

        process = MagicMock()
        process.wait.return_value = 0

        original_thread = threading.Thread
        daemon_thread_kwargs = []

        def tracking_thread(*args, **kwargs):
            if kwargs.get("daemon"):
                daemon_thread_kwargs.append(kwargs)
            return original_thread(*args, **kwargs)

        with (
            patch("shutil.which", return_value="/usr/bin/docker"),
            patch("subprocess.Popen", return_value=process),
            patch(
                "oci_runtime.adapters.transport.streaming.ProcessPipeReader"
            ) as mock_reader,
            patch("threading.Thread", side_effect=tracking_thread),
        ):
            mock_reader.from_process.return_value.read.return_value = (
                [b"output\n"],
                [b""],
            )
            s.stream(["docker", "build", "-"], input_data=b"tar data")

        assert len(daemon_thread_kwargs) >= 1
        assert daemon_thread_kwargs[0].get("daemon") is True

    def test_stream_large_input_no_deadlock(self):
        s = CliStreamingTransport("docker", binary_resolver=MagicMock())

        process = MagicMock()
        process.wait.return_value = 0

        large_input = b"x" * 70000

        with (
            patch("shutil.which", return_value="/usr/bin/docker"),
            patch("subprocess.Popen", return_value=process),
            patch(
                "oci_runtime.adapters.transport.streaming.ProcessPipeReader"
            ) as mock_reader,
        ):
            mock_reader.from_process.return_value.read.return_value = (
                [b"build progress\n"],
                [b""],
            )
            result = s.stream(["docker", "build", "-"], input_data=large_input)

        assert result.returncode == 0
        assert b"build progress" in result.stdout

    def test_stream_read_exception_no_zombie(self):
        s = CliStreamingTransport("docker", binary_resolver=MagicMock())

        process = MagicMock()
        process.wait.return_value = 0

        with (
            patch("shutil.which", return_value="/usr/bin/docker"),
            patch("subprocess.Popen", return_value=process),
            patch(
                "oci_runtime.adapters.transport.streaming.ProcessPipeReader"
            ) as mock_reader,
        ):
            mock_reader.from_process.return_value.read.side_effect = ValueError(
                "read stream error"
            )
            with pytest.raises(ValueError):
                s.stream(["docker", "ps"])

        assert process.wait.called

    def test_stream_timeout_expired_kills_process(self):
        s = CliStreamingTransport("docker", binary_resolver=MagicMock())

        process = MagicMock()
        process.kill = MagicMock()

        with (
            patch("shutil.which", return_value="/usr/bin/docker"),
            patch("subprocess.Popen", return_value=process),
            patch(
                "oci_runtime.adapters.transport.streaming.ProcessPipeReader"
            ) as mock_reader,
            patch(
                "oci_runtime.adapters.transport.streaming.DeadlineCancellationToken"
            ) as mock_dc,
        ):
            mock_reader.from_process.return_value.read.return_value = (
                [b"output\n"],
                [b""],
            )
            mock_dc.return_value.is_cancelled = True
            with pytest.raises(OperationTimeoutError):
                s.stream(["docker", "ps"], timeout=10)

        process.kill.assert_called_once()

    def test_stream_exception_propagates(self):
        s = CliStreamingTransport("docker", binary_resolver=MagicMock())

        process = MagicMock()
        process.wait.return_value = 0

        with (
            patch("shutil.which", return_value="/usr/bin/docker"),
            patch("subprocess.Popen", return_value=process),
            patch(
                "oci_runtime.adapters.transport.streaming.ProcessPipeReader"
            ) as mock_reader,
        ):
            mock_reader.from_process.return_value.read.side_effect = ValueError(
                "read stream error"
            )
            with pytest.raises(ValueError):
                s.stream(["docker", "ps"])

    def test_stream_cancellation_returns_partial(self):
        """When cancelled, stream returns partial data with returncode=-1."""
        from oci_runtime.ports.cancellation import ThreadCancellationToken

        s = CliStreamingTransport("docker", binary_resolver=MagicMock())

        process = MagicMock()
        process.kill = MagicMock()

        token = ThreadCancellationToken()
        token.cancel()

        with (
            patch("shutil.which", return_value="/usr/bin/docker"),
            patch("subprocess.Popen", return_value=process),
            patch(
                "oci_runtime.adapters.transport.streaming.ProcessPipeReader"
            ) as mock_reader,
        ):
            mock_reader.from_process.return_value.read.return_value = (
                [b"partial\n"],
                [b""],
            )
            result = s.stream(["docker", "ps"], cancel_token=token)

        assert result.returncode == -1
        process.kill.assert_called_once()

    def test_stream_deadline_token_timeout_cancellation(self):
        import selectors

        with (
            patch("shutil.which", return_value="/usr/bin/docker"),
            patch("subprocess.Popen") as mock_popen,
            patch("selectors.DefaultSelector") as mock_sel_cls,
        ):
            mock_proc = MagicMock()
            mock_proc.stdout = MagicMock()
            mock_proc.stdout.fileno.return_value = 5
            mock_proc.stderr = MagicMock()
            mock_proc.stderr.fileno.return_value = 6
            mock_proc.poll.return_value = None
            mock_popen.return_value = mock_proc
            mock_key_stdout = MagicMock()
            mock_key_stdout.fileobj = mock_proc.stdout
            mock_sel = MagicMock()
            mock_sel_cls.return_value = mock_sel
            mock_sel.get_map.return_value = {5: mock_key_stdout, 6: MagicMock()}
            mock_sel.select.return_value = []
            from oci_runtime.adapters.transport.streaming import CliStreamingTransport

            s = CliStreamingTransport("docker", binary_resolver=MagicMock())
            with pytest.raises(OperationTimeoutError):
                s.stream(["docker", "ps"], timeout=0.3)
            assert mock_proc.kill.called


class TestProcessPipeReader:
    """Direct tests for the ProcessPipeReader helper."""

    def test_read_normal_case(self):
        mock_stdout_data = [b"line1\n", b"line2\n", b""]
        mock_stderr_data = [b""]

        def _os_read(fd, n):
            if fd == 3 and mock_stdout_data:
                return mock_stdout_data.pop(0)
            if fd == 4 and mock_stderr_data:
                return mock_stderr_data.pop(0)
            return b""

        process = MagicMock()
        process.stdout.fileno.return_value = 3
        process.stderr.fileno.return_value = 4

        selector = _MockSelector()

        with patch("selectors.DefaultSelector", return_value=selector):
            with patch("os.read", side_effect=_os_read):
                reader = ProcessPipeReader.from_process(process)
                stdout_acc, stderr_acc = reader.read()

        assert b"".join(stdout_acc) == b"line1\nline2\n"
        assert b"".join(stderr_acc) == b""

    def test_read_with_on_stdout_callback(self):
        process = MagicMock()
        process.stdout.fileno.return_value = 3
        process.stderr.fileno.return_value = 4

        selector = _MockSelector()
        received = []
        stdout_data = [b"chunk1\n", b"chunk2\n", b""]
        stderr_data = [b""]

        def _os_read(fd, n):
            if fd == 3 and stdout_data:
                return stdout_data.pop(0)
            if fd == 4 and stderr_data:
                return stderr_data.pop(0)
            return b""

        with patch("selectors.DefaultSelector", return_value=selector):
            with patch("os.read", side_effect=_os_read):
                reader = ProcessPipeReader.from_process(process)
                stdout_acc, stderr_acc = reader.read(
                    on_stdout=lambda d: received.append(d)
                )

        assert b"chunk1" in b"".join(received)

    def test_read_with_on_stderr_callback(self):
        process = MagicMock()
        process.stdout.fileno.return_value = 3
        process.stderr.fileno.return_value = 4

        selector = _MockSelector()
        received_err = []
        stdout_data = [b""]
        stderr_data = [b"err1\n", b""]

        def _os_read(fd, n):
            if fd == 3 and stdout_data:
                return stdout_data.pop(0)
            if fd == 4 and stderr_data:
                return stderr_data.pop(0)
            return b""

        with patch("selectors.DefaultSelector", return_value=selector):
            with patch("os.read", side_effect=_os_read):
                reader = ProcessPipeReader.from_process(process)
                stdout_acc, stderr_acc = reader.read(
                    on_stderr=lambda d: received_err.append(d)
                )

        assert b"err1" in b"".join(received_err)
