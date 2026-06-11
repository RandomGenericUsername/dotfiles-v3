import re

from oci_runtime.adapters.parser.base import BaseCliParser
from oci_runtime.domain.enums import ContainerState
from oci_runtime.domain.types import (
    ContainerInfo,
    ImageInfo,
    NetworkInfo,
    PortMapping,
    VolumeInfo,
)
from oci_runtime.ports.parsers import (
    ContainerParser,
    ImageParser,
    NetworkParser,
    VolumeParser,
)


class DockerContainerParser(BaseCliParser, ContainerParser):
    _not_found_patterns = ("no such container", "no such object")

    def parse_inspect(self, raw: str) -> ContainerInfo:
        item = self._parse_json_item(raw)
        return ContainerInfo(
            id=item.get("Id", ""),
            name=item.get("Name", "").lstrip("/"),
            image=item.get("Config", {}).get("Image", ""),
            state=ContainerState(item.get("State", {}).get("Status", ContainerState.CREATED)),
            status=item.get("State", {}).get("Status", ""),
            created=item.get("Created"),
            ports=_parse_docker_ports(item),
            labels=item.get("Config", {}).get("Labels", {}),
            exit_code=item.get("State", {}).get("ExitCode"),
        )

    def parse_list(self, raw: str) -> list[ContainerInfo]:
        data = self._parse_json_list(raw)
        result = []
        for item in data:
            result.append(ContainerInfo(
                id=item.get("Id", ""),
                name=(item.get("Names") or ["/"])[0].lstrip("/"),
                image=item.get("Image", ""),
                state=ContainerState(item.get("State", ContainerState.CREATED)),
                status=item.get("Status", ""),
                created=str(item.get("Created", "")),
                ports=_parse_docker_ports_from_list(item),
                labels=item.get("Labels", {}),
            ))
        return result


class DockerImageParser(BaseCliParser, ImageParser):
    _not_found_patterns = ("no such image", "pull access denied")

    def parse_inspect(self, raw: str) -> ImageInfo:
        item = self._parse_json_item(raw)
        return ImageInfo(
            id=item.get("Id", ""),
            tags=item.get("RepoTags", []),
            size=item.get("Size", 0),
            created=item.get("Created"),
            labels=item.get("Labels", {}),
        )

    def parse_list(self, raw: str) -> list[ImageInfo]:
        data = self._parse_json_list(raw)
        result = []
        for item in data:
            result.append(ImageInfo(
                id=item.get("Id", ""),
                tags=item.get("RepoTags", []),
                size=item.get("Size", 0),
                created=str(item.get("Created", "")),
                labels=item.get("Labels", {}),
            ))
        return result

    def parse_build_output(self, raw: str) -> str:
        output = raw.strip()
        if output.startswith("sha256:"):
            return output
        return f"sha256:{output}"

    def parse_id_from_pull(self, raw: str) -> str:
        """Extract image ID or name from pull output."""
        match = re.search(r"Digest: sha256:([a-f0-9]+)", raw)
        if match:
            return f"sha256:{match.group(1)}"
        lines = raw.strip().split('\n')
        if lines:
            for line in reversed(lines):
                if 'sha256' in line:
                    match = re.search(r"sha256:([a-f0-9]+)", line)
                    if match:
                        return f"sha256:{match.group(1)}"
        return ""


class DockerVolumeParser(BaseCliParser, VolumeParser):
    _not_found_patterns = ("no such volume",)

    def parse_inspect(self, raw: str) -> VolumeInfo:
        item = self._parse_json_item(raw)
        return VolumeInfo(
            name=item.get("Name", ""),
            driver=item.get("Driver", ""),
            mountpoint=item.get("Mountpoint"),
            labels=item.get("Labels", {}),
        )

    def parse_list(self, raw: str) -> list[VolumeInfo]:
        data = self._parse_json_list(raw)
        result = []
        for item in data:
            result.append(VolumeInfo(
                name=item.get("Name", ""),
                driver=item.get("Driver", ""),
                mountpoint=item.get("Mountpoint"),
                labels=item.get("Labels", {}),
            ))
        return result


class DockerNetworkParser(BaseCliParser, NetworkParser):
    _not_found_patterns = ("no such network",)

    def parse_inspect(self, raw: str) -> NetworkInfo:
        item = self._parse_json_item(raw)
        return NetworkInfo(
            id=item.get("Id", ""),
            name=item.get("Name", ""),
            driver=item.get("Driver", ""),
            scope=item.get("Scope", ""),
            labels=item.get("Labels", {}),
        )

    def parse_list(self, raw: str) -> list[NetworkInfo]:
        data = self._parse_json_list(raw)
        result = []
        for item in data:
            result.append(NetworkInfo(
                id=item.get("Id", ""),
                name=item.get("Name", ""),
                driver=item.get("Driver", ""),
                scope=item.get("Scope", ""),
                labels=item.get("Labels", {}),
            ))
        return result


def _parse_docker_ports(item: dict) -> list[PortMapping]:
    ports = []
    net_settings = item.get("NetworkSettings", {})
    port_map = net_settings.get("Ports", {}) or {}
    for key, bindings in port_map.items():
        try:
            container_port_str, protocol = key.split("/")
            container_port = int(container_port_str)
        except (ValueError, AttributeError):
            continue
        if bindings:
            for binding in bindings:
                host_port = int(binding["HostPort"]) if binding.get("HostPort") else None
                ports.append(PortMapping(
                    container_port=container_port,
                    host_port=host_port,
                    protocol=protocol,
                    host_ip=binding.get("HostIp", "127.0.0.1"),
                ))
        else:
            ports.append(PortMapping(
                container_port=container_port,
                protocol=protocol,
            ))
    return ports


def _parse_docker_ports_from_list(item: dict) -> list[PortMapping]:
    ports = []
    for p in item.get("Ports", []):
        ports.append(PortMapping(
            container_port=p.get("PrivatePort", 0),
            host_port=p.get("PublicPort"),
            protocol=p.get("Type", "tcp"),
            host_ip=p.get("HostIp", "127.0.0.1"),
        ))
    return ports
