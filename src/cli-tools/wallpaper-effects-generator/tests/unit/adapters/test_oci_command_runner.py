from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from wallpaper_effects_generator.adapters.oci_command_runner import OCICommandRunner
from wallpaper_effects_generator.domain.exceptions import (
    BinaryNotFoundError,
    CommandExecutionError,
)


class TestOCICommandRunner:
    def test_init_detects_binary(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/docker"):
            runner = OCICommandRunner(engine="docker")
            assert runner.get_binary() == "docker"

    def test_init_raises_when_binary_missing(self) -> None:
        with patch("shutil.which", return_value=None):
            with pytest.raises(BinaryNotFoundError):
                OCICommandRunner(engine="nonexistent_binary_xyz")

    def test_is_available_true(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/docker"):
            runner = OCICommandRunner(engine="docker")
            assert runner.is_available()

    def test_is_available_false(self) -> None:
        def _which(x: str) -> str | None:
            return "/usr/bin/docker" if x == "docker" else None
        with patch("shutil.which", side_effect=_which):
            runner = OCICommandRunner(engine="docker")
            assert not runner.is_available("nonexistent_binary_xyz")

    def test_execute_success(self) -> None:
        mock_result = subprocess.CompletedProcess(
            args=["docker", "ps"],
            returncode=0,
            stdout="CONTAINER ID   IMAGE\nabc123   nginx\n",
            stderr="",
        )
        with (
            patch("shutil.which", return_value="/usr/bin/docker"),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            runner = OCICommandRunner(engine="docker")
            result = runner.execute("docker ps")
            assert result.return_code == 0
            assert "abc123" in result.stdout
            mock_run.assert_called_once_with(
                ["docker", "ps"],
                capture_output=True,
                text=True,
                timeout=None,
            )

    def test_execute_failure(self) -> None:
        mock_result = subprocess.CompletedProcess(
            args=["docker", "nonexistent"],
            returncode=1,
            stdout="",
            stderr="unknown command",
        )
        with (
            patch("shutil.which", return_value="/usr/bin/docker"),
            patch("subprocess.run", return_value=mock_result),
        ):
            runner = OCICommandRunner(engine="docker")
            result = runner.execute("docker nonexistent")
            assert result.return_code == 1
            assert result.stderr == "unknown command"

    def test_execute_timeout_expired(self) -> None:
        with (
            patch("shutil.which", return_value="/usr/bin/docker"),
            patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired(
                    cmd="docker pull bigimage", timeout=1, output="", stderr="timeout"
                ),
            ),
        ):
            runner = OCICommandRunner(engine="docker")
            with pytest.raises(CommandExecutionError):
                runner.execute("docker pull bigimage", timeout=1)

    def test_detect_binary_docker_first(self) -> None:
        def _which(x: str) -> str | None:
            return "/usr/bin/docker" if x == "docker" else None
        with patch("shutil.which", side_effect=_which):
            runner = OCICommandRunner()
            assert runner.get_binary() == "docker"

    def test_detect_binary_podman_fallback(self) -> None:
        def _which(x: str) -> str | None:
            return "/usr/bin/podman" if x == "podman" else None
        with patch("shutil.which", side_effect=_which):
            runner = OCICommandRunner()
            assert runner.get_binary() == "podman"

    def test_detect_binary_none_found(self) -> None:
        with patch("shutil.which", return_value=None):
            with pytest.raises(BinaryNotFoundError):
                OCICommandRunner()
