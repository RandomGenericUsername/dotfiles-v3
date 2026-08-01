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

    def test_memory_limit_accepts_valid_shapes(self) -> None:
        assert ContainerSettingsSchema(memory_limit="512m").memory_limit == "512m"
        assert ContainerSettingsSchema(memory_limit="2G").memory_limit == "2g"
        assert ContainerSettingsSchema(memory_limit="128").memory_limit == "128"

    def test_memory_limit_rejects_invalid_shape(self) -> None:
        with pytest.raises(ValidationError, match="Invalid memory limit"):
            ContainerSettingsSchema(memory_limit="abc")
        with pytest.raises(ValidationError, match="Invalid memory limit"):
            ContainerSettingsSchema(memory_limit="512mb")

    def test_negative_timeout_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Timeout must be non-negative"):
            ContainerSettingsSchema(timeout_seconds=-1)
        with pytest.raises(ValidationError, match="Timeout must be non-negative"):
            ContainerSettingsSchema(mount_timeout_seconds=-5)

    def test_zero_timeout_accepted(self) -> None:
        assert ContainerSettingsSchema(timeout_seconds=0).timeout_seconds == 0


class TestNestedCompositePropagation:
    def test_all_nested_fields_propagate(self) -> None:
        data = {
            "output": {
                "directory": "/srv/csg/out",
                "default_formats": ["json", "sh"],
                "overwrite": True,
                "verbosity": 3,
            },
            "generation": {"backend": "wallust", "default_params": {"saturation": "1.0"}},
            "runtime": {"mode": "container"},
            "container": {
                "engine": "podman",
                "image_prefix": "mycsg",
                "image_tag": "v1",
                "timeout_seconds": 120,
                "memory_limit": "1g",
                "mount_timeout_seconds": 15,
            },
        }
        schema = CoreSettingsSchema.model_validate(data)
        assert schema.output.directory == Path("/srv/csg/out")
        assert schema.output.default_formats == ["json", "sh"]
        assert schema.output.overwrite is True
        assert schema.output.verbosity == 3
        assert schema.generation.backend == "wallust"
        assert schema.generation.default_params == {"saturation": "1.0"}
        assert schema.runtime.mode == "container"
        assert schema.container.engine == "podman"
        assert schema.container.image_prefix == "mycsg"
        assert schema.container.image_tag == "v1"
        assert schema.container.timeout_seconds == 120
        assert schema.container.memory_limit == "1g"
        assert schema.container.mount_timeout_seconds == 15

    def test_invalid_nested_value_rejected(self) -> None:
        data = {
            "output": {"directory": "/out"},
            "generation": {"backend": "custom"},
            "runtime": {"mode": "local"},
            "container": {"engine": "containerd"},
        }
        with pytest.raises(ValidationError):
            CoreSettingsSchema.model_validate(data)


class TestDefaultFormatsValidation:
    def test_default_formats_rejects_invalid_color_format(self) -> None:
        from color_scheme_generator.adapters.settings.schema import OutputSettingsSchema

        with pytest.raises(ValidationError):
            OutputSettingsSchema(directory="/out", default_formats=["weird"])

    def test_core_settings_rejects_invalid_default_formats(self) -> None:
        data = {
            "output": {"directory": "/out", "default_formats": ["not-a-format"]},
            "generation": {"backend": "custom"},
            "runtime": {"mode": "local"},
            "container": {"engine": "docker"},
        }
        with pytest.raises(ValidationError):
            CoreSettingsSchema.model_validate(data)
