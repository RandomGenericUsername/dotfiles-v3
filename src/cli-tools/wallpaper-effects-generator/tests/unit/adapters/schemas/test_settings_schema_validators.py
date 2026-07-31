from __future__ import annotations

import pytest
from pydantic import ValidationError

from wallpaper_effects_generator.adapters.schemas.settings_schema import (
    ContainerSchema,
    CoreSettingsSchema,
)


class TestContainerSchemaValidators:
    def test_engine_docker_allowed(self) -> None:
        schema = ContainerSchema(engine="docker")
        assert schema.engine == "docker"

    def test_engine_podman_allowed(self) -> None:
        schema = ContainerSchema(engine="podman")
        assert schema.engine == "podman"

    def test_engine_case_insensitive(self) -> None:
        schema = ContainerSchema(engine="DOCKER")
        assert schema.engine == "docker"

    def test_engine_invalid_raises_error(self) -> None:
        with pytest.raises(ValidationError):
            ContainerSchema(engine="invalid")

    def test_engine_empty_string_raises_error(self) -> None:
        with pytest.raises(ValidationError):
            ContainerSchema(engine="")

    def test_registry_slash_strip(self) -> None:
        schema = ContainerSchema(engine="docker", image_registry="ghcr.io/")
        assert schema.image_registry == "ghcr.io"

    def test_registry_multiple_slashes_strip(self) -> None:
        schema = ContainerSchema(engine="docker", image_registry="ghcr.io///")
        assert schema.image_registry == "ghcr.io"

    def test_registry_none_preserved(self) -> None:
        schema = ContainerSchema(engine="docker", image_registry=None)
        assert schema.image_registry is None

    def test_registry_empty_string_preserved(self) -> None:
        schema = ContainerSchema(engine="docker", image_registry="")
        assert schema.image_registry == ""

    def test_registry_no_slash_preserved(self) -> None:
        schema = ContainerSchema(engine="docker", image_registry="ghcr.io")
        assert schema.image_registry == "ghcr.io"


class TestCoreSettingsSchema:
    def test_default_container_engine(self) -> None:
        schema = CoreSettingsSchema()
        assert schema.container.engine == "docker"

    def test_custom_container(self) -> None:
        schema = CoreSettingsSchema(container={"engine": "podman", "image_registry": "myreg.io/"})
        assert schema.container.engine == "podman"
        assert schema.container.image_registry == "myreg.io"
