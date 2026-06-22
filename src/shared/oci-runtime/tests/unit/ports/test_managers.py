from abc import ABC


from oci_runtime.domain.types import (
    ImageInfo,
    PruneResult,
)
from oci_runtime.ports.managers import (
    ContainerManager,
    ImageManager,
    NetworkManager,
    VolumeManager,
)
from oci_runtime.ports.parsers import ImageParser
from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.transport import Transport


class _Parser(ImageParser):
    def parse_inspect(self, raw: str) -> ImageInfo: ...
    def parse_list(self, raw: str) -> list[ImageInfo]: ...
    def parse_build_output(self, raw: str) -> str: ...
    def parse_digest_from_pull(self, raw: str) -> str: ...
    def parse_prune(self, raw: str) -> PruneResult:
        return PruneResult()
    def is_not_found_error(self, stderr: str) -> bool:
        return "No such image" in stderr


class TestImageManager:
    def test_is_abc(self):
        assert issubclass(ImageManager, ABC)

    def test_has_abstract_build(self):
        assert ImageManager.build.__isabstractmethod__


class TestContainerManager:
    def test_is_abc(self):
        assert issubclass(ContainerManager, ABC)

    def test_has_abstract_run(self):
        assert ContainerManager.run.__isabstractmethod__


class TestVolumeManager:
    def test_is_abc(self):
        assert issubclass(VolumeManager, ABC)

    def test_has_abstract_create(self):
        assert VolumeManager.create.__isabstractmethod__


class TestNetworkManager:
    def test_is_abc(self):
        assert issubclass(NetworkManager, ABC)

    def test_has_abstract_create(self):
        assert NetworkManager.create.__isabstractmethod__


def _make_transport() -> Transport:
    class T(Transport):
        def execute(self, command, *, timeout=None, input_data=None):
            return RawExecResult(returncode=0, stdout=b"", stderr=b"")
        def get_runtime_binary(self) -> str:
            return "docker"
        def probe(self) -> bool:
            return True
    return T()
