from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class ResourceKind(Enum):
    FILE = "file"
    DIRECTORY = "directory"


class PathSource(Enum):
    DEFAULT = "default"
    XDG = "xdg"
    DIRECTORY = "directory"
    ENV_PATH = "env_path"
    CLI_PATH = "cli_path"


class OverrideSource(Enum):
    ENV = "env"
    CLI = "cli"


class ResolutionPolicy:
    def __init__(self, env_prefix: str) -> None:
        self.env_prefix = env_prefix


class OverrideRule:
    def __init__(self, field_path: str, sources: set[OverrideSource]) -> None:
        self.field_path = field_path
        self.sources = sources


class ResolvedPath:
    def __init__(self, path: Path, source: PathSource, kind: ResourceKind = ResourceKind.FILE) -> None:
        self.path = path
        self.source = source
        self.kind = kind


class OverrideValue:
    def __init__(self, field_path: str, raw_value: str, source: OverrideSource) -> None:
        self.field_path = field_path
        self.raw_value = raw_value
        self.source = source


class AppliedOverride:
    def __init__(
        self,
        field_path: str,
        raw_value: str,
        coerced_value: Any,
        source: OverrideSource,
    ) -> None:
        self.field_path = field_path
        self.raw_value = raw_value
        self.coerced_value = coerced_value
        self.source = source


class AssemblyResult:
    def __init__(
        self,
        config: BaseModel,
        resolved_path: ResolvedPath,
        applied_overrides: list[AppliedOverride],
    ) -> None:
        self.config = config
        self.resolved_path = resolved_path
        self.applied_overrides = applied_overrides


class DirAssemblyResult:
    def __init__(self, directory: Path, source: PathSource, files: list[Path]) -> None:
        self.directory = directory
        self.source = source
        self.files = files
