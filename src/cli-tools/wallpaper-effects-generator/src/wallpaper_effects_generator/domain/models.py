from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wallpaper_effects_generator.domain.enums import (
    ItemType,
    RuntimeMode,
    Verbosity,
)


@dataclass(frozen=True)
class ParameterDefinition:
    key: str
    description: str
    default: Any = None
    required: bool = False


@dataclass(frozen=True)
class EffectDefinition:
    name: str
    description: str
    command: str
    parameters: tuple[ParameterDefinition, ...] = ()
    item_type: ItemType = ItemType.EFFECT


@dataclass(frozen=True)
class ChainStep:
    effect_name: str
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.parameters is None:
            object.__setattr__(self, "parameters", {})


@dataclass(frozen=True)
class CompositeDefinition:
    name: str
    description: str
    steps: tuple[ChainStep, ...] = ()


@dataclass(frozen=True)
class PresetDefinition:
    name: str
    description: str
    effects: tuple[str, ...] = ()


@dataclass(frozen=True)
class EffectsCatalog:
    effects: tuple[EffectDefinition, ...] = ()
    composites: tuple[CompositeDefinition, ...] = ()
    presets: tuple[PresetDefinition, ...] = ()


@dataclass(frozen=True)
class ProcessingRequest:
    input_path: Path
    output_path: Path
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CommandResult:
    stdout: str
    stderr: str
    return_code: int
    duration: float = 0.0


@dataclass(frozen=True)
class ProcessingResult:
    success: bool
    command: str
    stdout: str
    stderr: str
    return_code: int
    duration: float = 0.0
    output_path: Path | None = None


@dataclass(frozen=True)
class BatchRequest:
    input_path: Path
    output_dir: Path
    item_types: tuple[ItemType, ...] = (ItemType.EFFECT,)
    flat: bool = False
    explicit_output: bool = False
    parallel: bool = True
    strict: bool = False
    max_workers: int = 4

    def __post_init__(self) -> None:
        if self.max_workers < 1:
            raise ValueError(f"max_workers must be >= 1, got {self.max_workers}")


@dataclass(frozen=True)
class BatchResult:
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    results: tuple[ProcessingResult, ...] = ()
    output_dir: Path | None = None


@dataclass(frozen=True)
class ExecutionSettings:
    parallel: bool = True
    strict: bool = False
    max_workers: int = 4

    def __post_init__(self) -> None:
        if self.max_workers < 1:
            raise ValueError(f"max_workers must be >= 1, got {self.max_workers}")


@dataclass(frozen=True)
class OutputSettings:
    verbosity: Verbosity = Verbosity.NORMAL
    directory: Path | None = None


@dataclass(frozen=True)
class ProcessingSettings:
    temp_dir: Path | None = None


@dataclass(frozen=True)
class BackendSettings:
    binary: str = "magick"


@dataclass(frozen=True)
class RuntimeSettings:
    mode: RuntimeMode = RuntimeMode.LOCAL


@dataclass(frozen=True)
class ContainerSettings:
    engine: str = "docker"
    image_tag: str = "latest"
    image_registry: str | None = None


@dataclass(frozen=True)
class AppSettings:
    version: str = "0.1.0"
    execution: ExecutionSettings = field(default_factory=ExecutionSettings)
    output: OutputSettings = field(default_factory=OutputSettings)
    processing: ProcessingSettings = field(default_factory=ProcessingSettings)
    backend: BackendSettings = field(default_factory=BackendSettings)
    runtime: RuntimeSettings = field(default_factory=RuntimeSettings)
    container: ContainerSettings = field(default_factory=ContainerSettings)
