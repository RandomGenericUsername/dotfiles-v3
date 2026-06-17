import io
import sys
from unittest.mock import MagicMock, patch

import pytest
import subprocess

from oci_runtime.domain.exceptions import ContainerRuntimeError, RuntimeNotAvailableError


class TestRunPty:
    def test_empty_command_raises(self):
        from oci_runtime.adapters.managers.pty import run_pty
        with pytest.raises(ContainerRuntimeError, match="Empty command"):
            run_pty([])

    def test_missing_binary_raises(self):
        from oci_runtime.adapters.managers.pty import run_pty
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeNotAvailableError, match="nonexistent"):
                run_pty(["nonexistent", "arg"])

    def test_basic_execution_returns_completed_process(self):
        from oci_runtime.adapters.managers.pty import run_pty
        with patch("shutil.which", return_value="/usr/bin/true"):
            with patch("pty.openpty", return_value=(3, 4)):
                with patch("os.close"):
                    with patch("os.read", return_value=b""):
                        with patch("subprocess.Popen") as mock_popen:
                            proc = MagicMock()
                            proc.poll.return_value = 0
                            proc.returncode = 0
                            mock_popen.return_value = proc
                            with patch("select.select", return_value=([], [], [])):
                                result = run_pty(["/usr/bin/true"])
        assert isinstance(result, subprocess.CompletedProcess)
        assert result.returncode == 0

    def test_non_zero_exit_returns_completed_process(self):
        from oci_runtime.adapters.managers.pty import run_pty
        with patch("shutil.which", return_value="/usr/bin/false"):
            with patch("pty.openpty", return_value=(3, 4)):
                with patch("os.close"):
                    with patch("os.read", return_value=b""):
                        with patch("subprocess.Popen") as mock_popen:
                            proc = MagicMock()
                            proc.poll.return_value = 1
                            proc.returncode = 1
                            mock_popen.return_value = proc
                            with patch("select.select", return_value=([], [], [])):
                                result = run_pty(["/usr/bin/false"])
        assert isinstance(result, subprocess.CompletedProcess)
        assert result.returncode == 1


class TestRunPtyEdgeCases:
    def test_output_streamed_to_bytesio(self):
        from oci_runtime.adapters.managers.pty import run_pty
        buf = io.BytesIO()
        with patch("shutil.which", return_value="/usr/bin/echo"):
            with patch("pty.openpty", return_value=(3, 4)):
                with patch("os.read", side_effect=[b"hello", b""]):
                    with patch("os.close"):
                        with patch("subprocess.Popen") as mock_popen:
                            proc = MagicMock()
                            proc.poll.side_effect = [None, 0]
                            proc.returncode = 0
                            mock_popen.return_value = proc
                            with patch("select.select", return_value=([3], [], [])):
                                result = run_pty(["/usr/bin/echo", "hello"], output_stream=buf)
        assert buf.getvalue() == b"hello"
        assert result.stdout == b"hello"
        assert result.returncode == 0

    def test_run_pty_custom_output_stream(self):
        from oci_runtime.adapters.managers.pty import run_pty
        buf = io.BytesIO()
        with patch("shutil.which", return_value="/usr/bin/echo"):
            with patch("pty.openpty", return_value=(3, 4)):
                with patch("os.read", side_effect=[b"output data", b""]):
                    with patch("os.close"):
                        with patch("subprocess.Popen") as mock_popen:
                            proc = MagicMock()
                            proc.poll.side_effect = [None, 0]
                            proc.returncode = 0
                            mock_popen.return_value = proc
                            with patch("select.select", return_value=([3], [], [])):
                                result = run_pty(["/usr/bin/echo", "test"], output_stream=buf)
        assert buf.getvalue() == b"output data"
        assert result.stdout == b"output data"
        assert result.returncode == 0

    def test_run_pty_default_writes_to_stdout(self):
        from oci_runtime.adapters.managers.pty import run_pty
        with patch("shutil.which", return_value="/usr/bin/echo"):
            with patch("pty.openpty", return_value=(3, 4)):
                with patch("os.read", side_effect=[b"hello default", b""]):
                    with patch("os.close"):
                        with patch("subprocess.Popen") as mock_popen:
                            proc = MagicMock()
                            proc.poll.side_effect = [None, 0]
                            proc.returncode = 0
                            mock_popen.return_value = proc
                            with patch("select.select", return_value=([3], [], [])):
                                with patch.object(sys.stdout.buffer, "write") as mock_write:
                                    with patch.object(sys.stdout.buffer, "flush") as mock_flush:
                                        result = run_pty(["/usr/bin/echo", "hello"])
        mock_write.assert_called_once_with(b"hello default")
        mock_flush.assert_called_once()
        assert result.returncode == 0

    def test_drain_after_exit(self):
        from oci_runtime.adapters.managers.pty import run_pty
        with patch("shutil.which", return_value="/usr/bin/echo"):
            with patch("pty.openpty", return_value=(3, 4)):
                with patch("os.read", return_value=b""):
                    with patch("os.close"):
                        with patch("subprocess.Popen") as mock_popen:
                            proc = MagicMock()
                            proc.poll.side_effect = [None, 0]
                            proc.returncode = 0
                            mock_popen.return_value = proc
                            with patch("select.select", return_value=([], [], [])):
                                result = run_pty(["/usr/bin/echo"])
        assert result.returncode == 0

    def test_non_utf8_output_handled(self):
        from oci_runtime.adapters.managers.pty import run_pty
        with patch("shutil.which", return_value="/usr/bin/echo"):
            with patch("pty.openpty", return_value=(3, 4)):
                with patch("os.read", side_effect=[b"valid\xff\xfe", b""]):
                    with patch("os.close"):
                        with patch("subprocess.Popen") as mock_popen:
                            proc = MagicMock()
                            proc.poll.side_effect = [None, 0]
                            proc.returncode = 0
                            mock_popen.return_value = proc
                            with patch("select.select", return_value=([3], [], [])):
                                result = run_pty(["/usr/bin/echo", "test"])
        assert result.returncode == 0

    def test_large_output(self):
        from oci_runtime.adapters.managers.pty import run_pty
        big_data = b"x" * 10000
        with patch("shutil.which", return_value="/usr/bin/echo"):
            with patch("pty.openpty", return_value=(3, 4)):
                with patch("os.read", side_effect=[big_data, b""]):
                    with patch("os.close"):
                        with patch("subprocess.Popen") as mock_popen:
                            proc = MagicMock()
                            proc.poll.side_effect = [None, 0]
                            proc.returncode = 0
                            mock_popen.return_value = proc
                            with patch("select.select", return_value=([3], [], [])):
                                result = run_pty(["/usr/bin/echo", "x"])
        assert result.returncode == 0

    def test_select_raises_value_error(self):
        from oci_runtime.adapters.managers.pty import run_pty
        with patch("shutil.which", return_value="/usr/bin/true"):
            with patch("pty.openpty", return_value=(3, 4)):
                with patch("os.close"):
                    with patch("subprocess.Popen") as mock_popen:
                        proc = MagicMock()
                        proc.returncode = 0
                        proc.poll.return_value = 0
                        mock_popen.return_value = proc
                        with patch("select.select", side_effect=ValueError("bad fd")):
                            result = run_pty(["/usr/bin/true"])
        assert result.returncode == 0

    def test_proc_never_started_raises(self):
        from oci_runtime.adapters.managers.pty import run_pty
        with patch("shutil.which", return_value="/usr/bin/true"):
            with patch("pty.openpty", return_value=(3, 4)):
                with patch("os.close"):
                    with patch("subprocess.Popen") as mock_popen:
                        mock_popen.side_effect = OSError("fork failed")
                        with pytest.raises(ContainerRuntimeError):
                            run_pty(["/usr/bin/true"])
