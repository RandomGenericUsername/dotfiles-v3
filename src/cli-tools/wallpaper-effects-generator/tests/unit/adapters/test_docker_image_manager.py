from __future__ import annotations

from unittest.mock import Mock

import pytest

from wallpaper_effects_generator.adapters.docker_image_manager import (
    DockerImageManager,
)
from wallpaper_effects_generator.domain.exceptions import (
    CommandExecutionError,
    ContainerImageNotFoundError,
)
from wallpaper_effects_generator.domain.models import CommandResult


@pytest.fixture
def mock_runner() -> Mock:
    runner = Mock()
    runner.is_available.return_value = True
    runner.get_binary.return_value = "docker"
    return runner


class TestDockerImageManager:
    def test_pull_success(self, mock_runner: Mock) -> None:
        mock_runner.execute.return_value = CommandResult(
            stdout="",
            stderr="",
            return_code=0,
            duration=1.0,
        )
        mgr = DockerImageManager(command_runner=mock_runner)
        mgr.pull("nginx:latest")
        mock_runner.execute.assert_called_once()
        args = mock_runner.execute.call_args[0]
        assert "docker pull" in args[0]

    def test_pull_failure(self, mock_runner: Mock) -> None:
        mock_runner.execute.return_value = CommandResult(
            stdout="",
            stderr="pull access denied",
            return_code=1,
            duration=0.5,
        )
        mgr = DockerImageManager(command_runner=mock_runner)
        with pytest.raises(CommandExecutionError):
            mgr.pull("private/image:latest")

    def test_exists_true(self, mock_runner: Mock) -> None:
        mock_runner.execute.return_value = CommandResult(
            stdout="",
            stderr="",
            return_code=0,
            duration=0.1,
        )
        mgr = DockerImageManager(command_runner=mock_runner)
        assert mgr.exists("nginx:latest") is True

    def test_exists_false(self, mock_runner: Mock) -> None:
        mock_runner.execute.return_value = CommandResult(
            stdout="",
            stderr="No such image",
            return_code=1,
            duration=0.1,
        )
        mgr = DockerImageManager(command_runner=mock_runner)
        assert mgr.exists("nonexistent:latest") is False

    def test_remove_success(self, mock_runner: Mock) -> None:
        mock_runner.execute.return_value = CommandResult(
            stdout="Untagged: nginx:latest\n",
            stderr="",
            return_code=0,
            duration=0.5,
        )
        mgr = DockerImageManager(command_runner=mock_runner)
        mgr.remove("nginx:latest")
        mock_runner.execute.assert_called_once()

    def test_remove_image_not_found(self, mock_runner: Mock) -> None:
        mock_runner.execute.return_value = CommandResult(
            stdout="",
            stderr="No such image: nginx:latest",
            return_code=1,
            duration=0.1,
        )
        mgr = DockerImageManager(command_runner=mock_runner)
        with pytest.raises(ContainerImageNotFoundError):
            mgr.remove("nginx:latest")

    def test_remove_generic_error(self, mock_runner: Mock) -> None:
        mock_runner.execute.return_value = CommandResult(
            stdout="",
            stderr="permission denied",
            return_code=1,
            duration=0.1,
        )
        mgr = DockerImageManager(command_runner=mock_runner)
        with pytest.raises(CommandExecutionError):
            mgr.remove("nginx:latest")

    def test_list_images(self, mock_runner: Mock) -> None:
        mock_runner.execute.return_value = CommandResult(
            stdout="nginx:latest\npython:3.12\n",
            stderr="",
            return_code=0,
            duration=0.3,
        )
        mgr = DockerImageManager(command_runner=mock_runner)
        images = mgr.list()
        assert images == ["nginx:latest", "python:3.12"]

    def test_get_default_registry(self, mock_runner: Mock) -> None:
        mgr = DockerImageManager(command_runner=mock_runner)
        assert mgr.get_default_registry() == "docker.io"
