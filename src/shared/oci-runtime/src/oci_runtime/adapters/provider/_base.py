from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.aggregates import Parsers
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.provider import RuntimeProvider


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
