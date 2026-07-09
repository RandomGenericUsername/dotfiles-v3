from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from wallpaper_effects_generator.adapters.subprocess_runner import (
    SubprocessCommandRunner,
)
from wallpaper_effects_generator.domain.exceptions import (
    BinaryNotFoundError,
    CommandExecutionError,
)


class TestSubprocessCommandRunner:
    def test_init_detects_binary(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/magick"):
            runner = SubprocessCommandRunner(binary="magick")
            assert runner.get_binary() == "magick"

    def test_init_raises_when_binary_missing(self) -> None:
        with patch("shutil.which", return_value=None):
            with pytest.raises(BinaryNotFoundError):
                SubprocessCommandRunner(binary="nonexistent_binary_xyz")

    def test_is_available_true(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/magick"):
            runner = SubprocessCommandRunner(binary="magick")
            assert runner.is_available()

    def test_is_available_false(self) -> None:
        with (
            patch("shutil.which", side_effect=lambda x: "/usr/bin/cp" if x == "cp" else None),
        ):
            runner = SubprocessCommandRunner(binary="cp")
            assert not runner.is_available("nonexistent_binary_xyz")

    def test_get_binary(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/magick"):
            runner = SubprocessCommandRunner(binary="magick")
            assert runner.get_binary() == "magick"

    def test_execute_success(self) -> None:
        mock_result = subprocess.CompletedProcess(
            args=["echo", "hello"],
            returncode=0,
            stdout="hello\n",
            stderr="",
        )
        with (
            patch("shutil.which", return_value="/usr/bin/magick"),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            runner = SubprocessCommandRunner(binary="magick")
            result = runner.execute("echo hello")
            assert result.return_code == 0
            assert result.stdout == "hello\n"
            assert result.stderr == ""
            mock_run.assert_called_once_with(
                ["echo", "hello"],
                capture_output=True,
                text=True,
                timeout=None,
            )

    def test_execute_with_timeout(self) -> None:
        mock_result = subprocess.CompletedProcess(
            args=["sleep", "1"],
            returncode=0,
            stdout="",
            stderr="",
        )
        with (
            patch("shutil.which", return_value="/usr/bin/magick"),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            runner = SubprocessCommandRunner(binary="magick")
            runner.execute("sleep 1", timeout=30)
            mock_run.assert_called_once_with(
                ["sleep", "1"],
                capture_output=True,
                text=True,
                timeout=30,
            )

    def test_execute_failure(self) -> None:
        mock_result = subprocess.CompletedProcess(
            args=["false"],
            returncode=1,
            stdout="",
            stderr="error msg",
        )
        with (
            patch("shutil.which", return_value="/usr/bin/magick"),
            patch("subprocess.run", return_value=mock_result),
        ):
            runner = SubprocessCommandRunner(binary="magick")
            result = runner.execute("false")
            assert result.return_code == 1
            assert result.stderr == "error msg"

    def test_execute_timeout_expired(self) -> None:
        with (
            patch("shutil.which", return_value="/usr/bin/magick"),
            patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired(
                    cmd="sleep 10", timeout=1, output="", stderr="timeout"
                ),
            ),
        ):
            runner = SubprocessCommandRunner(binary="magick")
            with pytest.raises(CommandExecutionError):
                runner.execute("sleep 10", timeout=1)
