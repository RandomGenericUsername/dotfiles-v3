from unittest.mock import patch, MagicMock

import pytest

from oci_runtime.adapters.transport.cli import CliTransport
from oci_runtime.domain.exceptions import RuntimeNotAvailableError
from oci_runtime.domain.types import RawExecResult


class TestCliTransport:
    def test_stores_binary(self):
        t = CliTransport("docker")
        assert t.binary == "docker"

    def test_execute_returns_bytes(self):
        t = CliTransport("docker")
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch("subprocess.Popen") as mock_popen:
                proc = MagicMock()
                proc.stdout.fileno.return_value = 3
                proc.stderr.fileno.return_value = 4
                proc.wait.return_value = 0
                mock_popen.return_value = proc
                with patch("oci_runtime.adapters.transport.cli.ProcessPipeReader") as mock_reader:
                    mock_reader.from_process.return_value.read.return_value = ([b"binary\x00data"], [b""])
                    result = t.execute(["docker", "build", "-"])
        assert isinstance(result.stdout, bytes)
        assert isinstance(result.stderr, bytes)
        assert result.stdout == b"binary\x00data"

    def test_execute_passes_input_data(self):
        t = CliTransport("docker")
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch("subprocess.Popen") as mock_popen:
                proc = MagicMock()
                proc.stdout.fileno.return_value = 3
                proc.stderr.fileno.return_value = 4
                proc.wait.return_value = 0
                mock_popen.return_value = proc
                with patch("oci_runtime.adapters.transport.cli.ProcessPipeReader") as mock_reader:
                    mock_reader.from_process.return_value.read.return_value = ([b""], [b""])
                    t.execute(["docker", "build", "-"], input_data=b"tar content")
        mock_popen.assert_called_once()

    def test_execute_handles_binary_input_and_output(self):
        t = CliTransport("docker")
        binary_input = b"\x00\x01\x02\x03binary data"
        binary_output = b"output\x00with\x00nulls"
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch("subprocess.Popen") as mock_popen:
                proc = MagicMock()
                proc.stdout.fileno.return_value = 3
                proc.stderr.fileno.return_value = 4
                proc.wait.return_value = 0
                mock_popen.return_value = proc
                with patch("oci_runtime.adapters.transport.cli.ProcessPipeReader") as mock_reader:
                    mock_reader.from_process.return_value.read.return_value = ([binary_output], [b""])
                    result = t.execute(["docker", "build", "-"], input_data=binary_input)
        assert result.stdout == binary_output
        assert result.returncode == 0

    def test_execute_raises_runtime_not_available_when_binary_missing(self):
        t = CliTransport("nonexistent-runtime")
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeNotAvailableError, match="nonexistent-runtime"):
                t.execute(["nonexistent-runtime", "--version"])

    def test_probe_returns_true_when_binary_available(self):
        t = CliTransport("docker")
        with patch("shutil.which", return_value="/usr/bin/docker"):
            assert t.probe() is True

    def test_probe_returns_false_when_binary_not_found(self):
        t = CliTransport("nonexistent")
        with patch("shutil.which", return_value=None):
            assert t.probe() is False

    def test_transport_caches_which(self):
        with patch("shutil.which", side_effect=["/usr/bin/docker", "/usr/bin/docker", "/usr/bin/docker"]) as mock_which:
            with patch("subprocess.Popen") as mock_popen:
                proc = MagicMock()
                proc.stdout.fileno.return_value = 3
                proc.stderr.fileno.return_value = 4
                proc.wait.return_value = 0
                mock_popen.return_value = proc
                with patch("oci_runtime.adapters.transport.cli.ProcessPipeReader") as mock_reader:
                    mock_reader.from_process.return_value.read.return_value = ([], [])
                    from oci_runtime.adapters.transport.cli import CliTransport
                    t = CliTransport("docker")
                    t.get_runtime_binary()
                    t.execute(["docker", "ps"])
                    t.execute(["docker", "ps"])
                    assert mock_which.call_count == 1
