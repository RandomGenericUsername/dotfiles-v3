from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.aggregates import Parsers
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.provider import RuntimeProvider
from oci_runtime.ports.parsers import (
    ContainerParser,
    ImageParser,
    NetworkParser,
    VolumeParser,
)


_DOCKER_CAPABILITIES = RuntimeCapabilities(
    list_format_flags=("--format", "{{json .}}"),
    needs_userns_keep_id=False,
    supports_log_drivers=True,
    tar_entry_name="Dockerfile",
    default_build_flags=("--quiet",),
)


class DockerRuntimeProvider(RuntimeProvider):
    def __init__(
        self,
        *,
        container_parser_cls: type[ContainerParser],
        image_parser_cls: type[ImageParser],
        volume_parser_cls: type[VolumeParser],
        network_parser_cls: type[NetworkParser],
        capabilities: RuntimeCapabilities | None = None,
    ):
        self._kind = RuntimeKind.DOCKER
        self._container_parser_cls = container_parser_cls
        self._image_parser_cls = image_parser_cls
        self._volume_parser_cls = volume_parser_cls
        self._network_parser_cls = network_parser_cls
        self._capabilities = (
            capabilities if capabilities is not None else _DOCKER_CAPABILITIES
        )

    @property
    def kind(self) -> RuntimeKind:
        return self._kind

    def capabilities(self) -> RuntimeCapabilities:
        return self._capabilities

    def create_parsers(self) -> Parsers:
        return Parsers(
            container_parser=self._container_parser_cls(),
            image_parser=self._image_parser_cls(),
            volume_parser=self._volume_parser_cls(),
            network_parser=self._network_parser_cls(),
        )
