from oci_runtime.adapters.managers.container import CliContainerManager
from oci_runtime.adapters.managers.image import CliImageManager
from oci_runtime.adapters.managers.network import CliNetworkManager
from oci_runtime.adapters.managers.volume import CliVolumeManager
from oci_runtime.adapters.parser.docker import (
    DockerContainerParser,
    DockerImageParser,
    DockerNetworkParser,
    DockerVolumeParser,
)
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.factory import Managers, Parsers
from oci_runtime.ports.provider import RuntimeProvider
from oci_runtime.ports.transport import Transport


class DockerRuntimeProvider(RuntimeProvider):
    @property
    def kind(self) -> RuntimeKind:
        return RuntimeKind.DOCKER

    def capabilities(self) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            list_format_flags=["--format", "{{json .}}"],
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

    def create_managers(self, transport: Transport, caps: RuntimeCapabilities) -> Managers:
        parsers = self.create_parsers()
        return Managers(
            image_manager=CliImageManager(transport, parsers.image_parser, caps),
            container_manager=CliContainerManager(transport, parsers.container_parser, caps),
            volume_manager=CliVolumeManager(transport, parsers.volume_parser, caps),
            network_manager=CliNetworkManager(transport, parsers.network_parser, caps),
        )
