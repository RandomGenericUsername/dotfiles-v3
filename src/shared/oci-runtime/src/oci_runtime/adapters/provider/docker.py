from oci_runtime.adapters.provider._base import BaseCliRuntimeProvider
from oci_runtime.adapters.parser.docker import (
    DockerContainerParser,
    DockerImageParser,
    DockerNetworkParser,
    DockerVolumeParser,
)
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.capabilities import RuntimeCapabilities


class DockerRuntimeProvider(BaseCliRuntimeProvider):
    _kind = RuntimeKind.DOCKER
    _container_parser_cls = DockerContainerParser
    _image_parser_cls = DockerImageParser
    _volume_parser_cls = DockerVolumeParser
    _network_parser_cls = DockerNetworkParser
    _capabilities = RuntimeCapabilities(
        list_format_flags=("--format", "{{json .}}"),
        needs_userns_keep_id=False,
        supports_log_drivers=True,
        tar_entry_name="Dockerfile",
        default_build_flags=("--quiet",),
    )
