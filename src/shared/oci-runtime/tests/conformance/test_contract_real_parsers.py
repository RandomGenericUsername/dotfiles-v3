from __future__ import annotations

from pathlib import Path

import pytest

from oci_runtime.adapters.parser.docker import DockerContainerParser
from oci_runtime.adapters.parser.podman import PodmanContainerParser
from oci_runtime.domain.types import ContainerInfo

_FIXTURES = Path(__file__).parent / "fixtures"


class ContainerListContract:
    """Contract: a container list parser must produce valid ContainerInfo objects from real CLI output."""

    def __init__(
        self, parser, runtime: str, fixture_name: str = "container_list.ndjson"
    ):
        self._parser = parser
        self._runtime = runtime
        self._fixture_name = fixture_name

    def assert_passes(self) -> None:
        fixture_path = _FIXTURES / self._runtime / self._fixture_name
        if not fixture_path.exists():
            pytest.skip(f"fixture {self._runtime}/{self._fixture_name} not captured")
        raw = fixture_path.read_text(encoding="utf-8")
        result = self._parser(raw)
        assert isinstance(result, list), "parse_list must return a list"
        assert len(result) > 0, "fixture must contain at least one container"
        for item in result:
            assert isinstance(item, ContainerInfo)
            assert item.name, "ContainerInfo.name must be non-empty"
            assert item.image, "ContainerInfo.image must be non-empty"
            assert isinstance(item.state, str)


@pytest.mark.slow
class TestContainerListContractDocker:
    def test_container_list_contract_docker(self):
        contract = ContainerListContract(
            parser=DockerContainerParser().parse_list,
            runtime="docker",
        )
        contract.assert_passes()


@pytest.mark.slow
class TestContainerListContractPodman:
    def test_container_list_contract_podman(self):
        contract = ContainerListContract(
            parser=PodmanContainerParser().parse_list,
            runtime="podman",
        )
        contract.assert_passes()


@pytest.mark.slow
class TestContainerListContractLima:
    def test_container_list_contract_lima(self):
        pytest.skip("Lima parser not yet implemented")
