import re

from oci_runtime.domain.json_parsing import parse_json_item, parse_json_list
from oci_runtime.domain.error_matching import matches_any_pattern
from oci_runtime.domain.prune_parsing import parse_prune_result
from oci_runtime.domain.size_parsing import coerce_size
from oci_runtime.domain.exceptions import ParsingError
from oci_runtime.domain.enums import ContainerState
from oci_runtime.domain.types import (
    ContainerInfo,
    ImageInfo,
    NetworkInfo,
    PortMapping,
    PruneResult,
    VolumeInfo,
)
from oci_runtime.ports.parsers import (
    ContainerParser,
    ImageParser,
    NetworkParser,
    VolumeParser,
)


class DockerContainerParser(ContainerParser):
    _not_found_patterns = ("no such container", "no such object")

    def parse_inspect(self, raw: str) -> ContainerInfo:
        item = parse_json_item(raw)
        return ContainerInfo(
            id=item.get("Id", ""),
            name=item.get("Name", "").lstrip("/"),
            image=item.get("Config", {}).get("Image", ""),
            state=ContainerState(
                item.get("State", {}).get("Status", ContainerState.CREATED)
            ),
            status=item.get("State", {}).get("Status", ""),
            created=item.get("Created"),
            ports=_parse_docker_ports(item),
            labels=item.get("Config", {}).get("Labels") or {},
            exit_code=item.get("State", {}).get("ExitCode"),
        )

    def parse_list(self, raw: str) -> list[ContainerInfo]:
        data = parse_json_list(raw)
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
                    ports=_parse_docker_ports_from_list(item),
                    labels=item.get("Labels") or {},
                )
            )
        return result

    def parse_prune(self, raw: str) -> PruneResult:
        return parse_prune_result(raw)

    def is_not_found_error(self, stderr: str) -> bool:
        return matches_any_pattern(stderr, self._not_found_patterns)


class DockerImageParser(ImageParser):
    _not_found_patterns = ("no such image",)
    _auth_error_patterns = (
        "pull access denied",
        "unauthorized",
        "authentication required",
    )

    def parse_inspect(self, raw: str) -> ImageInfo:
        item = parse_json_item(raw)
        return ImageInfo(
            id=item.get("Id", ""),
            tags=(item.get("RepoTags") or []),
            size=item.get("Size", 0),
            created=item.get("Created"),
            labels=item.get("Labels") or {},
        )

    def parse_list(self, raw: str) -> list[ImageInfo]:
        data = parse_json_list(raw)
        result = []
        for item in data:
            image_id = item.get("Id") or item.get("ID") or item.get("id", "")
            tags = item.get("RepoTags", [])
            if not tags:
                repo = item.get("Repository", "")
                tag = item.get("Tag", "")
                if repo and repo != "<none>":
                    tags = (
                        [f"{repo}:{tag}"]
                        if tag and tag != "<none>"
                        else [f"{repo}:latest"]
                    )
            size = coerce_size(item.get("Size", 0))
            if not size:
                size = coerce_size(item.get("VirtualSize", 0))
            labels = item.get("Labels", {})
            if isinstance(labels, str):
                labels = {}
            result.append(
                ImageInfo(
                    id=image_id,
                    tags=tags if tags else [],
                    size=size if isinstance(size, int) else 0,
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
        match = re.search(r"Digest: sha256:([a-f0-9]+)", raw)
        if match:
            return f"sha256:{match.group(1)}"
        lines = raw.strip().split("\n")
        if lines:
            for line in reversed(lines):
                if "sha256" in line:
                    match = re.search(r"sha256:([a-f0-9]+)", line)
                    if match:
                        return f"sha256:{match.group(1)}"
        return ""

    def parse_prune(self, raw: str) -> PruneResult:
        return parse_prune_result(raw)

    def is_not_found_error(self, stderr: str) -> bool:
        return matches_any_pattern(stderr, self._not_found_patterns)

    def is_auth_error(self, stderr: str) -> bool:
        return matches_any_pattern(stderr, self._auth_error_patterns)


class DockerVolumeParser(VolumeParser):
    _not_found_patterns = ("no such volume",)

    def parse_inspect(self, raw: str) -> VolumeInfo:
        item = parse_json_item(raw)
        return VolumeInfo(
            name=item.get("Name", ""),
            driver=item.get("Driver", ""),
            mountpoint=item.get("Mountpoint"),
            labels=item.get("Labels") or {},
        )

    def parse_list(self, raw: str) -> list[VolumeInfo]:
        data = parse_json_list(raw)
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

    def parse_prune(self, raw: str) -> PruneResult:
        return parse_prune_result(raw)

    def is_not_found_error(self, stderr: str) -> bool:
        return matches_any_pattern(stderr, self._not_found_patterns)


class DockerNetworkParser(NetworkParser):
    _not_found_patterns = ("no such network",)

    def parse_inspect(self, raw: str) -> NetworkInfo:
        item = parse_json_item(raw)
        return NetworkInfo(
            id=item.get("Id", ""),
            name=item.get("Name", ""),
            driver=item.get("Driver", ""),
            scope=item.get("Scope", ""),
            labels=item.get("Labels") or {},
        )

    def parse_list(self, raw: str) -> list[NetworkInfo]:
        data = parse_json_list(raw)
        result = []
        for item in data:
            net_id = item.get("Id") or item.get("ID") or item.get("id", "")
            labels = item.get("Labels", {})
            if isinstance(labels, str):
                labels = {}
            result.append(
                NetworkInfo(
                    id=net_id,
                    name=item.get("Name", ""),
                    driver=item.get("Driver", ""),
                    scope=item.get("Scope", ""),
                    labels=labels,
                )
            )
        return result

    def parse_prune(self, raw: str) -> PruneResult:
        return parse_prune_result(raw)

    def is_not_found_error(self, stderr: str) -> bool:
        return matches_any_pattern(stderr, self._not_found_patterns)


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
                host_port = (
                    int(binding["HostPort"]) if binding.get("HostPort") else None
                )
                host_ip = binding.get("HostIp") or None
                ports.append(
                    PortMapping(
                        container_port=container_port,
                        host_port=host_port,
                        protocol=protocol,
                        host_ip=host_ip,
                    )
                )
        else:
            ports.append(
                PortMapping(
                    container_port=container_port,
                    protocol=protocol,
                    host_ip=None,
                )
            )
    return ports


def _parse_docker_ports_from_list(item: dict) -> list[PortMapping]:
    ports = []
    for p in item.get("Ports", []):
        cport = p.get("PrivatePort")
        if cport is None:
            continue
        host_ip = p.get("HostIp") or None
        ports.append(
            PortMapping(
                container_port=cport,
                host_port=p.get("PublicPort"),
                protocol=p.get("Type", "tcp"),
                host_ip=host_ip,
            )
        )
    return ports
