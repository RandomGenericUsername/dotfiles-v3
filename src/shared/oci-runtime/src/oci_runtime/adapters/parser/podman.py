import re

from oci_runtime.adapters.parser.base import BaseCliParser, _coerce_size, _safe_int
from oci_runtime.ports.parsers import ParsingError
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

                if mappings is None:
                    ports.append(
                        PortMapping(
                            container_port=container_port,
                            protocol=protocol,
                            host_ip=None,
                        )
                    )
                elif isinstance(mappings, list):
                    for mapping in mappings:
                        if isinstance(mapping, dict):
                            host_port = mapping.get("HostPort")
                            host_ip = mapping.get("HostIp", "") or "0.0.0.0"

                            if host_port:
                                ports.append(
                                    PortMapping(
                                        container_port=container_port,
                                        host_port=int(host_port),
                                        protocol=protocol,
                                        host_ip=host_ip,
                                    )
                                )
            except (ValueError, AttributeError):
                continue

        return ports

    @staticmethod
    def _parse_ports_from_list(item: dict) -> list[PortMapping]:
        """Parse the Ports array from `podman ps --format json` output.

        The list format has a different structure than inspect:
          [{"HostPort": 8080, "ContainerPort": 80, "Protocol": "tcp", "HostIp": "0.0.0.0"}, ...]
        """
        ports = []
        for p in item.get("Ports") or []:
            if not isinstance(p, dict):
                continue
            host_port = p.get("HostPort")
            container_port = p.get("ContainerPort")
            protocol = p.get("Protocol", "tcp")
            host_ip = p.get("HostIp", "") or "0.0.0.0"
            cport = _safe_int(container_port)
            if cport is None:
                continue
            ports.append(
                PortMapping(
                    container_port=cport,
                    host_port=_safe_int(host_port),
                    protocol=protocol,
                    host_ip=host_ip,
                )
            )
        return ports

    def parse_inspect(self, raw: str) -> ContainerInfo:
        item = self._parse_json_item(raw)
        network_settings = item.get("NetworkSettings", {})
        ports = self._parse_ports(network_settings)
        return ContainerInfo(
            id=item.get("Id", ""),
            name=item.get("Name", "").lstrip("/"),
            image=item.get("Config", {}).get("Image", ""),
            state=ContainerState(
                item.get("State", {}).get("Status", ContainerState.CREATED)
            ),
            status=item.get("State", {}).get("Status", ""),
            created=item.get("Created"),
            ports=ports,
            labels=item.get("Config", {}).get("Labels") or {},
            exit_code=item.get("State", {}).get("ExitCode"),
        )

    def parse_list(self, raw: str) -> list[ContainerInfo]:
        data = self._parse_json_list(raw)
        result = []
        for item in data:
            names = item.get("Names")
            if isinstance(names, str):
                names = [names]
            if not names or not isinstance(names, list):
                raise ParsingError(
                    raw=raw, message="Container list entry missing 'Names' field"
                )
            result.append(
                ContainerInfo(
                    id=item.get("Id", ""),
                    name=names[0].lstrip("/"),
                    image=item.get("Image", ""),
                    state=ContainerState(item.get("State", ContainerState.CREATED)),
                    status=item.get("Status", ""),
                    created=str(item.get("Created", "")),
                    ports=self._parse_ports_from_list(item),
                    labels=item.get("Labels") or {},
                )
            )
        return result


class PodmanImageParser(BaseCliParser, ImageParser):
    _not_found_patterns = ("image not found",)
    _auth_error_patterns = (
        "authentication required",
        "requested access to the resource is denied",
    )

    def parse_inspect(self, raw: str) -> ImageInfo:
        item = self._parse_json_item(raw)
        return ImageInfo(
            id=item.get("Id", ""),
            tags=(item.get("RepoTags") or []),
            size=item.get("Size", 0),
            created=item.get("Created"),
            labels=item.get("Labels") or {},
        )

    def parse_list(self, raw: str) -> list[ImageInfo]:
        data = self._parse_json_list(raw)
        result = []
        for item in data:
            tags = item.get("RepoTags", [])
            if not tags:
                names = item.get("Names", [])
                if names:
                    tags = names
            labels = item.get("Labels", {})
            if isinstance(labels, str):
                labels = {}
            result.append(
                ImageInfo(
                    id=item.get("Id", ""),
                    tags=tags if tags else [],
                    size=_coerce_size(item.get("Size", 0)),
                    created=str(item.get("Created", "")),
                    labels=labels,
                )
            )
        return result

    def parse_build_output(self, raw: str) -> str:
        output = raw.strip()
        if not output.startswith("sha256:"):
            output = f"sha256:{output}"
        if not re.match(r"^sha256:[a-f0-9]{12,64}$", output):
            raise ParsingError(raw=raw, message=f"Invalid build output: {raw!r}")
        return output

    def parse_digest_from_pull(self, raw: str) -> str:
        lines = raw.strip().split("\n")
        noise_prefixes = (
            "Resolved",
            "Trying",
            "Getting",
            "Copying",
            "Writing",
            "Storing",
        )
        for line in reversed(lines):
            cleaned = line.strip()
            if not cleaned:
                continue
            if cleaned.startswith(noise_prefixes):
                continue
            if cleaned.startswith("Error") or cleaned.startswith("Warning"):
                continue
            if "sha256:" in cleaned:
                match = re.search(r"sha256:([a-f0-9]+)", cleaned)
                if match:
                    return f"sha256:{match.group(1)}"
            if re.match(r"^[a-f0-9]{12,64}$", cleaned):
                return f"sha256:{cleaned}"
        return ""


class PodmanVolumeParser(BaseCliParser, VolumeParser):
    _not_found_patterns = ("no such volume",)

    def parse_inspect(self, raw: str) -> VolumeInfo:
        item = self._parse_json_item(raw)
        return VolumeInfo(
            name=item.get("Name", ""),
            driver=item.get("Driver", ""),
            mountpoint=item.get("Mountpoint"),
            labels=item.get("Labels") or {},
        )

    def parse_list(self, raw: str) -> list[VolumeInfo]:
        data = self._parse_json_list(raw)
        result = []
        for item in data:
            labels = item.get("Labels", {})
            if isinstance(labels, str):
                labels = {}
            result.append(
                VolumeInfo(
                    name=item.get("Name", ""),
                    driver=item.get("Driver", ""),
                    mountpoint=item.get("Mountpoint"),
                    labels=labels,
                )
            )
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
            labels=item.get("Labels") or {},
        )

    def parse_list(self, raw: str) -> list[NetworkInfo]:
        data = self._parse_json_list(raw)
        result = []
        for item in data:
            net_id = item.get("Id") or item.get("id", "")
            name = item.get("Name") or item.get("name", "")
            driver = item.get("Driver") or item.get("driver", "")
            scope = item.get("Scope") or item.get("scope", "")
            labels = item.get("Labels", {})
            if isinstance(labels, str):
                labels = {}
            result.append(
                NetworkInfo(
                    id=net_id,
                    name=name,
                    driver=driver,
                    scope=scope,
                    labels=labels,
                )
            )
        return result
