import subprocess
from unittest.mock import MagicMock, patch

import pytest

from oci_runtime.adapters.transport.cli import CliTransport
from oci_runtime.domain.exceptions import RuntimeNotAvailableError
from oci_runtime.domain.types import RawExecResult


class TestCliTransportExecute:
    def test_execute_calls_subprocess_popen(self):
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch("subprocess.Popen") as mock_popen:
                proc = MagicMock()
                proc.wait.return_value = 0
                mock_popen.return_value = proc
                with patch(
                    "oci_runtime.adapters.transport.cli.ProcessPipeReader"
                ) as mock_reader:
                    mock_reader.from_process.return_value.read.return_value = (
                        [b"running"],
                        [b""],
                    )
                    t = CliTransport("docker", binary_resolver=MagicMock())
                    result = t.execute(["docker", "ps"])
                    mock_popen.assert_called_once_with(
                        ["docker", "ps"],
                        stdin=None,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    assert isinstance(result, RawExecResult)
                    assert result.returncode == 0
                    assert result.stdout == b"running"

    def test_execute_passes_input_data(self):
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch("subprocess.Popen") as mock_popen:
                proc = MagicMock()
                proc.wait.return_value = 0
                mock_popen.return_value = proc
                with patch(
                    "oci_runtime.adapters.transport.cli.ProcessPipeReader"
                ) as mock_reader:
                    mock_reader.from_process.return_value.read.return_value = (
                        [b"built"],
                        [b""],
                    )
                    t = CliTransport("docker", binary_resolver=MagicMock())
                    t.execute(["docker", "build", "-"], input_data=b"FROM alpine")
                    mock_popen.assert_called_once_with(
                        ["docker", "build", "-"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )

    def test_execute_passes_timeout(self):
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch("subprocess.Popen") as mock_popen:
                proc = MagicMock()
                proc.wait.return_value = 0
                mock_popen.return_value = proc
                with patch(
                    "oci_runtime.adapters.transport.cli.ProcessPipeReader"
                ) as mock_reader:
                    mock_reader.from_process.return_value.read.return_value = (
                        [b""],
                        [b""],
                    )
                    t = CliTransport("docker", binary_resolver=MagicMock())
                    t.execute(["docker", "pull", "alpine"], timeout=300)
                    mock_popen.assert_called_once_with(
                        ["docker", "pull", "alpine"],
                        stdin=None,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )

    def test_execute_propagates_file_not_found(self):
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch("subprocess.Popen") as mock_popen:
                mock_popen.side_effect = FileNotFoundError()
                t = CliTransport("docker", binary_resolver=MagicMock())
                with pytest.raises(FileNotFoundError):
                    t.execute(["docker", "ps"])

    def test_execute_raises_on_missing_binary(self):
        from oci_runtime.adapters.binary import CliBinaryResolver
        with patch("shutil.which", return_value=None):
            t = CliTransport("nonexistent", binary_resolver=CliBinaryResolver())
            with pytest.raises(RuntimeNotAvailableError, match="nonexistent"):
                t.execute(["nonexistent", "ps"])

    def test_get_runtime_binary_returns_binary(self):
        from oci_runtime.adapters.binary import CliBinaryResolver
        with patch("shutil.which", return_value="/usr/bin/docker"):
            t = CliTransport("docker", binary_resolver=CliBinaryResolver())
            assert t.get_runtime_binary() == "/usr/bin/docker"

    def test_get_runtime_binary_custom_path(self):
        from oci_runtime.adapters.binary import CliBinaryResolver
        with patch("shutil.which", return_value="/custom/bin/podman"):
            t = CliTransport("/custom/bin/podman", binary_resolver=CliBinaryResolver())
            assert t.get_runtime_binary() == "/custom/bin/podman"

    def test_get_runtime_binary_raises_on_missing(self):
        from oci_runtime.adapters.binary import CliBinaryResolver
        with patch("shutil.which", return_value=None):
            t = CliTransport("missing", binary_resolver=CliBinaryResolver())
            with pytest.raises(RuntimeNotAvailableError):
                t.get_runtime_binary()
