from oci_runtime.adapters.parser.podman import (
    PodmanContainerParser,
    PodmanImageParser,
    PodmanNetworkParser,
    PodmanVolumeParser,
)
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.factory import Parsers
from oci_runtime.ports.provider import RuntimeProvider


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
