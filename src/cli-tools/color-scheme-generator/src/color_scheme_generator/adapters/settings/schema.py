from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, field_validator

from color_scheme_generator.domain.enums import Backend, ContainerEngine, RuntimeMode

_MEMORY_LIMIT_PATTERN = re.compile(r"^\d+[kKmMgGtT]?$")


class OutputSettingsSchema(BaseModel):
    directory: Path
    default_formats: list[str] = []
    overwrite: bool = False

    @field_validator("directory", mode="before")
    @classmethod
    def _validate_directory_not_empty(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            raise ValueError("directory must not be empty")
        return v


class GenerationSettingsSchema(BaseModel):
    backend: str
    default_params: dict[str, Any] = {}

    @field_validator("backend")
    @classmethod
    def _validate_backend(cls, v: str) -> str:
        valid = {m.value for m in Backend}
        if v == "auto":
            raise ValueError(
                f"'auto' is not a valid backend — choose one of: {', '.join(sorted(valid))}"
            )
        if v not in valid:
            raise ValueError(f"Invalid backend '{v}' — must be one of: {', '.join(sorted(valid))}")
        return v


class TemplateSettingsSchema(BaseModel):
    templates_dir: Path | None = None
    custom_templates_dir: Path | None = None

    @field_validator("templates_dir", "custom_templates_dir")
    @classmethod
    def _validate_path_exists(cls, v: Path | None) -> Path | None:
        if v is not None and not v.exists():
            raise ValueError(f"Path does not exist: {v}")
        return v


class RuntimeSettingsSchema(BaseModel):
    mode: str

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, v: str) -> str:
        valid = {m.value for m in RuntimeMode}
        if v not in valid:
            raise ValueError(
                f"Invalid runtime mode '{v}' — must be one of: {', '.join(sorted(valid))}"
            )
        return v


class ContainerSettingsSchema(BaseModel):
    engine: str

    @field_validator("engine")
    @classmethod
    def _validate_engine(cls, v: str) -> str:
        valid = {m.value for m in ContainerEngine}
        if v not in valid:
            raise ValueError(
                f"Invalid container engine '{v}' — must be one of: {', '.join(sorted(valid))}"
            )
        return v

    @field_validator("memory_limit")
    @classmethod
    def _validate_memory_limit(cls, v: str) -> str:
        if not _MEMORY_LIMIT_PATTERN.match(v):
            raise ValueError(
                f"Invalid memory limit '{v}' — must be a number optionally followed by k/m/g/t"
            )
        return v.lower()

    @field_validator("timeout_seconds", "mount_timeout_seconds")
    @classmethod
    def _validate_timeout(cls, v: int) -> int:
        if v < 0:
            raise ValueError(f"Timeout must be non-negative, got {v}")
        return v

    image_prefix: str = "csg"
    image_tag: str = "latest"
    timeout_seconds: int = 300
    memory_limit: str = "512m"
    mount_timeout_seconds: int = 30


class CoreSettingsSchema(BaseModel):
    output: OutputSettingsSchema
    generation: GenerationSettingsSchema
    template: TemplateSettingsSchema = TemplateSettingsSchema()
    runtime: RuntimeSettingsSchema
    container: ContainerSettingsSchema
