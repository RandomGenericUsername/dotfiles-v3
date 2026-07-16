from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, field_validator

from color_scheme_generator.domain.enums import Backend, ContainerEngine, RuntimeMode


class OutputSettingsSchema(BaseModel):
    directory: Path
    default_formats: list[str] = []
    overwrite: bool = False


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
