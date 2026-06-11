import json
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
    def parse_inspect(self, raw: str) -> ContainerInfo | None:
        try:
            data = json.loads(raw)
            if not data:
                return None
            item = data[0] if isinstance(data, list) else data
        except (json.JSONDecodeError, IndexError, KeyError):
            return None

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
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            data = [data]
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

    def is_not_found_error(self, stderr: str) -> bool:
        lower = stderr.lower()
        return "no such container" in lower or "no such object" in lower


class DockerImageParser(BaseCliParser, ImageParser):
    def parse_inspect(self, raw: str) -> ImageInfo | None:
        try:
            data = json.loads(raw)
            if not data:
                return None
            item = data[0] if isinstance(data, list) else data
        except (json.JSONDecodeError, IndexError, KeyError):
            return None

        return ImageInfo(
            id=item.get("Id", ""),
            tags=item.get("RepoTags", []),
            size=item.get("Size", 0),
            created=item.get("Created"),
            labels=item.get("Labels", {}),
        )

    def parse_list(self, raw: str) -> list[ImageInfo]:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            data = [data]
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
        return raw.strip().removeprefix("sha256:")

    def parse_id_from_pull(self, raw: str) -> str:
        """Extract image ID or name from pull output."""
        # Docker pull output ends with "Digest: sha256:..." or "Status: Downloaded newer image"
        # Look for the digest line which contains the image ID
        match = re.search(r"Digest: sha256:([a-f0-9]+)", raw)
        if match:
            return f"sha256:{match.group(1)}"
        # If no digest found, try to extract from status messages
        # Sometimes the output ends with the image name
        lines = raw.strip().split('\n')
        if lines:
            for line in reversed(lines):
                # Look for lines that might contain image info
                if 'sha256' in line:
                    match = re.search(r"sha256:([a-f0-9]+)", line)
                    if match:
                        return f"sha256:{match.group(1)}"
        return ""

    def is_not_found_error(self, stderr: str) -> bool:
        lower = stderr.lower()
        return "no such image" in lower or "pull access denied" in lower


class DockerVolumeParser(BaseCliParser, VolumeParser):
    def parse_inspect(self, raw: str) -> VolumeInfo | None:
        try:
            data = json.loads(raw)
            if not data:
                return None
            item = data[0] if isinstance(data, list) else data
        except (json.JSONDecodeError, IndexError, KeyError):
            return None

        return VolumeInfo(
            name=item.get("Name", ""),
            driver=item.get("Driver", ""),
            mountpoint=item.get("Mountpoint"),
            labels=item.get("Labels", {}),
        )

    def parse_list(self, raw: str) -> list[VolumeInfo]:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            data = [data]
        result = []
        for item in data:
            result.append(VolumeInfo(
                name=item.get("Name", ""),
                driver=item.get("Driver", ""),
                mountpoint=item.get("Mountpoint"),
                labels=item.get("Labels", {}),
            ))
        return result

    def is_not_found_error(self, stderr: str) -> bool:
        return "no such volume" in stderr.lower()


class DockerNetworkParser(BaseCliParser, NetworkParser):
    def parse_inspect(self, raw: str) -> NetworkInfo | None:
        try:
            data = json.loads(raw)
            if not data:
                return None
            item = data[0] if isinstance(data, list) else data
        except (json.JSONDecodeError, IndexError, KeyError):
            return None

        return NetworkInfo(
            id=item.get("Id", ""),
            name=item.get("Name", ""),
            driver=item.get("Driver", ""),
            scope=item.get("Scope", ""),
            labels=item.get("Labels", {}),
        )

    def parse_list(self, raw: str) -> list[NetworkInfo]:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            data = [data]
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

    def is_not_found_error(self, stderr: str) -> bool:
        return "no such network" in stderr.lower()


def _parse_docker_ports(item: dict) -> list[PortMapping]:
    ports = []
    net_settings = item.get("NetworkSettings", {})
    port_map = net_settings.get("Ports", {}) or {}
    for key, bindings in port_map.items():
        container_port_str, protocol = key.split("/")
        container_port = int(container_port_str)
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
