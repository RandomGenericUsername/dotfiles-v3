from __future__ import annotations

from wallpaper_effects_generator.domain.exceptions import (
    CommandExecutionError,
    ContainerImageNotFoundError,
)
from wallpaper_effects_generator.domain.services import CommandSanitizer
from wallpaper_effects_generator.ports.command_runner import CommandRunnerPort
from wallpaper_effects_generator.ports.image_manager import ImageManagerPort


class DockerImageManager(ImageManagerPort):
    def __init__(
        self,
        command_runner: CommandRunnerPort,
        sanitizer: CommandSanitizer | None = None,
    ) -> None:
        self._runner = command_runner
        self._sanitizer = sanitizer or CommandSanitizer()

    def pull(self, image: str) -> None:
        cmd = f"{self._runner.get_binary()} pull {self._sanitizer.quote(image)}"
        result = self._runner.execute(cmd, timeout=300)
        if result.return_code != 0:
            raise CommandExecutionError(cmd, result.return_code, result.stderr)

    def exists(self, image: str) -> bool:
        cmd = f"{self._runner.get_binary()} image inspect {self._sanitizer.quote(image)}"
        result = self._runner.execute(cmd)
        return result.return_code == 0

    def remove(self, image: str) -> None:
        cmd = f"{self._runner.get_binary()} rmi {self._sanitizer.quote(image)}"
        result = self._runner.execute(cmd)
        if result.return_code != 0:
            if "No such image" in result.stderr or "not found" in result.stderr:
                raise ContainerImageNotFoundError(image)
            raise CommandExecutionError(cmd, result.return_code, result.stderr)

    def list(self) -> list[str]:
        fmt = self._sanitizer.quote("{{.Repository}}:{{.Tag}}")
        cmd = f"{self._runner.get_binary()} images --format {fmt}"
        result = self._runner.execute(cmd)
        if result.return_code != 0:
            raise CommandExecutionError(cmd, result.return_code, result.stderr)
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def get_default_registry(self) -> str:
        return "docker.io"
