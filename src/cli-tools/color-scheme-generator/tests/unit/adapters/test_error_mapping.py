from __future__ import annotations

import json

from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.domain.exceptions import (
    ContainerNotFoundError,
    ContainerRuntimeError,
    ImageNotFoundError,
    ImagePullAccessDeniedError,
    ImageRuntimeError,
    OciError,
    OperationTimeoutError,
    ProviderNotRegisteredError,
    RuntimeNotAvailableError,
)

from color_scheme_generator.adapters.error_mapping import map_oci_error
from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import (
    ColorSchemeError,
    ContainerImageNotFoundError,
    ContainerRuntimeUnavailableError,
    ContainerTimeoutError,
    ImagePullAccessError,
)


class TestErrorMapping:
    def test_image_not_found_mapping(self) -> None:
        oci_error = ImageNotFoundError(image_name="test-image:latest")
        domain_error = map_oci_error(oci_error)

        assert isinstance(domain_error, ContainerImageNotFoundError)
        assert domain_error.image == "test-image:latest"

    def test_image_not_found_mapping_with_backend_context(self) -> None:
        oci_error = ImageNotFoundError(image_name="test-image:latest")
        domain_error = map_oci_error(oci_error, backend=Backend.CUSTOM)

        assert isinstance(domain_error, ContainerImageNotFoundError)
        assert domain_error.backend == Backend.CUSTOM

    def test_runtime_not_available_mapping(self) -> None:
        oci_error = RuntimeNotAvailableError(runtime="docker")
        domain_error = map_oci_error(oci_error)

        assert isinstance(domain_error, ContainerRuntimeUnavailableError)
        assert domain_error.runtime == "docker"

    def test_image_pull_access_denied_mapping(self) -> None:
        oci_error = ImagePullAccessDeniedError(
            image_name="private/app",
            registry="ghcr.io",
        )
        domain_error = map_oci_error(oci_error)

        assert isinstance(domain_error, ImagePullAccessError)
        assert domain_error.image == "private/app"
        assert domain_error.registry == "ghcr.io"

    def test_operation_timeout_mapping(self) -> None:
        oci_error = OperationTimeoutError(
            command=["docker", "run"],
            timeout=30.0,
        )
        domain_error = map_oci_error(oci_error)

        assert isinstance(domain_error, ContainerTimeoutError)

    def test_container_not_found_mapping(self) -> None:
        oci_error = ContainerNotFoundError(container_id="abc123")
        domain_error = map_oci_error(oci_error)

        assert isinstance(domain_error, ContainerRuntimeUnavailableError)

    def test_container_runtime_error_mapping(self) -> None:
        oci_error = ContainerRuntimeError("container runtime failure")
        domain_error = map_oci_error(oci_error)

        assert isinstance(domain_error, ContainerRuntimeUnavailableError)

    def test_provider_not_registered_mapping(self) -> None:
        oci_error = ProviderNotRegisteredError(kind=RuntimeKind.DOCKER)
        domain_error = map_oci_error(oci_error)

        assert isinstance(domain_error, ContainerRuntimeUnavailableError)

    def test_image_runtime_error_mapping(self) -> None:
        oci_error = ImageRuntimeError("image runtime failure")
        domain_error = map_oci_error(oci_error)

        assert isinstance(domain_error, ColorSchemeError)

    def test_generic_oci_error_fallback(self) -> None:
        oci_error = OciError("some generic oci error")
        domain_error = map_oci_error(oci_error)

        assert isinstance(domain_error, ColorSchemeError)
        assert "some generic oci error" in str(domain_error)

    def test_non_oci_error_fallback(self) -> None:
        domain_error = map_oci_error(ValueError("unexpected"))

        assert isinstance(domain_error, ColorSchemeError)
        assert "unexpected" in str(domain_error)

    def test_color_scheme_error_passes_through_unmodified(self) -> None:
        original = ContainerImageNotFoundError(image="csg-custom:latest", backend=Backend.CUSTOM)
        domain_error = map_oci_error(original)

        assert domain_error is original


class TestErrorMappingJsonSerialization:
    def test_mapped_exception_serializes_to_json(self, capsys) -> None:
        from color_scheme_generator.adapters.output.json_output import JsonOutput

        oci_error = ImageNotFoundError(image_name="test-image:latest")
        domain_error = map_oci_error(oci_error, backend=Backend.CUSTOM)

        JsonOutput().error(domain_error)
        captured = capsys.readouterr()
        data = json.loads(captured.err)

        assert data["kind"] == "ContainerImageNotFoundError"
        assert "test-image:latest" in data["message"]
