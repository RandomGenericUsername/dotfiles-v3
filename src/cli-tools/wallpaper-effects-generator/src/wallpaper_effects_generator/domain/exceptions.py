from pathlib import Path


class WallpaperEffectsError(Exception):
    pass


class EffectsLoadError(WallpaperEffectsError):
    def __init__(self, file_path: Path, reason: str) -> None:
        self.file_path = file_path
        self.reason = reason
        super().__init__(f"Failed to load effects from {file_path}: {reason}")


class EffectsValidationError(WallpaperEffectsError):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class CommandExecutionError(WallpaperEffectsError):
    def __init__(self, command: str, return_code: int, stderr: str) -> None:
        self.command = command
        self.return_code = return_code
        self.stderr = stderr
        super().__init__(f"Command '{command}' failed with code {return_code}: {stderr}")


class CatalogError(WallpaperEffectsError):
    pass


class EffectNotFoundError(CatalogError):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Effect not found: {name}")


class CompositeNotFoundError(CatalogError):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Composite not found: {name}")


class PresetNotFoundError(CatalogError):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Preset not found: {name}")


class BinaryNotFoundError(WallpaperEffectsError):
    def __init__(self, binary: str) -> None:
        self.binary = binary
        super().__init__(f"Binary not found: {binary}")


class ContainerImageNotFoundError(WallpaperEffectsError):
    def __init__(self, image: str) -> None:
        self.image = image
        super().__init__(f"Container image not found: {image}")


class ContainerRuntimeUnavailableError(WallpaperEffectsError):
    def __init__(self, runtime: str) -> None:
        self.runtime = runtime
        super().__init__(f"Container runtime unavailable: {runtime}")


class ContainerTimeoutError(WallpaperEffectsError):
    def __init__(self, command: str, timeout: int) -> None:
        self.command = command
        self.timeout = timeout
        super().__init__(f"Container command timed out after {timeout}s: {command}")


class ImagePullAccessError(WallpaperEffectsError):
    def __init__(self, image: str, registry: str) -> None:
        self.image = image
        self.registry = registry
        super().__init__(f"Access denied pulling image {image} from {registry}")


class ConfigResolutionError(WallpaperEffectsError):
    pass


class NoInputFilesError(WallpaperEffectsError):
    def __init__(self, input_path: str) -> None:
        self.input_path = input_path
        super().__init__(f"No input files found at: {input_path}")


class BatchProcessingError(WallpaperEffectsError):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


__all__ = [
    "WallpaperEffectsError",
    "EffectsLoadError",
    "EffectsValidationError",
    "CommandExecutionError",
    "CatalogError",
    "EffectNotFoundError",
    "CompositeNotFoundError",
    "PresetNotFoundError",
    "BinaryNotFoundError",
    "ContainerImageNotFoundError",
    "ContainerRuntimeUnavailableError",
    "ContainerTimeoutError",
    "ImagePullAccessError",
    "ConfigResolutionError",
    "NoInputFilesError",
    "BatchProcessingError",
]
