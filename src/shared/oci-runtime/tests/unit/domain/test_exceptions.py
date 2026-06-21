import pytest

from oci_runtime.domain.exceptions import (
    ContainerError,
    ContainerNotFoundError,
    ImageError,
    ImageNotFoundError,
    NetworkError,
    NetworkNotFoundError,
    OciError,
    RuntimeNotAvailableError,
    VolumeError,
    VolumeNotFoundError,
)


class TestContainerError:
    def test_stores_command_exit_code_stderr(self):
        err = ContainerError(
            message="something failed",
            command=["docker", "run", "image"],
            exit_code=1,
            stderr="Error: OOM killed",
        )
        assert err.command == ["docker", "run", "image"]
        assert err.exit_code == 1
        assert err.stderr == "Error: OOM killed"

    def test_message_only(self):
        err = ContainerError(message="simple error")
        assert err.command is None
        assert err.exit_code is None
        assert err.stderr is None

    def test_str_includes_details(self):
        err = ContainerError(message="fail", command=["docker", "run"], exit_code=1, stderr="err")
        msg = str(err)
        assert "fail" in msg
        assert "docker run" in msg
        assert "Exit code: 1" in msg
        assert "err" in msg

    def test_is_exception(self):
        assert issubclass(ContainerError, Exception)


class TestImageError:
    def test_is_oci_error(self):
        assert issubclass(ImageError, OciError)

    def test_is_not_container_error(self):
        assert not issubclass(ImageError, ContainerError)

    def test_raise(self):
        with pytest.raises(ImageError):
            raise ImageError(message="image error")


class TestVolumeError:
    def test_is_oci_error(self):
        assert issubclass(VolumeError, OciError)

    def test_is_not_container_error(self):
        assert not issubclass(VolumeError, ContainerError)

    def test_raise(self):
        with pytest.raises(VolumeError):
            raise VolumeError(message="volume error")


class TestNetworkError:
    def test_is_oci_error(self):
        assert issubclass(NetworkError, OciError)

    def test_is_not_container_error(self):
        assert not issubclass(NetworkError, ContainerError)

    def test_raise(self):
        with pytest.raises(NetworkError):
            raise NetworkError(message="network error")


class TestImageNotFoundError:
    def test_formats_message_with_image_name(self):
        err = ImageNotFoundError(image_name="alpine:latest")
        assert "alpine:latest" in str(err)
        assert "Image not found" in str(err)

    def test_stores_image_name(self):
        err = ImageNotFoundError(image_name="nginx:1.25")
        assert err.image_name == "nginx:1.25"

    def test_is_image_error(self):
        assert issubclass(ImageNotFoundError, ImageError)


class TestContainerNotFoundError:
    def test_formats_message_with_container_id(self):
        err = ContainerNotFoundError(container_id="abc123")
        assert "abc123" in str(err)
        assert "Container not found" in str(err)

    def test_stores_container_id(self):
        err = ContainerNotFoundError(container_id="abc123")
        assert err.container_id == "abc123"

    def test_is_container_error(self):
        assert issubclass(ContainerNotFoundError, ContainerError)


class TestVolumeNotFoundError:
    def test_formats_message_with_volume_name(self):
        err = VolumeNotFoundError(volume_name="my-vol")
        assert "my-vol" in str(err)
        assert "Volume not found" in str(err)

    def test_stores_volume_name(self):
        err = VolumeNotFoundError(volume_name="my-vol")
        assert err.volume_name == "my-vol"

    def test_is_volume_error(self):
        assert issubclass(VolumeNotFoundError, VolumeError)


class TestNetworkNotFoundError:
    def test_formats_message_with_network_name(self):
        err = NetworkNotFoundError(network_name="net1")
        assert "net1" in str(err)
        assert "Network not found" in str(err)

    def test_stores_network_name(self):
        err = NetworkNotFoundError(network_name="net1")
        assert err.network_name == "net1"

    def test_is_network_error(self):
        assert issubclass(NetworkNotFoundError, NetworkError)


class TestRuntimeNotAvailableError:
    def test_formats_message_with_runtime_name(self):
        err = RuntimeNotAvailableError(runtime="podman")
        assert "podman" in str(err)
        assert "not available" in str(err)

    def test_stores_runtime(self):
        err = RuntimeNotAvailableError(runtime="podman")
        assert err.runtime == "podman"

    def test_is_oci_error(self):
        assert issubclass(RuntimeNotAvailableError, OciError)

    def test_is_not_container_error(self):
        assert not issubclass(RuntimeNotAvailableError, ContainerError)


