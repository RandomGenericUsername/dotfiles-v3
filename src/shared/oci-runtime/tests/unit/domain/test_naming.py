from __future__ import annotations

import pytest

from oci_runtime.domain.naming import engine_qualified_image


class TestEngineQualifiedImage:
    def test_no_registry(self) -> None:
        assert engine_qualified_image("weg", "docker", "latest") == "weg-docker:latest"

    def test_with_registry(self) -> None:
        result = engine_qualified_image("weg-managed", "podman", "latest", "ghcr.io")
        assert result == "ghcr.io/weg-managed-podman:latest"

    def test_registry_with_trailing_slash(self) -> None:
        result = engine_qualified_image("weg-managed", "docker", "v1.0", "ghcr.io/")
        assert result == "ghcr.io/weg-managed-docker:v1.0"

    def test_docker_engine(self) -> None:
        result = engine_qualified_image("csg-color-scheme-base", "docker", "latest")
        assert result == "csg-color-scheme-base-docker:latest"

    def test_podman_engine(self) -> None:
        result = engine_qualified_image("csg-color-scheme-custom", "podman", "latest")
        assert result == "csg-color-scheme-custom-podman:latest"

    def test_custom_tag(self) -> None:
        result = engine_qualified_image("weg", "docker", "v2.5.0")
        assert result == "weg-docker:v2.5.0"

    def test_empty_engine_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="engine is required"):
            engine_qualified_image("weg", "", "latest")

    def test_public_api_export(self) -> None:
        from oci_runtime import engine_qualified_image as exported

        assert exported is engine_qualified_image
