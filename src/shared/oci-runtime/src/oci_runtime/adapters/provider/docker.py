from oci_runtime.adapters.parser.docker import (
    DockerContainerParser,
    DockerImageParser,
    DockerNetworkParser,
    DockerVolumeParser,
)
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.factory import Parsers
from oci_runtime.ports.provider import RuntimeProvider


class DockerRuntimeProvider(RuntimeProvider):
    @property
    def kind(self) -> RuntimeKind:
        return RuntimeKind.DOCKER

    def capabilities(self) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            supported_output_formats=["json", "yaml"],
            needs_userns_keep_id=False,
            supports_log_drivers=True,
            tar_entry_name="Dockerfile",
            default_build_flags=["--quiet"],
        )

    def create_parsers(self) -> Parsers:
        return Parsers(
            container_parser=DockerContainerParser(), image_parser=DockerImageParser(),
            volume_parser=DockerVolumeParser(), network_parser=DockerNetworkParser(),
        )
