from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from color_scheme_generator.adapters.oci_container_runtime import OciContainerRuntimeAdapter
from color_scheme_generator.domain.exceptions import ImageBuildError, ImageRemoveError


@pytest.fixture
def mock_oci_engine() -> MagicMock:
    engine = MagicMock()
    engine.images.build.return_value = "sha256:abc123"
    engine.images.remove.return_value = None
    return engine


@pytest.fixture
def adapter(mock_oci_engine: MagicMock) -> OciContainerRuntimeAdapter:
    return OciContainerRuntimeAdapter(mock_oci_engine)


class TestBuildImage:
    def test_delegates_to_oci_engine_build(
        self,
        adapter: OciContainerRuntimeAdapter,
        mock_oci_engine: MagicMock,
    ) -> None:
        from oci_runtime.domain.types import BuildContext

        context = BuildContext(build_file_path=Path("/tmp/Dockerfile.test"))
        result = adapter.build_image(context, "test-image:latest", timeout=600)

        mock_oci_engine.images.build.assert_called_once_with(
            context, "test-image:latest", 600
        )
        assert result == "sha256:abc123"

    def test_oci_build_error_maps_to_image_build_error(
        self,
        adapter: OciContainerRuntimeAdapter,
        mock_oci_engine: MagicMock,
    ) -> None:
        from oci_runtime.domain.exceptions import ImageError

        mock_oci_engine.images.build.side_effect = ImageError("build failure")
        from oci_runtime.domain.types import BuildContext

        context = BuildContext(build_file_path=Path("/tmp/Dockerfile.test"))

        with pytest.raises(ImageBuildError) as exc_info:
            adapter.build_image(context, "test-image:latest")

        assert "test-image:latest" in str(exc_info.value)
        assert "build failure" in str(exc_info.value)

    def test_default_timeout_is_600(
        self,
        adapter: OciContainerRuntimeAdapter,
        mock_oci_engine: MagicMock,
    ) -> None:
        from oci_runtime.domain.types import BuildContext

        context = BuildContext(build_file_path=Path("/tmp/Dockerfile.test"))
        adapter.build_image(context, "test-image:latest")

        _, _, timeout = mock_oci_engine.images.build.call_args[0]
        assert timeout == 600


class TestRemoveImage:
    def test_delegates_to_oci_engine_remove(
        self,
        adapter: OciContainerRuntimeAdapter,
        mock_oci_engine: MagicMock,
    ) -> None:
        adapter.remove_image("test-image:latest", force=False)

        mock_oci_engine.images.remove.assert_called_once_with(
            "test-image:latest", force=False
        )

    def test_force_flag_forwarded(
        self,
        adapter: OciContainerRuntimeAdapter,
        mock_oci_engine: MagicMock,
    ) -> None:
        adapter.remove_image("test-image:latest", force=True)

        mock_oci_engine.images.remove.assert_called_once_with(
            "test-image:latest", force=True
        )

    def test_oci_remove_error_maps_to_image_remove_error(
        self,
        adapter: OciContainerRuntimeAdapter,
        mock_oci_engine: MagicMock,
    ) -> None:
        from oci_runtime.domain.exceptions import ImageError

        mock_oci_engine.images.remove.side_effect = ImageError("remove failure")

        with pytest.raises(ImageRemoveError) as exc_info:
            adapter.remove_image("test-image:latest")

        assert "test-image:latest" in str(exc_info.value)
        assert "remove failure" in str(exc_info.value)


class TestDockerfileResolution:
    def test_dockerfile_resolution_works_for_all_backends(self) -> None:
        from importlib.resources import files as pkg_files

        for suffix in ("base", "custom", "pywal", "wallust"):
            path = pkg_files("color_scheme_generator.adapters.docker").joinpath(
                f"Dockerfile.{suffix}"
            )
            assert path.exists(), f"Dockerfile.{suffix} not found at {path}"
