import pytest

from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.domain.exceptions import (
    ContainerError,
    ContainerNotFoundError,
    ImageError,
    ImageNotFoundError,
    ImagePullAccessDeniedError,
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
        err = ContainerError(
            message="fail", command=["docker", "run"], exit_code=1, stderr="err"
        )
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


class TestImagePullAccessDeniedError:
    def test_formats_message_with_image_name(self):
        err = ImagePullAccessDeniedError(image_name="private-repo/my-image")
        assert "private-repo/my-image" in str(err)
        assert "Pull access denied" in str(err)

    def test_formats_message_with_registry(self):
        err = ImagePullAccessDeniedError(image_name="my-image", registry="ghcr.io")
        assert "ghcr.io" in str(err)
        assert "registry" in str(err).lower()

    def test_stores_image_name(self):
        err = ImagePullAccessDeniedError(image_name="alpine:latest")
        assert err.image_name == "alpine:latest"

    def test_stores_registry(self):
        err = ImagePullAccessDeniedError(image_name="img", registry="docker.io")
        assert err.registry == "docker.io"

    def test_stores_default_registry(self):
        err = ImagePullAccessDeniedError(image_name="img")
        assert err.registry == ""

    def test_is_image_error(self):
        assert issubclass(ImagePullAccessDeniedError, ImageError)


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


class TestOperationTimeoutError:
    def test_construct_with_command_and_timeout(self):
        from oci_runtime.domain.exceptions import OperationTimeoutError

        err = OperationTimeoutError(
            command=["docker", "ps"],
            timeout=30.0,
            message="Operation timed out",
        )
        assert err.command == ["docker", "ps"]
        assert err.timeout == 30.0

    def test_str_contains_command(self):
        from oci_runtime.domain.exceptions import OperationTimeoutError

        err = OperationTimeoutError(command=["docker", "run"], timeout=None)
        assert "docker run" in str(err)

    def test_is_oci_error(self):
        from oci_runtime.domain.exceptions import OperationTimeoutError

        assert issubclass(OperationTimeoutError, OciError)


class TestImageRuntimeError:
    def test_construct(self):
        from oci_runtime.domain.exceptions import ImageRuntimeError

        err = ImageRuntimeError(
            message="image runtime failed",
            command=["docker", "build"],
            exit_code=1,
        )
        assert err.message == "image runtime failed"
        assert err.exit_code == 1

    def test_is_image_error(self):
        from oci_runtime.domain.exceptions import ImageRuntimeError

        assert issubclass(ImageRuntimeError, ImageError)


class TestVolumeRuntimeError:
    def test_construct(self):
        from oci_runtime.domain.exceptions import VolumeRuntimeError

        err = VolumeRuntimeError(
            message="volume runtime failed",
            command=["docker", "volume", "create"],
            exit_code=1,
        )
        assert err.message == "volume runtime failed"

    def test_is_volume_error(self):
        from oci_runtime.domain.exceptions import VolumeRuntimeError

        assert issubclass(VolumeRuntimeError, VolumeError)


class TestNetworkRuntimeError:
    def test_construct(self):
        from oci_runtime.domain.exceptions import NetworkRuntimeError

        err = NetworkRuntimeError(
            message="network runtime failed",
            command=["docker", "network", "create"],
            exit_code=1,
        )
        assert err.message == "network runtime failed"

    def test_is_network_error(self):
        from oci_runtime.domain.exceptions import NetworkRuntimeError

        assert issubclass(NetworkRuntimeError, NetworkError)


class TestContainerRuntimeError:
    def test_construct(self):
        from oci_runtime.domain.exceptions import ContainerRuntimeError

        err = ContainerRuntimeError(
            message="container runtime failed",
            command=["docker", "run"],
            exit_code=1,
            stderr="error output",
        )
        assert err.message == "container runtime failed"
        assert err.exit_code == 1
        assert err.stderr == "error output"

    def test_is_container_error(self):
        from oci_runtime.domain.exceptions import ContainerRuntimeError

        assert issubclass(ContainerRuntimeError, ContainerError)


class TestOciErrorKeywordContext:
    def test_oci_error_accepts_keyword_command(self):
        err = OciError(
            message="test",
            command=["docker", "ps"],
        )
        assert err.command == ["docker", "ps"]

    def test_oci_error_accepts_keyword_exit_code(self):
        err = OciError(
            message="test",
            exit_code=1,
        )
        assert err.exit_code == 1

    def test_oci_error_accepts_keyword_stderr(self):
        err = OciError(
            message="test",
            stderr="something went wrong",
        )
        assert err.stderr == "something went wrong"

    def test_container_error_accepts_keyword_context(self):
        err = ContainerError(
            message="fail",
            command=["docker", "run"],
            exit_code=1,
            stderr="OOM",
        )
        assert err.command == ["docker", "run"]
        assert err.exit_code == 1
        assert err.stderr == "OOM"


class TestNotFoundErrorContext:
    def test_image_not_found_populates_context(self):
        err = ImageNotFoundError(
            "alpine",
            command=["docker", "pull", "alpine"],
            exit_code=1,
            stderr="No such image",
        )
        assert err.command == ["docker", "pull", "alpine"]
        assert err.exit_code == 1
        assert err.stderr == "No such image"

    def test_container_not_found_populates_context(self):
        err = ContainerNotFoundError(
            "abc123",
            command=["docker", "inspect", "abc123"],
            exit_code=1,
            stderr="No such container",
        )
        assert err.command == ["docker", "inspect", "abc123"]
        assert err.exit_code == 1
        assert err.stderr == "No such container"

    def test_volume_not_found_populates_context(self):
        err = VolumeNotFoundError(
            "my-vol",
            command=["docker", "volume", "inspect", "my-vol"],
            exit_code=1,
            stderr="No such volume",
        )
        assert err.command == ["docker", "volume", "inspect", "my-vol"]
        assert err.exit_code == 1
        assert err.stderr == "No such volume"

    def test_network_not_found_populates_context(self):
        err = NetworkNotFoundError(
            "net1",
            command=["docker", "network", "inspect", "net1"],
            exit_code=1,
            stderr="No such network",
        )
        assert err.command == ["docker", "network", "inspect", "net1"]
        assert err.exit_code == 1
        assert err.stderr == "No such network"


class TestProviderNotRegisteredError:
    def test_construct(self):
        from oci_runtime.domain.exceptions import ProviderNotRegisteredError

        err = ProviderNotRegisteredError(kind="unknown")
        assert "unknown" in str(err)
        assert "No RuntimeProvider registered" in str(err)

    def test_is_oci_error(self):
        from oci_runtime.domain.exceptions import ProviderNotRegisteredError

        assert issubclass(ProviderNotRegisteredError, OciError)

    def test_kind_typed(self):
        from oci_runtime.domain.exceptions import ProviderNotRegisteredError

        err = ProviderNotRegisteredError(RuntimeKind.DOCKER)
        assert err.kind is RuntimeKind.DOCKER


class TestExistingPositionalCallersUnbroken:
    def test_image_not_found_positional_works(self):
        err = ImageNotFoundError("alpine")
        assert err.image_name == "alpine"
        assert "Image not found: alpine" in str(err)

    def test_container_not_found_positional_works(self):
        err = ContainerNotFoundError("abc123")
        assert err.container_id == "abc123"
        assert "Container not found: abc123" in str(err)

    def test_volume_not_found_positional_works(self):
        err = VolumeNotFoundError("my-vol")
        assert err.volume_name == "my-vol"
        assert "Volume not found: my-vol" in str(err)

    def test_network_not_found_positional_works(self):
        err = NetworkNotFoundError("net1")
        assert err.network_name == "net1"
        assert "Network not found: net1" in str(err)


class TestParsingError:
    def test_parsing_error_importable_from_domain(self):
        from oci_runtime.domain import ParsingError
        from oci_runtime.domain.exceptions import ParsingError as P2

        assert ParsingError is P2
