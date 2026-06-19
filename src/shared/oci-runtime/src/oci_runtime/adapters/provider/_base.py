from oci_runtime.adapters.managers.container import CliContainerManager
from oci_runtime.adapters.managers.image import CliImageManager
from oci_runtime.adapters.managers.network import CliNetworkManager
from oci_runtime.adapters.managers.volume import CliVolumeManager
from oci_runtime.adapters.tty import StdoutTtyDetector
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.aggregates import Managers, Parsers
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.provider import RuntimeProvider
from oci_runtime.ports.streaming import StreamingTransport
from oci_runtime.ports.transport import Transport


class BaseCliRuntimeProvider(RuntimeProvider):
    """Base for CLI-based runtime providers.

    Concrete subclasses declare:
      _kind: RuntimeKind
      _capabilities: RuntimeCapabilities
      _container_parser_cls, _image_parser_cls,
      _volume_parser_cls, _network_parser_cls
    """

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

    def create_managers(self, transport: Transport, streaming_transport: StreamingTransport, caps: RuntimeCapabilities) -> Managers:
        parsers = self.create_parsers()
        return Managers(
            image_manager=CliImageManager(transport, parsers.image_parser, caps),
            container_manager=CliContainerManager(
                transport, parsers.container_parser, caps, streaming=streaming_transport,
                tty_detector=StdoutTtyDetector(),
            ),
            volume_manager=CliVolumeManager(transport, parsers.volume_parser, caps),
            network_manager=CliNetworkManager(transport, parsers.network_parser, caps),
        )
