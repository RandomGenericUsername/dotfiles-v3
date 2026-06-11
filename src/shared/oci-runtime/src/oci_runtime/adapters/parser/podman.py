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


class PodmanContainerParser(BaseCliParser, ContainerParser):
    _not_found_patterns = ("no such container",)

    def _parse_ports(self, network_settings: dict) -> list[PortMapping]:
        ports = []
        ports_dict = network_settings.get("Ports", {})
        
        if not isinstance(ports_dict, dict):
            return ports
        
        for port_spec, mappings in ports_dict.items():
            try:
                container_port, protocol = port_spec.split("/")
                container_port = int(container_port)
                
                if isinstance(mappings, list):
                    for mapping in mappings:
                        if isinstance(mapping, dict):
                            host_port = mapping.get("HostPort")
                            host_ip = mapping.get("HostIp", "127.0.0.1")
                            
                            if host_port:
                                ports.append(PortMapping(
                                    container_port=container_port,
                                    host_port=int(host_port),
                                    protocol=protocol,
                                    host_ip=host_ip,
                                ))
            except (ValueError, AttributeError):
                continue
        
        return ports
    
    def parse_inspect(self, raw: str) -> ContainerInfo:
        item = self._parse_json_item(raw)
        network_settings = item.get("NetworkSettings", {})
        ports = self._parse_ports(network_settings)
        return ContainerInfo(
            id=item.get("Id", ""),
            name=item.get("Name", "").lstrip("/"),
            image=item.get("Config", {}).get("Image", ""),
            state=ContainerState(item.get("State", {}).get("Status", ContainerState.CREATED)),
            status=item.get("State", {}).get("Status", ""),
            created=item.get("Created"),
            ports=ports,
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
                ports=[],
                labels=item.get("Labels", {}),
            ))
        return result


class PodmanImageParser(BaseCliParser, ImageParser):
    _not_found_patterns = ("image not found",)

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
        lines = raw.strip().split('\n')
        if lines:
            for line in reversed(lines):
                line = line.strip()
                if line and not line.startswith('Trying') and not line.startswith('Getting'):
                    if 'sha256:' in line:
                        match = re.search(r"sha256:([a-f0-9]+)", line)
                        if match:
                            return f"sha256:{match.group(1)}"
                    if line and not line.startswith('Error') and not line.startswith('Warning'):
                        return line
        return ""


class PodmanVolumeParser(BaseCliParser, VolumeParser):
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


class PodmanNetworkParser(BaseCliParser, NetworkParser):
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
