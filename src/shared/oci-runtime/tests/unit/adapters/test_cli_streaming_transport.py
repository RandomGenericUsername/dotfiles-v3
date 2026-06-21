import subprocess
import threading
from unittest.mock import patch, MagicMock

import pytest

from oci_runtime.adapters._process_reader import ProcessPipeReader
from oci_runtime.adapters.transport.streaming import CliStreamingTransport
from oci_runtime.domain.exceptions import RuntimeNotAvailableError


class _MockSelectorKey:
    def __init__(self, fileobj):
        self.fileobj = fileobj


class _MockSelector:
    def __init__(self):
        self._registered = {}
        self.select_calls: list = []
        self.select_on_empty_count = 0

    def register(self, fileobj, events):
        self._registered[id(fileobj)] = fileobj

    def unregister(self, fileobj):
        self._registered.pop(id(fileobj), None)

    def get_map(self):
        return dict(self._registered)

    def select(self, timeout=None):
        self.select_calls.append(timeout)
        if not self._registered:
            self.select_on_empty_count += 1
            return []
        return [(_MockSelectorKey(fobj), 1) for fobj in self._registered.values()]

    def close(self):
        pass


class TestCliStreamingTransport:
    def test_stores_binary(self):
        s = CliStreamingTransport("docker")
        assert s.binary == "docker"

    def test_stream_normal_execution(self):
        s = CliStreamingTransport("docker")

        mock_stdout = MagicMock()
        mock_stdout.read.side_effect = [b"line1\n", b"line2\n", b""]
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        process = MagicMock()
        process.stdout = mock_stdout
        process.stderr = mock_stderr
        process.wait = MagicMock(return_value=0)

        selector = _MockSelector()

        with (patch("shutil.which", return_value="/usr/bin/docker"),
              patch("subprocess.Popen", return_value=process),
              patch("selectors.DefaultSelector", return_value=selector)):
            result = s.stream(["docker", "ps"])

        assert result.returncode == 0
        assert result.stdout == b"line1\nline2\n"
        assert result.stderr == b""

    def test_stream_raises_runtime_not_available(self):
        s = CliStreamingTransport("nonexistent-runtime")
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeNotAvailableError, match="nonexistent-runtime"):
                s.stream(["nonexistent-runtime", "ps"])

    def test_stream_on_stdout_callback(self):
        s = CliStreamingTransport("docker")

        mock_stdout = MagicMock()
        mock_stdout.read.side_effect = [b"chunk1\n", b"chunk2\n", b""]
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        process = MagicMock()
        process.stdout = mock_stdout
        process.stderr = mock_stderr
        process.wait = MagicMock(return_value=0)

        selector = _MockSelector()
        received_stdout = []
        received_stderr = []

        def on_stdout(data):
            received_stdout.append(data)

        def on_stderr(data):
            received_stderr.append(data)

        with (patch("shutil.which", return_value="/usr/bin/docker"),
              patch("subprocess.Popen", return_value=process),
              patch("selectors.DefaultSelector", return_value=selector)):
            result = s.stream(["docker", "ps"], on_stdout=on_stdout, on_stderr=on_stderr)

        assert result.returncode == 0
        assert len(received_stdout) >= 1
        all_output = b"".join(received_stdout)
        assert b"chunk1" in all_output

    def test_stream_no_spin_on_empty_selector_map(self):
        s = CliStreamingTransport("docker")

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b""
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        process = MagicMock()
        process.stdout = mock_stdout
        process.stderr = mock_stderr
        process.wait = MagicMock(return_value=0)

        selector = _MockSelector()

        with (patch("shutil.which", return_value="/usr/bin/docker"),
              patch("subprocess.Popen", return_value=process),
              patch("selectors.DefaultSelector", return_value=selector)):
            s.stream(["docker", "ps"])

        assert selector.select_on_empty_count == 0

    def test_stream_stdin_in_daemon_thread(self):
        s = CliStreamingTransport("docker")

        mock_stdout = MagicMock()
        mock_stdout.read.side_effect = [b"output\n", b""]
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        process = MagicMock()
        process.stdout = mock_stdout
        process.stderr = mock_stderr
        process.wait = MagicMock(return_value=0)

        original_thread = threading.Thread
        daemon_thread_kwargs = []

        def tracking_thread(*args, **kwargs):
            if kwargs.get("daemon"):
                daemon_thread_kwargs.append(kwargs)
            return original_thread(*args, **kwargs)

        selector = _MockSelector()

        with (patch("shutil.which", return_value="/usr/bin/docker"),
              patch("subprocess.Popen", return_value=process),
              patch("selectors.DefaultSelector", return_value=selector),
              patch("threading.Thread", side_effect=tracking_thread)):
            s.stream(["docker", "build", "-"], input_data=b"tar data")

        assert len(daemon_thread_kwargs) >= 1
        assert daemon_thread_kwargs[0].get("daemon") is True

    def test_stream_large_input_no_deadlock(self):
        s = CliStreamingTransport("docker")

        mock_stdout = MagicMock()
        mock_stdout.read.side_effect = [b"build progress\n", b""]
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        process = MagicMock()
        process.stdout = mock_stdout
        process.stderr = mock_stderr
        process.wait = MagicMock(return_value=0)

        large_input = b"x" * 70000

        selector = _MockSelector()

        with (patch("shutil.which", return_value="/usr/bin/docker"),
              patch("subprocess.Popen", return_value=process),
              patch("selectors.DefaultSelector", return_value=selector)):
            result = s.stream(["docker", "build", "-"], input_data=large_input)

        assert result.returncode == 0
        assert b"build progress" in result.stdout

    def test_stream_read_exception_no_zombie(self):
        s = CliStreamingTransport("docker")

        mock_stdout = MagicMock()
        mock_stdout.read.side_effect = ValueError("read stream error")
        mock_stderr = MagicMock()

        process = MagicMock()
        process.stdout = mock_stdout
        process.stderr = mock_stderr
        process.wait = MagicMock(return_value=0)

        selector = _MockSelector()

        with (patch("shutil.which", return_value="/usr/bin/docker"),
              patch("subprocess.Popen", return_value=process),
              patch("selectors.DefaultSelector", return_value=selector)):
            with pytest.raises(ValueError):
                s.stream(["docker", "ps"])

        assert process.wait.called

    def test_stream_timeout_expired_kills_process(self):
        s = CliStreamingTransport("docker")

        mock_stdout = MagicMock()
        mock_stdout.read.side_effect = [b"output\n", b""]
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        process = MagicMock()
        process.poll.return_value = None
        process.stdout = mock_stdout
        process.stderr = mock_stderr
        process.wait = MagicMock(
            side_effect=[subprocess.TimeoutExpired("cmd", 10), 0],
        )
        process.kill = MagicMock()

        selector = _MockSelector()

        with (patch("shutil.which", return_value="/usr/bin/docker"),
              patch("subprocess.Popen", return_value=process),
              patch("selectors.DefaultSelector", return_value=selector)):
            with pytest.raises(subprocess.TimeoutExpired):
                s.stream(["docker", "ps"], timeout=10)

        process.kill.assert_called_once()

    def test_stream_selectors_cleaned_up(self):
        s = CliStreamingTransport("docker")

        mock_stdout = MagicMock()
        mock_stdout.read.side_effect = ValueError("read stream error")
        mock_stderr = MagicMock()

        process = MagicMock()
        process.stdout = mock_stdout
        process.stderr = mock_stderr
        process.wait = MagicMock(return_value=0)

        selector = _MockSelector()

        with (patch("shutil.which", return_value="/usr/bin/docker"),
              patch("subprocess.Popen", return_value=process),
              patch("selectors.DefaultSelector", return_value=selector)):
            with pytest.raises(ValueError):
                s.stream(["docker", "ps"])

        mock_stdout.close.assert_called_once()
        mock_stderr.close.assert_called_once()

    def test_stream_cancellation_returns_partial(self):
        """When cancelled, stream returns partial data with returncode=-1."""
        from oci_runtime.adapters._cancellation import ThreadCancellationToken
        s = CliStreamingTransport("docker")

        mock_stdout = MagicMock()
        mock_stdout.read.side_effect = [b"partial\n", b""]
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        process = MagicMock()
        process.stdout = mock_stdout
        process.stderr = mock_stderr
        process.kill = MagicMock()
        process.wait = MagicMock(return_value=0)

        selector = _MockSelector()
        token = ThreadCancellationToken()
        token.cancel()

        with (patch("shutil.which", return_value="/usr/bin/docker"),
              patch("subprocess.Popen", return_value=process),
              patch("selectors.DefaultSelector", return_value=selector)):
            result = s.stream(["docker", "ps"], cancel_token=token)

        assert result.returncode == -1
        process.kill.assert_called_once()


class TestProcessPipeReader:
    """Direct tests for the ProcessPipeReader helper."""

    def test_read_normal_case(self):
        mock_stdout = MagicMock()
        mock_stdout.read.side_effect = [b"line1\n", b"line2\n", b""]
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        process = MagicMock()
        process.stdout = mock_stdout
        process.stderr = mock_stderr

        selector = _MockSelector()

        with patch("selectors.DefaultSelector", return_value=selector):
            reader = ProcessPipeReader(process)
            stdout_acc, stderr_acc = reader.read()

        assert b"".join(stdout_acc) == b"line1\nline2\n"
        assert b"".join(stderr_acc) == b""

    def test_read_with_on_stdout_callback(self):
        mock_stdout = MagicMock()
        mock_stdout.read.side_effect = [b"chunk1\n", b"chunk2\n", b""]
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        process = MagicMock()
        process.stdout = mock_stdout
        process.stderr = mock_stderr

        selector = _MockSelector()
        received = []

        with patch("selectors.DefaultSelector", return_value=selector):
            reader = ProcessPipeReader(process)
            stdout_acc, stderr_acc = reader.read(on_stdout=lambda d: received.append(d))

        assert b"chunk1" in b"".join(received)

    def test_read_with_on_stderr_callback(self):
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b""
        mock_stderr = MagicMock()
        mock_stderr.read.side_effect = [b"err1\n", b""]

        process = MagicMock()
        process.stdout = mock_stdout
        process.stderr = mock_stderr

        selector = _MockSelector()
        received_err = []

        with patch("selectors.DefaultSelector", return_value=selector):
            reader = ProcessPipeReader(process)
            stdout_acc, stderr_acc = reader.read(on_stderr=lambda d: received_err.append(d))

        assert b"err1" in b"".join(received_err)