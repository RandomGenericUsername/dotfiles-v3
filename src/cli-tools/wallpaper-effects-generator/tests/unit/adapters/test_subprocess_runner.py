from __future__ import annotations

import subprocess
from unittest.mock import ANY, patch

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
                env=ANY,
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
                env=ANY,
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

    def test_execute_applies_image_magick_memory_limit(self) -> None:
        """Every invocation is bounded by the default 256 MiB pixel-cache cap."""
        mock_result = subprocess.CompletedProcess(
            args=["magick", "-version"], returncode=0, stdout="", stderr=""
        )
        with (
            patch("shutil.which", return_value="/usr/bin/magick"),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            SubprocessCommandRunner(binary="magick").execute("magick -version")
            env = mock_run.call_args.kwargs["env"]
            assert env is not None
            assert env["MAGICK_MEMORY_LIMIT"] == "256MiB"

    def test_execute_honours_custom_memory_limit(self) -> None:
        mock_result = subprocess.CompletedProcess(
            args=["magick", "-version"], returncode=0, stdout="", stderr=""
        )
        with (
            patch("shutil.which", return_value="/usr/bin/magick"),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            SubprocessCommandRunner(binary="magick", memory_limit="512MiB").execute(
                "magick -version"
            )
            env = mock_run.call_args.kwargs["env"]
            assert env is not None
            assert env["MAGICK_MEMORY_LIMIT"] == "512MiB"

    def test_execute_memory_limit_none_inherits_parent_env(self) -> None:
        """Opting out leaves the subprocess environment untouched (env=None)."""
        mock_result = subprocess.CompletedProcess(
            args=["magick", "-version"], returncode=0, stdout="", stderr=""
        )
        with (
            patch("shutil.which", return_value="/usr/bin/magick"),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            SubprocessCommandRunner(binary="magick", memory_limit=None).execute("magick -version")
            assert mock_run.call_args.kwargs["env"] is None

    def test_execute_applies_temporary_path(self) -> None:
        """The pixel cache spills to the configured disk-backed temp dir."""
        mock_result = subprocess.CompletedProcess(
            args=["magick", "-version"], returncode=0, stdout="", stderr=""
        )
        with (
            patch("shutil.which", return_value="/usr/bin/magick"),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            SubprocessCommandRunner(binary="magick", temporary_path="/var/cache/weg-tmp").execute(
                "magick -version"
            )
            env = mock_run.call_args.kwargs["env"]
            assert env is not None
            assert env["MAGICK_TEMPORARY_PATH"] == "/var/cache/weg-tmp"
            assert env["MAGICK_MEMORY_LIMIT"] == "256MiB"

    def test_execute_temporary_path_without_memory_limit(self) -> None:
        mock_result = subprocess.CompletedProcess(
            args=["magick", "-version"], returncode=0, stdout="", stderr=""
        )
        with (
            patch("shutil.which", return_value="/usr/bin/magick"),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            SubprocessCommandRunner(
                binary="magick", memory_limit=None, temporary_path="/var/cache/weg-tmp"
            ).execute("magick -version")
            env = mock_run.call_args.kwargs["env"]
            assert env is not None
            assert env["MAGICK_TEMPORARY_PATH"] == "/var/cache/weg-tmp"
            assert "MAGICK_MEMORY_LIMIT" not in env
