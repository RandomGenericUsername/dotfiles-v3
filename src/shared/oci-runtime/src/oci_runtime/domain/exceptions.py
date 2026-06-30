class OciError(Exception):
    def __init__(
        self,
        message: str,
        command: list[str] | None = None,
        exit_code: int | None = None,
        stderr: str | None = None,
    ):
        self.message = message
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        parts = [self.message]
        if self.command:
            parts.append(f"Command: {' '.join(self.command)}")
        if self.exit_code is not None:
            parts.append(f"Exit code: {self.exit_code}")
        if self.stderr:
            parts.append(f"Error output: {self.stderr}")
        return "\n".join(parts)


class ParsingError(OciError):
    """Raised when CLI output cannot be parsed."""

    def __init__(self, raw: str, message: str = "Failed to parse output"):
        self.raw = raw
        super().__init__(message)


class ContainerError(OciError):
    pass


class ImageError(OciError):
    pass


class VolumeError(OciError):
    pass


class NetworkError(OciError):
    pass


class ImageNotFoundError(ImageError):
    def __init__(self, image_name: str):
        self.image_name = image_name
        super().__init__(f"Image not found: {image_name}")


class ImagePullAccessDeniedError(ImageError):
    def __init__(
        self,
        image_name: str,
        registry: str = "",
        command=None,
        exit_code=None,
        stderr=None,
    ):
        self.image_name = image_name
        self.registry = registry
        msg = f"Pull access denied for image: {image_name}"
        if registry:
            msg += f" (registry: {registry})"
        super().__init__(msg, command=command, exit_code=exit_code, stderr=stderr)


class ContainerNotFoundError(ContainerError):
    def __init__(self, container_id: str):
        self.container_id = container_id
        super().__init__(f"Container not found: {container_id}")


class VolumeNotFoundError(VolumeError):
    def __init__(self, volume_name: str):
        self.volume_name = volume_name
        super().__init__(f"Volume not found: {volume_name}")


class NetworkNotFoundError(NetworkError):
    def __init__(self, network_name: str):
        self.network_name = network_name
        super().__init__(f"Network not found: {network_name}")


class OperationTimeoutError(OciError):
    def __init__(
        self, command: list[str], timeout: float, message: str = "Operation timed out"
    ):
        self.command = command
        self.timeout = timeout
        super().__init__(message, command=command)


class ImageRuntimeError(ImageError):
    pass


class VolumeRuntimeError(VolumeError):
    pass


class NetworkRuntimeError(NetworkError):
    pass


class ContainerRuntimeError(ContainerError):
    pass


class RuntimeNotAvailableError(OciError):
    def __init__(self, runtime: str):
        self.runtime = runtime
        super().__init__(
            f"Container runtime '{runtime}' is not available. "
            f"Please ensure it is installed and running."
        )
