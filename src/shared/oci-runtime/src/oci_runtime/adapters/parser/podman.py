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


class PodmanContainerParser(BaseCliParser, ContainerParser):
    def _parse_ports(self, network_settings: dict) -> list[PortMapping]:
        """Parse Podman port mappings from NetworkSettings.Ports structure."""
        ports = []
        ports_dict = network_settings.get("Ports", {})
        
        if not isinstance(ports_dict, dict):
            return ports
        
        for port_spec, mappings in ports_dict.items():
            try:
                # port_spec is like "80/tcp" or "80/udp"
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
    
    def parse_inspect(self, raw: str) -> ContainerInfo | None:
        try:
            data = json.loads(raw)
            if not data:
                return None
            item = data[0] if isinstance(data, list) else data
        except (json.JSONDecodeError, IndexError, KeyError):
            return None

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
                ports=[],
                labels=item.get("Labels", {}),
            ))
        return result

    def is_not_found_error(self, stderr: str) -> bool:
        return "no such container" in stderr.lower()


class PodmanImageParser(BaseCliParser, ImageParser):
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
        # Podman pull output typically ends with the image name/ID
        # Look for lines with image digest or ID
        lines = raw.strip().split('\n')
        if lines:
            # Last non-empty line often contains the result
            for line in reversed(lines):
                line = line.strip()
                if line and not line.startswith('Trying') and not line.startswith('Getting'):
                    # Could be image digest, ID, or full image name
                    if 'sha256:' in line:
                        match = re.search(r"sha256:([a-f0-9]+)", line)
                        if match:
                            return f"sha256:{match.group(1)}"
                    # Return the last meaningful line if it contains image info
                    if line and not line.startswith('Error') and not line.startswith('Warning'):
                        return line
        return ""

    def is_not_found_error(self, stderr: str) -> bool:
        return "image not found" in stderr.lower()


class PodmanVolumeParser(BaseCliParser, VolumeParser):
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


class PodmanNetworkParser(BaseCliParser, NetworkParser):
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
