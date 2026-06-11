import sys
from dataclasses import dataclass, field
from pathlib import Path

from oci_runtime.domain.enums import ContainerState, NetworkMode, RestartPolicy


@dataclass
class VolumeMount:
    source: str | Path
    target: str | Path
    type: str
    read_only: bool = False


@dataclass
class PortMapping:
    container_port: int
    host_port: int | None = None
    protocol: str = "tcp"
    host_ip: str = "127.0.0.1"


@dataclass
class BuildContext:
    build_file_content: str | None = None
    build_file_path: Path | None = None
    context_path: Path | None = None
    files: dict[str, bytes] = field(default_factory=dict)
    build_args: dict[str, str] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    target: str | None = None
    network: str | None = None
    no_cache: bool = False
    pull: bool = False
    rm: bool = True
    build_contexts: dict[str, str | Path] = field(default_factory=dict)

    def __post_init__(self):
        has_content = self.build_file_content is not None
        has_path = self.build_file_path is not None
        if has_content and has_path:
            raise ValueError(
                "BuildContext: cannot set both build_file_content and "
                "build_file_path. Use build_file_content for inline "
                "Dockerfile text or build_file_path for a path."
            )
        if not has_content and not has_path:
            raise ValueError(
                "BuildContext: must set either build_file_content or "
                "build_file_path."
            )


@dataclass
class RunConfig:
    image: str
    name: str | None = None
    command: list[str] | None = None
    entrypoint: list[str] | None = None
    environment: dict[str, str] = field(default_factory=dict)
    volumes: list[VolumeMount] = field(default_factory=list)
    ports: list[PortMapping] = field(default_factory=list)
    network: str | NetworkMode = NetworkMode.BRIDGE
    restart_policy: str | RestartPolicy = RestartPolicy.NO
    detach: bool = True
    remove: bool = False
    stream_output: bool = False
    user: str | None = None
    working_dir: str | None = None
    hostname: str | None = None
    labels: dict[str, str] = field(default_factory=dict)
    log_driver: str | None = None
    privileged: bool = False
    read_only: bool = False
    memory_limit: str | None = None
    cpu_limit: str | None = None
    tty: bool = False
    stdin_open: bool = False
    auto_tty: bool = False
    runtime_flags: list[str] = field(default_factory=list)

    @property
    def effective_tty(self) -> bool:
        return self.tty or (self.auto_tty and sys.stdout.isatty())


@dataclass
class ImageInfo:
    id: str
    tags: list[str] = field(default_factory=list)
    size: int = 0
    created: str | None = None
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class ContainerInfo:
    id: str
    name: str
    image: str
    state: ContainerState
    status: str
    created: str | None = None
    ports: list[PortMapping] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)
    exit_code: int | None = None


@dataclass
class VolumeInfo:
    name: str
    driver: str
    mountpoint: str | None = None
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class ExecOutput:
    returncode: int
    stdout: str
    stderr: str


@dataclass
class NetworkInfo:
    id: str
    name: str
    driver: str
    scope: str
    labels: dict[str, str] = field(default_factory=dict)
