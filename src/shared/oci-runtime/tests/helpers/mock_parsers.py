from oci_runtime.domain.types import ContainerInfo, ImageInfo, PruneResult, VolumeInfo, NetworkInfo
from oci_runtime.domain.enums import ContainerState
from oci_runtime.ports.parsers import ContainerParser, ImageParser, VolumeParser, NetworkParser


class MockContainerParser(ContainerParser):
    def parse_inspect(self, raw: str) -> ContainerInfo:
        return ContainerInfo(id="abc", name="c1", image="alpine", state=ContainerState.RUNNING, status="Up")
    def parse_list(self, raw: str) -> list[ContainerInfo]:
        return [ContainerInfo(id="abc", name="c1", image="alpine", state=ContainerState.RUNNING, status="Up")]
    def parse_prune(self, raw: str) -> PruneResult:
        return PruneResult()
    def is_not_found_error(self, stderr: str) -> bool:
        return "No such container" in stderr or "No such object" in stderr


class MockImageParser(ImageParser):
    def parse_inspect(self, raw: str) -> ImageInfo:
        return ImageInfo(id="sha256:abc")
    def parse_list(self, raw: str) -> list[ImageInfo]:
        return [ImageInfo(id="sha256:abc")]
    def parse_build_output(self, raw: str) -> str:
        return "sha256:abc"
    def parse_id_from_pull(self, raw: str) -> str:
        return "sha256:abc"
    def parse_prune(self, raw: str) -> PruneResult:
        return PruneResult()
    def is_not_found_error(self, stderr: str) -> bool:
        return "No such image" in stderr or "pull access denied" in stderr


class MockVolumeParser(VolumeParser):
    def parse_inspect(self, raw: str) -> VolumeInfo:
        return VolumeInfo(name="my-vol", driver="local")
    def parse_list(self, raw: str) -> list[VolumeInfo]:
        return [VolumeInfo(name="my-vol", driver="local")]
    def parse_prune(self, raw: str) -> PruneResult:
        return PruneResult()
    def is_not_found_error(self, stderr: str) -> bool:
        return "No such volume" in stderr


class MockNetworkParser(NetworkParser):
    def parse_inspect(self, raw: str) -> NetworkInfo:
        return NetworkInfo(id="n1", name="net1", driver="bridge", scope="local")
    def parse_list(self, raw: str) -> list[NetworkInfo]:
        return [NetworkInfo(id="n1", name="net1", driver="bridge", scope="local")]
    def parse_prune(self, raw: str) -> PruneResult:
        return PruneResult()
    def is_not_found_error(self, stderr: str) -> bool:
        return "No such network" in stderr
