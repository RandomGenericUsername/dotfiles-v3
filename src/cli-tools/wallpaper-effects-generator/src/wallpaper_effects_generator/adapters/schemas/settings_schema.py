from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ExecutionSchema(BaseModel):
    parallel: bool = True
    strict: bool = False
    max_workers: int = 0


class OutputSchema(BaseModel):
    verbosity: int = 1
    directory: str = "/tmp/wallpaper-effects"


class ProcessingSchema(BaseModel):
    temp_dir: str = "/tmp/.wallpaper-effects-tmp"


class BackendSchema(BaseModel):
    binary: str = "magick"


class RuntimeSchema(BaseModel):
    mode: str = "local"


class ContainerSchema(BaseModel):
    engine: str = "docker"
    image_name: str = "weg"
    image_tag: str = "latest"
    image_registry: str | None = ""

    @field_validator("engine")
    @classmethod
    def validate_engine(cls, v: str) -> str:
        allowed = {"docker", "podman"}
        if v.lower() not in allowed:
            raise ValueError(f"engine must be one of {allowed}, got '{v}'")
        return v.lower()

    @field_validator("image_registry")
    @classmethod
    def strip_trailing_slash(cls, v: str | None) -> str | None:
        if v:
            return v.rstrip("/")
        return v


class CoreSettingsSchema(BaseModel):
    version: str = "1.0"
    execution: ExecutionSchema = Field(default_factory=ExecutionSchema)
    output: OutputSchema = Field(default_factory=OutputSchema)
    processing: ProcessingSchema = Field(default_factory=ProcessingSchema)
    backend: BackendSchema = Field(default_factory=BackendSchema)
    runtime: RuntimeSchema = Field(default_factory=RuntimeSchema)
    container: ContainerSchema = Field(default_factory=ContainerSchema)
