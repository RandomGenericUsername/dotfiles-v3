from oci_runtime.adapters.managers.container import CliContainerManager
from oci_runtime.adapters.managers.image import CliImageManager
from oci_runtime.adapters.managers.network import CliNetworkManager
from oci_runtime.adapters.managers.volume import CliVolumeManager
from oci_runtime.adapters.parser.podman import (
    PodmanContainerParser,
    PodmanImageParser,
    PodmanNetworkParser,
    PodmanVolumeParser,
)
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.factory import Managers, Parsers
from oci_runtime.ports.provider import RuntimeProvider
from oci_runtime.ports.transport import Transport


class PodmanRuntimeProvider(RuntimeProvider):
    @property
    def kind(self) -> RuntimeKind:
        return RuntimeKind.PODMAN

    def capabilities(self) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            supported_output_formats=["json"],
            needs_userns_keep_id=True,
            supports_log_drivers=False,
            tar_entry_name="Containerfile",
            default_run_flags=["--userns=keep-id"],
            default_build_flags=["--quiet"],
        )

    def create_parsers(self) -> Parsers:
        return Parsers(
            container_parser=PodmanContainerParser(), image_parser=PodmanImageParser(),
            volume_parser=PodmanVolumeParser(), network_parser=PodmanNetworkParser(),
        )

    def create_managers(self, transport: Transport, caps: RuntimeCapabilities) -> Managers:
        parsers = self.create_parsers()
        return Managers(
            image_manager=CliImageManager(transport, parsers.image_parser, caps),
            container_manager=CliContainerManager(transport, parsers.container_parser, caps),
            volume_manager=CliVolumeManager(transport, parsers.volume_parser, caps),
            network_manager=CliNetworkManager(transport, parsers.network_parser, caps),
        )
