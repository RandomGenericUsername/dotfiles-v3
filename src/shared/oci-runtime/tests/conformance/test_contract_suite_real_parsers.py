from __future__ import annotations

from pathlib import Path

import pytest

from oci_runtime.adapters.parser.docker import (
    DockerContainerParser,
    DockerImageParser,
    DockerNetworkParser,
    DockerVolumeParser,
)
from oci_runtime.adapters.parser.podman import (
    PodmanContainerParser,
    PodmanImageParser,
    PodmanNetworkParser,
    PodmanVolumeParser,
)
from oci_runtime.domain.types import (
    ContainerInfo,
    ImageInfo,
    NetworkInfo,
    VolumeInfo,
)

_FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(runtime: str, name: str) -> str:
    p = _FIXTURES / runtime / name
    if not p.exists():
        pytest.skip(f"fixture {runtime}/{name} not captured")
    return p.read_text(encoding="utf-8")


class ContractSuite:
    """Aggregate of contracts for a single parser family."""

    def __init__(
        self,
        *,
        container_parser,
        image_parser,
        volume_parser,
        network_parser,
        runtime: str,
    ):
        self._container = container_parser
        self._image = image_parser
        self._volume = volume_parser
        self._network = network_parser
        self._runtime = runtime

    def run_all(self) -> None:
        r = self._runtime

        raw = _fixture(r, "container_list.ndjson")
        result = self._container.parse_list(raw)
        assert isinstance(result, list)
        assert len(result) > 0

        raw = _fixture(r, "container_inspect.json")
        result = self._container.parse_inspect(raw)
        assert isinstance(result, ContainerInfo)

        raw = _fixture(r, "image_list.ndjson")
        result = self._image.parse_list(raw)
        assert isinstance(result, list)
        assert len(result) > 0

        raw = _fixture(r, "image_inspect_alpine.json")
        result = self._image.parse_inspect(raw)
        assert isinstance(result, ImageInfo)

        raw = _fixture(r, "volume_list.ndjson")
        result = self._volume.parse_list(raw)
        assert isinstance(result, list)
        assert len(result) > 0

        raw = _fixture(r, "volume_inspect.json")
        result = self._volume.parse_inspect(raw)
        assert isinstance(result, VolumeInfo)

        raw = _fixture(r, "network_list.ndjson")
        result = self._network.parse_list(raw)
        assert isinstance(result, list)
        assert len(result) > 0

        net_inspect = "network_inspect_bridge.json"
        r_net = r
        if r == "podman":
            net_inspect = "network_inspect_podman.json"
        raw = _fixture(r_net, net_inspect)
        result = self._network.parse_inspect(raw)
        assert isinstance(result, NetworkInfo)


@pytest.mark.slow
class TestDockerContractSuite:
    def test_full_suite(self):
        suite = ContractSuite(
            container_parser=DockerContainerParser(),
            image_parser=DockerImageParser(),
            volume_parser=DockerVolumeParser(),
            network_parser=DockerNetworkParser(),
            runtime="docker",
        )
        suite.run_all()


@pytest.mark.slow
class TestPodmanContractSuite:
    def test_full_suite_podman(self):
        suite = ContractSuite(
            container_parser=PodmanContainerParser(),
            image_parser=PodmanImageParser(),
            volume_parser=PodmanVolumeParser(),
            network_parser=PodmanNetworkParser(),
            runtime="podman",
        )
        suite.run_all()
