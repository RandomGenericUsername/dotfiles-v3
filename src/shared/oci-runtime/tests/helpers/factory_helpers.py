from oci_runtime.adapters.helpers.list_executor import CliListExecutor
from oci_runtime.adapters.helpers.result_checker import CliResultChecker
from oci_runtime.adapters.managers.container import CliContainerManager
from oci_runtime.adapters.managers.image import CliImageManager
from oci_runtime.adapters.managers.network import CliNetworkManager
from oci_runtime.adapters.managers.volume import CliVolumeManager
from oci_runtime.domain.exceptions import (
    ContainerNotFoundError,
    ContainerRuntimeError,
    ImageNotFoundError,
    ImagePullAccessDeniedError,
    ImageRuntimeError,
    NetworkNotFoundError,
    NetworkRuntimeError,
    VolumeNotFoundError,
    VolumeRuntimeError,
)
from oci_runtime.ports.cancellation import ThreadCancellationToken

from tests.helpers.mock_transport import FakeTtyDetector, MockPtyTransport


def image_mgr(transport, parser, caps):
    chk = CliResultChecker(
        generic_error=ImageRuntimeError,
        not_found_error=ImageNotFoundError,
        is_not_found=parser.is_not_found_error,
        auth_error=ImagePullAccessDeniedError,
        is_auth=parser.is_auth_error,
    )
    return CliImageManager(
        transport,
        parser,
        caps,
        result_checker=chk,
        list_executor=CliListExecutor(transport, caps, chk, parse_list=parser.parse_list),
    )


def container_mgr(transport, parser, caps, streaming, tty_detector=None, **extra):
    chk = CliResultChecker(
        generic_error=ContainerRuntimeError,
        not_found_error=ContainerNotFoundError,
        is_not_found=parser.is_not_found_error,
    )
    if tty_detector is None:
        tty_detector = FakeTtyDetector()
    return CliContainerManager(
        transport,
        parser,
        caps,
        streaming=streaming,
        tty_detector=tty_detector,
        pty_transport=MockPtyTransport(),
        cancellation_factory=lambda: ThreadCancellationToken(),
        result_checker=chk,
        list_executor=CliListExecutor(transport, caps, chk, parse_list=parser.parse_list),
        **extra,
    )


def volume_mgr(transport, parser, caps):
    chk = CliResultChecker(
        generic_error=VolumeRuntimeError,
        not_found_error=VolumeNotFoundError,
        is_not_found=parser.is_not_found_error,
    )
    return CliVolumeManager(
        transport,
        parser,
        caps,
        result_checker=chk,
        list_executor=CliListExecutor(transport, caps, chk, parse_list=parser.parse_list),
    )


def network_mgr(transport, parser, caps):
    chk = CliResultChecker(
        generic_error=NetworkRuntimeError,
        not_found_error=NetworkNotFoundError,
        is_not_found=parser.is_not_found_error,
    )
    return CliNetworkManager(
        transport,
        parser,
        caps,
        result_checker=chk,
        list_executor=CliListExecutor(transport, caps, chk, parse_list=parser.parse_list),
    )
