from unittest.mock import patch, MagicMock

import pytest

from oci_runtime.adapters.transport.cli import CliTransport
from oci_runtime.domain.exceptions import RuntimeNotAvailableError
from oci_runtime.domain.types import RawExecResult


class TestCliTransportExecute:
    def test_execute_calls_subprocess_run(self):
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout=b"running", stderr=b"")
                t = CliTransport("docker")
                result = t.execute(["docker", "ps"])
                mock_run.assert_called_once_with(
                    ["docker", "ps"],
                    capture_output=True,
                    timeout=None,
                    input=None,
                )
                assert isinstance(result, RawExecResult)
                assert result.returncode == 0
                assert result.stdout == b"running"

    def test_execute_passes_input_data(self):
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout=b"built", stderr=b"")
                t = CliTransport("docker")
                t.execute(["docker", "build", "-"], input_data=b"FROM alpine")
                mock_run.assert_called_once_with(
                    ["docker", "build", "-"],
                    capture_output=True,
                    timeout=None,
                    input=b"FROM alpine",
                )

    def test_execute_passes_timeout(self):
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
                t = CliTransport("docker")
                t.execute(["docker", "pull", "alpine"], timeout=300)
                mock_run.assert_called_once_with(
                    ["docker", "pull", "alpine"],
                    capture_output=True,
                    timeout=300,
                    input=None,
                )

    def test_execute_propagates_file_not_found(self):
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = FileNotFoundError()
                t = CliTransport("docker")
                with pytest.raises(RuntimeNotAvailableError):
                    t.execute(["docker", "ps"])

    def test_execute_raises_on_missing_binary(self):
        with patch("shutil.which", return_value=None):
            t = CliTransport("nonexistent")
            with pytest.raises(RuntimeNotAvailableError, match="nonexistent"):
                t.execute(["nonexistent", "ps"])

    def test_get_runtime_binary_returns_binary(self):
        with patch("shutil.which", return_value="/usr/bin/docker"):
            t = CliTransport("docker")
            assert t.get_runtime_binary() == "docker"

    def test_get_runtime_binary_custom_path(self):
        with patch("shutil.which", return_value="/custom/bin/podman"):
            t = CliTransport("/custom/bin/podman")
            assert t.get_runtime_binary() == "/custom/bin/podman"

    def test_get_runtime_binary_raises_on_missing(self):
        with patch("shutil.which", return_value=None):
            t = CliTransport("missing")
            with pytest.raises(RuntimeNotAvailableError):
                t.get_runtime_binary()
