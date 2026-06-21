import subprocess
from unittest.mock import patch, MagicMock

import pytest

from oci_runtime.adapters.transport.cli import CliTransport
from oci_runtime.domain.exceptions import RuntimeNotAvailableError
from oci_runtime.domain.types import RawExecResult


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
        assert isinstance(result, RawExecResult)
        assert result.returncode == 0
        assert result.stdout == b"ok\n"
        assert result.stderr == b""

    def test_execute_returns_bytes(self):
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