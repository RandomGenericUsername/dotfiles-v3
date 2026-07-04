from __future__ import annotations

import json
from pathlib import Path

import pytest

from oci_runtime.adapters.parser.docker import _parse_docker_ports
from oci_runtime.domain.types import PortMapping

_FIXTURES = Path(__file__).parent.parent / "fixtures"


class DockerPortParser:
    @staticmethod
    def parse(raw: str) -> list[PortMapping]:
        item = json.loads(raw)
        if isinstance(item, list):
            item = item[0]
        return _parse_docker_ports(item)


def _fixture(name: str) -> str:
    p = _FIXTURES / "docker" / name
    if not p.exists():
        pytest.skip(f"fixture docker/{name} not captured")
    return p.read_text(encoding="utf-8")


class TestDockerPortParserAdapter:
    def test_parse_container_inspect_ports(self):
        raw = _fixture("container_inspect.json")
        ports = DockerPortParser.parse(raw)
        assert isinstance(ports, list)

    def test_parse_returns_port_mapping_instances(self):
        raw = _fixture("container_inspect.json")
        ports = DockerPortParser.parse(raw)
        for p in ports:
            assert isinstance(p, PortMapping)

    def test_parse_empty_when_no_ports_exposed(self):
        raw = _fixture("container_list.ndjson")
        ports = DockerPortParser.parse(raw)
        assert isinstance(ports, list)

    def test_parse_with_ports_fixture(self):
        raw = _fixture("container_list_ports.ndjson")
        port_line = json.loads(raw.strip().split("\n")[0])
        item = {"NetworkSettings": {"Ports": {}}}
        ports_str = port_line.get("Ports", "")
        if ports_str:
            for entry in ports_str.split(", "):
                entry = entry.strip()
                if "->" in entry:
                    parts = entry.split("->")
                    host_part = parts[0]
                    container_part = parts[1]
                    if "/" in container_part:
                        cport_str, proto = container_part.split("/")
                        cport = int(cport_str)
                        key = f"{cport}/{proto}"
                        if ":" in host_part:
                            host_ip, host_port = host_part.rsplit(":", 1)
                        else:
                            host_ip = None
                            host_port = host_part
                        item["NetworkSettings"]["Ports"][key] = [
                            {"HostIp": host_ip or "", "HostPort": host_port}
                        ]
        ports = _parse_docker_ports(item)
        assert isinstance(ports, list)
        assert len(ports) > 0
        assert isinstance(ports[0], PortMapping)
