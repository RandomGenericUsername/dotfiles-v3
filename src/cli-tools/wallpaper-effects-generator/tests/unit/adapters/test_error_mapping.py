from __future__ import annotations

from oci_runtime.domain.exceptions import (
    ImageError,
    ImageNotFoundError,
    ImagePullAccessDeniedError,
    RuntimeNotAvailableError,
)

from wallpaper_effects_generator.adapters.error_mapping import map_oci_error
from wallpaper_effects_generator.domain.exceptions import (
    CommandExecutionError,
    ContainerImageNotFoundError,
    ContainerRuntimeUnavailableError,
    ImagePullAccessError,
)


class TestErrorMapping:
    def test_map_runtime_not_available(self) -> None:
        oci_error = RuntimeNotAvailableError(runtime="docker")
        domain_error = map_oci_error(oci_error)
        assert isinstance(domain_error, ContainerRuntimeUnavailableError)
        assert "docker" in str(domain_error)

    def test_map_image_not_found(self) -> None:
        oci_error = ImageNotFoundError(
            image_name="nginx:latest",
            command=["docker", "inspect", "nginx"],
            exit_code=1,
            stderr="not found",
        )
        domain_error = map_oci_error(oci_error)
        assert isinstance(domain_error, ContainerImageNotFoundError)
        assert "nginx" in str(domain_error)

    def test_map_pull_access_denied(self) -> None:
        oci_error = ImagePullAccessDeniedError(
            image_name="private/app",
            registry="ghcr.io",
            command=["docker", "pull", "private/app"],
            exit_code=1,
            stderr="denied",
        )
        domain_error = map_oci_error(oci_error)
        assert isinstance(domain_error, ImagePullAccessError)
        assert "private/app" in str(domain_error)
        assert "ghcr.io" in str(domain_error)

    def test_map_generic_image_error(self) -> None:
        oci_error = ImageError(
            "Generic image failure",
            command=["docker", "build", "."],
            exit_code=1,
            stderr="build failed",
        )
        domain_error = map_oci_error(oci_error)
        assert isinstance(domain_error, CommandExecutionError)

    def test_map_unknown_error(self) -> None:
        oci_error = ValueError("something unexpected")
        domain_error = map_oci_error(oci_error)
        assert isinstance(domain_error, CommandExecutionError)
