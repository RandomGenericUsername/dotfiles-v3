"""Conformance tests: parsers must round-trip REAL CLI output.

These tests load fixtures captured from live docker/podman daemons
(see ``tests/conformance/capture.py``) and assert the parsers produce
valid domain objects from them. This anchors the test suite to ground
truth — the actual JSON shapes the CLIs emit — rather than the
implementer's imagination of those shapes.

Fixtures are committed under ``tests/conformance/fixtures/``.
Refresh them with:  make capture-fixtures

These are conformance checks that assert parser behavior directly — every
parser must correctly convert real CLI output into valid domain objects.
A failing test always indicates a real parser bug that must be fixed.
"""

from __future__ import annotations

from collections.abc import Mapping
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

_PARSERS = {
    "docker": {
        "container": DockerContainerParser(),
        "image": DockerImageParser(),
        "volume": DockerVolumeParser(),
        "network": DockerNetworkParser(),
    },
    "podman": {
        "container": PodmanContainerParser(),
        "image": PodmanImageParser(),
        "volume": PodmanVolumeParser(),
        "network": PodmanNetworkParser(),
    },
}


def _fixture(runtime: str, name: str) -> str:
    p = _FIXTURES / runtime / name
    if not p.exists():
        pytest.skip(
            f"fixture {runtime}/{name} not captured (run make capture-fixtures)"
        )
    return p.read_text(encoding="utf-8")


def _has_fixture(runtime: str, name: str) -> bool:
    return (_FIXTURES / runtime / name).exists()


# ─── Image inspect ───


class TestImageInspectConformance:
    @pytest.mark.parametrize("runtime", ["docker", "podman"])
    def test_parse_inspect_produces_valid_image_info(self, runtime):
        raw = _fixture(runtime, "image_inspect_alpine.json")
        info = _PARSERS[runtime]["image"].parse_inspect(raw)
        assert isinstance(info, ImageInfo)
        assert info.id, "id must be non-empty"
        assert isinstance(info.size, int), (
            f"size must be int, got {type(info.size).__name__}"
        )
        assert info.size >= 0

    @pytest.mark.parametrize("runtime", ["docker", "podman"])
    def test_parse_inspect_tags_present(self, runtime):
        raw = _fixture(runtime, "image_inspect_alpine.json")
        info = _PARSERS[runtime]["image"].parse_inspect(raw)
        assert isinstance(info.tags, tuple)
        assert any("alpine" in t for t in info.tags), (
            f"expected alpine tag, got {info.tags}"
        )


# ─── Image list ───


class TestImageListConformance:
    @pytest.mark.parametrize("runtime", ["docker", "podman"])
    def test_parse_list_produces_list_of_image_info(self, runtime):
        raw = _fixture(runtime, "image_list.ndjson")
        result = _PARSERS[runtime]["image"].parse_list(raw)
        assert isinstance(result, list)
        assert len(result) > 0, "fixture has images; list must not be empty"
        assert all(isinstance(i, ImageInfo) for i in result)

    @pytest.mark.parametrize("runtime", ["docker", "podman"])
    def test_parse_list_sizes_are_int(self, runtime):
        raw = _fixture(runtime, "image_list.ndjson")
        result = _PARSERS[runtime]["image"].parse_list(raw)
        for img in result:
            assert isinstance(img.size, int), (
                f"size must be int, got {type(img.size).__name__}: {img.size!r}"
            )


# ─── Container inspect ───


class TestContainerInspectConformance:
    @pytest.mark.parametrize("runtime", ["docker", "podman"])
    def test_parse_inspect_produces_valid_container_info(self, runtime):
        raw = _fixture(runtime, "container_inspect.json")
        info = _PARSERS[runtime]["container"].parse_inspect(raw)
        assert isinstance(info, ContainerInfo)
        assert info.id, "id must be non-empty"
        assert info.name, "name must be non-empty"
        assert info.image, "image must be non-empty"

    @pytest.mark.parametrize("runtime", ["docker", "podman"])
    def test_parse_inspect_labels_is_dict(self, runtime):
        raw = _fixture(runtime, "container_inspect.json")
        info = _PARSERS[runtime]["container"].parse_inspect(raw)
        assert isinstance(info.labels, Mapping), (
            f"labels must be dict, got {type(info.labels).__name__}"
        )


# ─── Container list ───


class TestContainerListConformance:
    def test_docker_parse_list_produces_container_infos(self):
        raw = _fixture("docker", "container_list.ndjson")
        result = _PARSERS["docker"]["container"].parse_list(raw)
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(c, ContainerInfo) for c in result)

    def test_podman_parse_list_produces_container_infos(self):
        raw = _fixture("podman", "container_list.ndjson")
        result = _PARSERS["podman"]["container"].parse_list(raw)
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(c, ContainerInfo) for c in result)

    @pytest.mark.parametrize("runtime", ["docker", "podman"])
    def test_parse_list_labels_is_dict(self, runtime):
        """Labels must be a dict even when the CLI emits null/empty string."""
        raw = _fixture(runtime, "container_list.ndjson")
        result = _PARSERS[runtime]["container"].parse_list(raw)
        for c in result:
            assert isinstance(c.labels, Mapping), (
                f"labels must be dict, got {type(c.labels).__name__}: {c.labels!r}"
            )


# ─── Volume inspect ───


class TestVolumeInspectConformance:
    @pytest.mark.parametrize("runtime", ["docker", "podman"])
    def test_parse_inspect_produces_valid_volume_info(self, runtime):
        raw = _fixture(runtime, "volume_inspect.json")
        info = _PARSERS[runtime]["volume"].parse_inspect(raw)
        assert isinstance(info, VolumeInfo)
        assert info.name, "name must be non-empty"
        assert info.driver, "driver must be non-empty"

    @pytest.mark.parametrize("runtime", ["docker", "podman"])
    def test_parse_inspect_labels_is_dict(self, runtime):
        raw = _fixture(runtime, "volume_inspect.json")
        info = _PARSERS[runtime]["volume"].parse_inspect(raw)
        assert isinstance(info.labels, Mapping), (
            f"labels must be dict, got {type(info.labels).__name__}"
        )


# ─── Volume list ───


class TestVolumeListConformance:
    @pytest.mark.parametrize("runtime", ["docker", "podman"])
    def test_parse_list_produces_list_of_volume_info(self, runtime):
        raw = _fixture(runtime, "volume_list.ndjson")
        result = _PARSERS[runtime]["volume"].parse_list(raw)
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(v, VolumeInfo) for v in result)

    @pytest.mark.parametrize("runtime", ["docker", "podman"])
    def test_parse_list_labels_is_dict(self, runtime):
        raw = _fixture(runtime, "volume_list.ndjson")
        result = _PARSERS[runtime]["volume"].parse_list(raw)
        for v in result:
            assert isinstance(v.labels, Mapping), (
                f"labels must be dict, got {type(v.labels).__name__}"
            )


# ─── Network inspect ───


class TestNetworkInspectConformance:
    def test_docker_parse_inspect_produces_valid_network_info(self):
        raw = _fixture("docker", "network_inspect_bridge.json")
        info = _PARSERS["docker"]["network"].parse_inspect(raw)
        assert isinstance(info, NetworkInfo)
        assert info.name == "bridge"
        assert info.driver, "driver must be non-empty"

    @pytest.mark.skipif(
        not _has_fixture("podman", "network_inspect_bridge.json"),
        reason="podman network inspect fixture not captured",
    )
    def test_podman_parse_inspect_produces_valid_network_info(self):
        raw = _fixture("podman", "network_inspect_bridge.json")
        info = _PARSERS["podman"]["network"].parse_inspect(raw)
        assert isinstance(info, NetworkInfo)
        assert info.name == "bridge"


# ─── Network list ───


class TestNetworkListConformance:
    @pytest.mark.parametrize("runtime", ["docker", "podman"])
    def test_parse_list_produces_list_of_network_info(self, runtime):
        raw = _fixture(runtime, "network_list.ndjson")
        result = _PARSERS[runtime]["network"].parse_list(raw)
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(n, NetworkInfo) for n in result)

    @pytest.mark.parametrize("runtime", ["docker", "podman"])
    def test_parse_list_labels_is_dict(self, runtime):
        raw = _fixture(runtime, "network_list.ndjson")
        result = _PARSERS[runtime]["network"].parse_list(raw)
        for n in result:
            assert isinstance(n.labels, Mapping), (
                f"labels must be dict, got {type(n.labels).__name__}"
            )


# ─── Pull output ───


class TestPullIdConformance:
    @pytest.mark.parametrize("runtime", ["docker", "podman"])
    def test_parse_digest_from_pull_returns_sha256(self, runtime):
        raw = _fixture(runtime, "pull_alpine.txt")
        ident = _PARSERS[runtime]["image"].parse_digest_from_pull(raw)
        assert ident, "pull id must be non-empty (empty = silent failure)"
        assert ident.startswith("sha256:"), (
            f"pull id must be sha256-prefixed, got {ident!r}"
        )
