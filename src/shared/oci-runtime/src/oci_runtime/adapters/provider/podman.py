from oci_runtime.adapters.provider._base import BaseCliRuntimeProvider
from oci_runtime.adapters.parser.podman import (
    PodmanContainerParser,
    PodmanImageParser,
    PodmanNetworkParser,
    PodmanVolumeParser,
)
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.capabilities import RuntimeCapabilities


class PodmanRuntimeProvider(BaseCliRuntimeProvider):
    _kind = RuntimeKind.PODMAN
    _container_parser_cls = PodmanContainerParser
    _image_parser_cls = PodmanImageParser
    _volume_parser_cls = PodmanVolumeParser
    _network_parser_cls = PodmanNetworkParser
    _capabilities = RuntimeCapabilities(
        list_format_flags=["--format", "json"],
        needs_userns_keep_id=True,
        supports_log_drivers=False,
        tar_entry_name="Containerfile",
        default_run_flags=["--userns=keep-id"],
        default_build_flags=["--quiet"],
    )
