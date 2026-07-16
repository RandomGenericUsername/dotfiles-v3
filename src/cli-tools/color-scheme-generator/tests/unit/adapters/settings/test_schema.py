from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from color_scheme_generator.adapters.settings.schema import (
    ContainerSettingsSchema,
    CoreSettingsSchema,
    GenerationSettingsSchema,
    RuntimeSettingsSchema,
)


class TestCoreSettingsSchema:
    def test_valid_full_config(self) -> None:
        data = {
            "output": {"directory": "/tmp/out", "default_formats": ["json"], "overwrite": True},
            "generation": {"backend": "custom", "default_params": {"quality": "high"}},
            "template": {"templates_dir": "/templates", "custom_templates_dir": None},
            "runtime": {"mode": "local"},
            "container": {"engine": "docker", "image_prefix": "myapp", "timeout_seconds": 600},
        }
        schema = CoreSettingsSchema.model_validate(data)
        assert schema.output.directory == Path("/tmp/out")
        assert schema.generation.backend == "custom"
        assert schema.runtime.mode == "local"
        assert schema.container.engine == "docker"

    def test_minimal_config_with_defaults(self) -> None:
        data = {
            "output": {"directory": "/out"},
            "generation": {"backend": "wallust"},
            "runtime": {"mode": "container"},
            "container": {"engine": "podman"},
        }
        schema = CoreSettingsSchema.model_validate(data)
        assert schema.output.overwrite is False
        assert schema.container.image_prefix == "csg"
        assert schema.container.memory_limit == "512m"

    def test_missing_required_field_raises(self) -> None:
        with pytest.raises(ValidationError):
            CoreSettingsSchema.model_validate({})


class TestGenerationSettingsSchema:
    def test_valid_backend_custom(self) -> None:
        schema = GenerationSettingsSchema(backend="custom")
        assert schema.backend == "custom"

    def test_valid_backend_pywal(self) -> None:
        schema = GenerationSettingsSchema(backend="pywal")
        assert schema.backend == "pywal"

    def test_valid_backend_wallust(self) -> None:
        schema = GenerationSettingsSchema(backend="wallust")
        assert schema.backend == "wallust"

    def test_auto_raises(self) -> None:
        with pytest.raises(ValidationError, match="not a valid backend"):
            GenerationSettingsSchema(backend="auto")

    def test_invalid_backend_raises(self) -> None:
        with pytest.raises(ValidationError, match="Invalid backend"):
            GenerationSettingsSchema(backend="nonexistent")


class TestRuntimeSettingsSchema:
    def test_valid_local(self) -> None:
        schema = RuntimeSettingsSchema(mode="local")
        assert schema.mode == "local"

    def test_valid_container(self) -> None:
        schema = RuntimeSettingsSchema(mode="container")
        assert schema.mode == "container"

    def test_invalid_mode_raises(self) -> None:
        with pytest.raises(ValidationError, match="Invalid runtime mode"):
            RuntimeSettingsSchema(mode="hybrid")


class TestContainerSettingsSchema:
    def test_valid_docker(self) -> None:
        schema = ContainerSettingsSchema(engine="docker")
        assert schema.engine == "docker"

    def test_valid_podman(self) -> None:
        schema = ContainerSettingsSchema(engine="podman")
        assert schema.engine == "podman"

    def test_invalid_engine_raises(self) -> None:
        with pytest.raises(ValidationError, match="Invalid container engine"):
            ContainerSettingsSchema(engine="containerd")
