import subprocess
import threading
from unittest.mock import patch, MagicMock

import pytest

from oci_runtime.adapters._process_reader import ProcessPipeReader
from oci_runtime.adapters.transport.cli import CliTransport
from oci_runtime.domain.exceptions import RuntimeNotAvailableError
from oci_runtime.domain.types import ExecResult


class _MockSelectorKey:
    """Minimal mock for selectors.SelectorKey — provides .fileobj."""
    def __init__(self, fileobj):
        self.fileobj = fileobj


class _MockSelector:
    """Controlled mock for selectors.DefaultSelector.

    Tracks register/unregister state so get_map() reflects what's
    currently registered. select() returns readable events for
    registered pipes (triggering read() calls) and returns []
    when the map is empty (simulating spin).
    """
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


class TestCliTransport:
    def test_stores_binary(self):
        t = CliTransport("docker")
        assert t.binary == "docker"

    def test_execute_calls_subprocess_run(self):
        t = CliTransport("docker")
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=b"ok\n", stderr=b"")) as mock_run:
                result = t.execute(["docker", "--version"])
        mock_run.assert_called_once_with(
            ["docker", "--version"],
            capture_output=True,
            timeout=None,
            input=None,
        )
        assert isinstance(result, ExecResult)
        assert result.returncode == 0
        assert result.stdout == b"ok\n"
        assert result.stderr == b""

    def test_execute_returns_bytes(self):
        """Regression test: ExecResult should contain bytes, not strings."""
        t = CliTransport("docker")
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=b"binary\x00data", stderr=b"")):
                result = t.execute(["docker", "build", "-"])
        assert isinstance(result.stdout, bytes)
        assert isinstance(result.stderr, bytes)
        assert result.stdout == b"binary\x00data"

    def test_execute_passes_timeout(self):
        t = CliTransport("docker")
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=b"", stderr=b"")) as mock_run:
                t.execute(["docker", "ps"], timeout=30)
        mock_run.assert_called_once_with(
            ["docker", "ps"],
            capture_output=True,
            timeout=30,
            input=None,
        )

    def test_execute_passes_input_data(self):
        t = CliTransport("docker")
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=b"", stderr=b"")) as mock_run:
                t.execute(["docker", "build", "-"], input_data=b"tar content")
        mock_run.assert_called_once_with(
            ["docker", "build", "-"],
            capture_output=True,
            timeout=None,
            input=b"tar content",
        )

    def test_execute_handles_binary_input_and_output(self):
        """Regression test: Transport should handle binary data without decoding."""
        t = CliTransport("docker")
        binary_input = b"\x00\x01\x02\x03binary data"
        binary_output = b"output\x00with\x00nulls"
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=binary_output, stderr=b"")):
                result = t.execute(["docker", "build", "-"], input_data=binary_input)
        assert result.stdout == binary_output
        assert result.returncode == 0

    def test_execute_raises_runtime_not_available_when_binary_missing(self):
        t = CliTransport("nonexistent-runtime")
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeNotAvailableError, match="nonexistent-runtime"):
                t.execute(["nonexistent-runtime", "--version"])

    def test_execute_raises_runtime_not_available_on_subprocess_not_found(self):
        t = CliTransport("docker")
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                with pytest.raises(RuntimeNotAvailableError, match="docker"):
                    t.execute(["docker", "--version"])

    def test_probe_returns_true_when_binary_available(self):
        t = CliTransport("docker")
        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            assert t.probe() is True

    def test_probe_returns_false_when_binary_not_found(self):
        t = CliTransport("nonexistent")
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert t.probe() is False

    def test_probe_returns_false_on_timeout(self):
        t = CliTransport("docker")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="docker --version", timeout=30)):
            assert t.probe() is False

    def test_probe_returns_false_on_os_error(self):
        t = CliTransport("docker")
        with patch("subprocess.run", side_effect=OSError):
            assert t.probe() is False

    # ── Finding #16a: CPU spin when pipes close before process exits ──

    def test_streaming_no_spin_on_empty_selector_map(self):
        """Bug 16a: When pipes close before process exits, don't spin on empty selector.

        Both pipes return EOF (b'') on first read → selector.get_map() becomes
        empty. With the old code the loop spun on select() with an empty map
        (100% CPU). The redesigned loop exits when selector.get_map() is empty,
        so no spin occurs and no process.wait(timeout=0.1) fallback is needed.
        """
        t = CliTransport("docker")

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
            t.execute(["docker", "ps"], stream=True)

        # With the redesigned loop, select() is never called on an empty map.
        # Once both pipes return EOF and are unregistered, the loop exits
        # because selector.get_map() is empty.
        assert selector.select_on_empty_count == 0

    # ── Finding #16b: stdin deadlock with large input ──

    def test_streaming_stdin_in_daemon_thread(self):
        """Bug 16b fix: stdin is written in a daemon thread, not the main thread.

        Verifies threading.Thread is called with daemon=True and the
        stdin write function as target.
        """
        t = CliTransport("docker")

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
            t.execute(["docker", "build", "-"], input_data=b"tar data", stream=True)

        assert len(daemon_thread_kwargs) >= 1
        assert daemon_thread_kwargs[0].get("daemon") is True

    def test_streaming_large_input_no_deadlock(self):
        """Bug 16b: Large input (>64KB) doesn't deadlock the streaming path.

        With the fix, stdin is written in a daemon thread so the main
        thread can enter the read loop concurrently. Without the fix,
        process.stdin.write() blocks on >PIPE_BUF and never returns.
        """
        t = CliTransport("docker")

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
            result = t.execute(["docker", "build", "-"], input_data=large_input,
                               stream=True)

        assert result.returncode == 0
        assert b"build progress" in result.stdout

    # ── Finding #14: _read_stream() extraction + guaranteed reaping ──


class TestProcessPipeReader:
    """Direct tests for the ProcessPipeReader helper.

    ProcessPipeReader owns only the selector lifecycle — reading bytes
    from stdout/stderr and accumulating them. The caller (execute())
    owns acquire/release of the Popen process.
    """
    def test_read_normal_case(self):
        """ProcessPipeReader returns correct accumulated bytes from both pipes."""
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


class TestExecuteStreaming:
    """Integration-level tests for the execute() streaming path.

    These test the full acquire -> operate -> release lifecycle that
    wraps _read_stream(). They verify that the outer try/finally
    always reaps the child process and cleans up pipes.
    """
    def test_normal_execution(self):
        """Full streaming path works end-to-end."""
        t = CliTransport("docker")

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
            result = t.execute(["docker", "ps"], stream=True)

        assert result.returncode == 0
        assert result.stdout == b"line1\nline2\n"
        assert result.stderr == b""

    def test_read_exception_no_zombie(self):
        """Exception in _read_stream() — child is still reaped."""
        t = CliTransport("docker")

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
                t.execute(["docker", "ps"], stream=True)

        # The outer finally must have reaped the child even after the error.
        # In the buggy code, process.wait() was never called -> zombie.
        assert process.wait.called

    def test_timeout_expired_kills_process(self):
        """TimeoutExpired from process.wait() — child is killed and reaped."""
        t = CliTransport("docker")

        mock_stdout = MagicMock()
        mock_stdout.read.side_effect = [b"output\n", b""]
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        # process.wait call order:
        #   1. execute:             wait(timeout=10) → TimeoutExpired
        #   2. except handler:      wait()            → 0 (after kill)
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
                t.execute(["docker", "ps"], stream=True, timeout=10)

        process.kill.assert_called_once()

    def test_stdin_large_input(self):
        """Large input (>64KB) doesn't deadlock the streaming path."""
        t = CliTransport("docker")

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
            result = t.execute(["docker", "build", "-"], input_data=large_input,
                               stream=True)

        assert result.returncode == 0
        assert b"build progress" in result.stdout

    def test_selectors_cleaned_up(self):
        """All pipes closed and selector cleaned up after exception."""
        t = CliTransport("docker")

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
                t.execute(["docker", "ps"], stream=True)

        mock_stdout.close.assert_called_once()
        mock_stderr.close.assert_called_once()


    def test_streaming_on_output_still_works(self):
        """on_output callback fires during streaming."""
        t = CliTransport("docker")

        mock_stdout = MagicMock()
        mock_stdout.read.side_effect = [b"chunk1\n", b"chunk2\n", b""]
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        process = MagicMock()
        process.stdout = mock_stdout
        process.stderr = mock_stderr
        process.wait = MagicMock(return_value=0)

        selector = _MockSelector()
        received = []

        def on_output(data, stream):
            received.append(data)

        with (patch("shutil.which", return_value="/usr/bin/docker"),
              patch("subprocess.Popen", return_value=process),
              patch("selectors.DefaultSelector", return_value=selector)):
            result = t.execute(["docker", "ps"], stream=True, on_output=on_output)

        assert result.returncode == 0
        assert len(received) >= 1
        all_output = b"".join(received)
        assert b"chunk1" in all_output
