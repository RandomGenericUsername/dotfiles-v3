import io
from unittest.mock import MagicMock, patch

import pytest

from oci_runtime.adapters.binary import CliBinaryResolver
from oci_runtime.adapters.transport.pty import CliPtyTransport
from oci_runtime.domain.exceptions import (
    OciError,
    OperationTimeoutError,
    RuntimeNotAvailableError,
)
from oci_runtime.domain.types import RawExecResult


class TestRunPty:
    def test_empty_command_raises(self):
        resolver = CliBinaryResolver()
        transport = CliPtyTransport(resolver)
        with pytest.raises(OciError) as exc:
            transport.execute_pty([], output_stream=MagicMock())
        assert "Empty" in str(exc.value)

    def test_missing_binary_raises(self):
        resolver = CliBinaryResolver()
        transport = CliPtyTransport(resolver)
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeNotAvailableError, match="nonexistent"):
                transport.execute_pty(["nonexistent", "arg"], output_stream=MagicMock())

    def test_basic_execution_returns_raw_exec_result(self):
        resolver = CliBinaryResolver()
        transport = CliPtyTransport(resolver)
        with patch("shutil.which", return_value="/usr/bin/true"):
            with patch("pty.openpty", return_value=(3, 4)):
                with patch("os.close"):
                    with patch("subprocess.Popen") as mock_popen:
                        proc = MagicMock()
                        proc.wait.return_value = 0
                        mock_popen.return_value = proc
                        with patch(
                            "oci_runtime.adapters.transport.pty._AsyncStreamReader"
                        ) as mock_reader:
                            mock_reader.return_value.read.return_value = (
                                [b""],
                                [b""],
                            )
                            result = transport.execute_pty(
                                ["/usr/bin/true"], output_stream=MagicMock()
                            )
        assert isinstance(result, RawExecResult)
        assert result.returncode == 0

    def test_run_pty_timeout_raises(self):
        resolver = CliBinaryResolver()
        transport = CliPtyTransport(resolver)
        with (
            patch("pty.openpty") as mock_openpty,
            patch("subprocess.Popen") as mock_popen,
            patch("os.close"),
            patch(
                "oci_runtime.adapters.transport.pty._AsyncStreamReader"
            ) as mock_reader,
            patch(
                "oci_runtime.adapters.transport.pty.DeadlineCancellationToken"
            ) as mock_dc,
        ):
            mock_openpty.return_value = (3, 4)
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc
            mock_reader.return_value.read.return_value = ([b""], [b""])
            mock_dc.return_value.is_cancelled = True
            with pytest.raises(OperationTimeoutError):
                transport.execute_pty(
                    ["/bin/sleep", "5"], timeout=0.3, output_stream=MagicMock()
                )
            mock_proc.kill.assert_called_once()

    def test_non_zero_exit_returns_raw_exec_result(self):
        resolver = CliBinaryResolver()
        transport = CliPtyTransport(resolver)
        with patch("shutil.which", return_value="/usr/bin/false"):
            with patch("pty.openpty", return_value=(3, 4)):
                with patch("os.close"):
                    with patch("subprocess.Popen") as mock_popen:
                        proc = MagicMock()
                        proc.wait.return_value = 1
                        mock_popen.return_value = proc
                        with patch(
                            "oci_runtime.adapters.transport.pty._AsyncStreamReader"
                        ) as mock_reader:
                            mock_reader.return_value.read.return_value = (
                                [b""],
                                [b""],
                            )
                            result = transport.execute_pty(
                                ["/usr/bin/false"], output_stream=MagicMock()
                            )
        assert isinstance(result, RawExecResult)
        assert result.returncode == 1


class TestRunPtyEdgeCases:
    def test_output_streamed_to_bytesio(self):
        resolver = CliBinaryResolver()
        transport = CliPtyTransport(resolver)
        buf = io.BytesIO()
        with patch("shutil.which", return_value="/usr/bin/echo"):
            with patch("pty.openpty", return_value=(3, 4)):
                with patch("os.close"):
                    with patch("subprocess.Popen") as mock_popen:
                        proc = MagicMock()
                        proc.wait.return_value = 0
                        mock_popen.return_value = proc
                        with patch(
                            "oci_runtime.adapters.transport.pty._AsyncStreamReader"
                        ) as mock_reader:

                            def _mock_read(
                                on_stdout=None,
                                on_stderr=None,
                                cancel_ctx=None,
                                timeout=None,
                            ):
                                if on_stdout:
                                    on_stdout(b"hello")
                                return ([b"hello"], [b""])

                            mock_reader.return_value.read.side_effect = _mock_read
                            result = transport.execute_pty(
                                ["/usr/bin/echo", "hello"], output_stream=buf
                            )
        assert buf.getvalue() == b"hello"
        assert result.stdout == b"hello"
        assert result.returncode == 0

    def test_run_pty_custom_output_stream(self):
        resolver = CliBinaryResolver()
        transport = CliPtyTransport(resolver)
        buf = io.BytesIO()
        with patch("shutil.which", return_value="/usr/bin/echo"):
            with patch("pty.openpty", return_value=(3, 4)):
                with patch("os.close"):
                    with patch("subprocess.Popen") as mock_popen:
                        proc = MagicMock()
                        proc.wait.return_value = 0
                        mock_popen.return_value = proc
                        with patch(
                            "oci_runtime.adapters.transport.pty._AsyncStreamReader"
                        ) as mock_reader:

                            def _mock_read(
                                on_stdout=None,
                                on_stderr=None,
                                cancel_ctx=None,
                                timeout=None,
                            ):
                                if on_stdout:
                                    on_stdout(b"output data")
                                return ([b"output data"], [b""])

                            mock_reader.return_value.read.side_effect = _mock_read
                            result = transport.execute_pty(
                                ["/usr/bin/echo", "test"], output_stream=buf
                            )
        assert buf.getvalue() == b"output data"
        assert result.stdout == b"output data"
        assert result.returncode == 0

    def test_run_pty_default_writes_to_output_stream(self):
        resolver = CliBinaryResolver()
        transport = CliPtyTransport(resolver)
        buf = io.BytesIO()
        with patch("shutil.which", return_value="/usr/bin/echo"):
            with patch("pty.openpty", return_value=(3, 4)):
                with patch("os.close"):
                    with patch("subprocess.Popen") as mock_popen:
                        proc = MagicMock()
                        proc.wait.return_value = 0
                        mock_popen.return_value = proc
                        with patch(
                            "oci_runtime.adapters.transport.pty._AsyncStreamReader"
                        ) as mock_reader:

                            def _mock_read(
                                on_stdout=None,
                                on_stderr=None,
                                cancel_ctx=None,
                                timeout=None,
                            ):
                                if on_stdout:
                                    on_stdout(b"hello default")
                                return ([b"hello default"], [b""])

                            mock_reader.return_value.read.side_effect = _mock_read
                            result = transport.execute_pty(
                                ["/usr/bin/echo", "hello"], output_stream=buf
                            )
        assert buf.getvalue() == b"hello default"
        assert result.returncode == 0

    def test_drain_after_exit(self):
        resolver = CliBinaryResolver()
        transport = CliPtyTransport(resolver)
        with patch("shutil.which", return_value="/usr/bin/echo"):
            with patch("pty.openpty", return_value=(3, 4)):
                with patch("os.close"):
                    with patch("subprocess.Popen") as mock_popen:
                        proc = MagicMock()
                        proc.wait.return_value = 0
                        mock_popen.return_value = proc
                        with patch(
                            "oci_runtime.adapters.transport.pty._AsyncStreamReader"
                        ) as mock_reader:
                            mock_reader.return_value.read.return_value = (
                                [b""],
                                [b""],
                            )
                            result = transport.execute_pty(
                                ["/usr/bin/echo"], output_stream=MagicMock()
                            )
        assert result.returncode == 0

    def test_non_utf8_output_handled(self):
        resolver = CliBinaryResolver()
        transport = CliPtyTransport(resolver)
        with patch("shutil.which", return_value="/usr/bin/echo"):
            with patch("pty.openpty", return_value=(3, 4)):
                with patch("os.close"):
                    with patch("subprocess.Popen") as mock_popen:
                        proc = MagicMock()
                        proc.wait.return_value = 0
                        mock_popen.return_value = proc
                        with patch(
                            "oci_runtime.adapters.transport.pty._AsyncStreamReader"
                        ) as mock_reader:
                            mock_reader.return_value.read.return_value = (
                                [b"valid\xff\xfe"],
                                [b""],
                            )
                            result = transport.execute_pty(
                                ["/usr/bin/echo", "test"], output_stream=MagicMock()
                            )
        assert result.returncode == 0

    def test_large_output(self):
        resolver = CliBinaryResolver()
        transport = CliPtyTransport(resolver)
        big_data = b"x" * 10000
        with patch("shutil.which", return_value="/usr/bin/echo"):
            with patch("pty.openpty", return_value=(3, 4)):
                with patch("os.close"):
                    with patch("subprocess.Popen") as mock_popen:
                        proc = MagicMock()
                        proc.wait.return_value = 0
                        mock_popen.return_value = proc
                        with patch(
                            "oci_runtime.adapters.transport.pty._AsyncStreamReader"
                        ) as mock_reader:
                            mock_reader.return_value.read.return_value = (
                                [big_data],
                                [b""],
                            )
                            result = transport.execute_pty(
                                ["/usr/bin/echo", "x"], output_stream=MagicMock()
                            )
        assert result.returncode == 0

    def test_reader_raises_value_error(self):
        resolver = CliBinaryResolver()
        transport = CliPtyTransport(resolver)
        with patch("shutil.which", return_value="/usr/bin/true"):
            with patch("pty.openpty", return_value=(3, 4)):
                with patch("os.close"):
                    with patch("subprocess.Popen") as mock_popen:
                        proc = MagicMock()
                        proc.wait.return_value = 0
                        mock_popen.return_value = proc
                        with patch(
                            "oci_runtime.adapters.transport.pty._AsyncStreamReader"
                        ) as mock_reader:
                            mock_reader.return_value.read.side_effect = ValueError(
                                "bad fd"
                            )
                            with pytest.raises(ValueError):
                                transport.execute_pty(
                                    ["/usr/bin/true"], output_stream=MagicMock()
                                )

    def test_pty_stderr_separation(self):
        resolver = CliBinaryResolver()
        transport = CliPtyTransport(resolver)
        with patch("shutil.which", return_value="/usr/bin/true"):
            with patch("pty.openpty", return_value=(3, 4)):
                with patch("os.close"):
                    with patch("subprocess.Popen") as mock_popen:
                        proc = MagicMock()
                        proc.wait.return_value = 0
                        mock_popen.return_value = proc
                        with patch(
                            "oci_runtime.adapters.transport.pty._AsyncStreamReader"
                        ) as mock_reader:
                            mock_reader.return_value.read.return_value = (
                                [b"stdout data"],
                                [b"stderr data"],
                            )
                            result = transport.execute_pty(
                                ["/usr/bin/true"], output_stream=MagicMock()
                            )
        assert result.stdout == b"stdout data"
        assert result.stderr == b"stderr data"
        assert result.returncode == 0

    def test_pty_raises_typed_error_when_stderr_is_none(self):
        resolver = CliBinaryResolver()
        transport = CliPtyTransport(resolver)
        with patch("shutil.which", return_value="/usr/bin/true"):
            with patch("pty.openpty", return_value=(3, 4)):
                with patch("os.close"):
                    with patch("subprocess.Popen") as mock_popen:
                        proc = MagicMock()
                        proc.stderr = None
                        proc.wait.return_value = 0
                        mock_popen.return_value = proc
                        with pytest.raises(OciError) as exc:
                            transport.execute_pty(
                                ["/usr/bin/true"], output_stream=MagicMock()
                            )
                        assert "stderr=None" in str(exc.value)

    def test_proc_never_started_raises(self):
        resolver = CliBinaryResolver()
        transport = CliPtyTransport(resolver)
        with patch("shutil.which", return_value="/usr/bin/true"):
            with patch("pty.openpty", return_value=(3, 4)):
                with patch("os.close"):
                    with patch("subprocess.Popen") as mock_popen:
                        mock_popen.side_effect = OSError("fork failed")
                        with pytest.raises(OSError):
                            transport.execute_pty(
                                ["/usr/bin/true"], output_stream=MagicMock()
                            )
