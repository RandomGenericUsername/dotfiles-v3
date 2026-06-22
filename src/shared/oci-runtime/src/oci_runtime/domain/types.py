from dataclasses import dataclass, field
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
import re

from oci_runtime.domain.enums import (
    ContainerState,
    NetworkMode,
    RestartPolicy,
    RuntimeKind,
    VolumeMountType,
)


def _freeze_mapping(self, field_names: list[str]) -> None:
    for name in field_names:
        value = getattr(self, name)
        if isinstance(value, dict):
            object.__setattr__(self, name, MappingProxyType(value))


def _freeze_sequence(self, field_names: list[str]) -> None:
    for name in field_names:
        value = getattr(self, name)
        if isinstance(value, list):
            object.__setattr__(self, name, tuple(value))


_MEMORY_LIMIT_RE = re.compile(r"^\d+(\.\d+)?[bkmg]?$", re.IGNORECASE)
_CPU_LIMIT_RE = re.compile(r"^\d+(\.\d+)?$")


@dataclass(frozen=True)
class VolumeMount:
    source: str | Path | None
    target: str | Path
    type: VolumeMountType = VolumeMountType.BIND
    read_only: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.type, VolumeMountType):
            raise TypeError(
                f"VolumeMount: type must be VolumeMountType, got "
                f"{type(self.type).__name__}: {self.type!r}"
            )
        if self.type is not VolumeMountType.TMPFS and self.source is None:
            raise ValueError("VolumeMount: source is required for non-TMPFS mounts")


@dataclass(frozen=True)
class PortMapping:
    container_port: int
    host_ip: str | None
    host_port: int | None = None
    protocol: str = "tcp"


@dataclass(frozen=True)
class BuildContext:
    build_file_content: str | None = None
    build_file_path: Path | None = None
    context_path: Path | None = None
    files: Mapping[str, bytes] = field(default_factory=dict)
    build_args: Mapping[str, str] = field(default_factory=dict)
    labels: Mapping[str, str] = field(default_factory=dict)
    target: str | None = None
    network: str | None = None
    no_cache: bool = False
    pull: bool = False
    rm: bool = True
    build_contexts: Mapping[str, str | Path] = field(default_factory=dict)

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
                "BuildContext: must set either build_file_content or build_file_path."
            )
        if self.context_path is not None and self.files:
            raise ValueError(
                "BuildContext: 'files' (in-memory) cannot be combined with 'context_path' "
                "(filesystem). docker build takes context from either stdin (tar) or a PATH, "
                "not both. Drop 'context_path' to send files via stdin tar, or drop 'files' "
                "to use the filesystem context at context_path."
            )
        _freeze_mapping(self, ["files", "build_args", "labels", "build_contexts"])


@dataclass(frozen=True)
class RunConfig:
    image: str
    name: str | None = None
    command: tuple[str, ...] | None = None
    entrypoint: str | None = None
    environment: Mapping[str, str] = field(default_factory=dict)
    volumes: tuple[VolumeMount, ...] = field(default_factory=tuple)
    ports: tuple[PortMapping, ...] = field(default_factory=tuple)
    network: NetworkMode = NetworkMode.BRIDGE
    network_container: str | None = None
    restart_policy: RestartPolicy = RestartPolicy.NO
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
    timeout: float | None = None
    runtime_flags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.memory_limit is not None and not _MEMORY_LIMIT_RE.match(
            self.memory_limit
        ):
            raise ValueError(f"Invalid memory_limit: {self.memory_limit!r}")
        if self.cpu_limit is not None and not _CPU_LIMIT_RE.match(self.cpu_limit):
            raise ValueError(f"Invalid cpu_limit: {self.cpu_limit!r}")
        if self.network == NetworkMode.CONTAINER and not self.network_container:
            raise ValueError(
                "RunConfig: network=CONTAINER requires network_container to be set"
            )
        if self.detach and (self.tty or self.auto_tty):
            raise ValueError(
                "RunConfig: detach=True is mutually exclusive with tty/auto_tty"
            )
        if self.timeout is not None and self.timeout <= 0:
            raise ValueError(
                f"RunConfig: timeout must be positive, got {self.timeout!r}"
            )
        if isinstance(self.command, list):
            object.__setattr__(self, "command", tuple(self.command))
        _freeze_mapping(self, ["environment", "labels"])
        _freeze_sequence(self, ["volumes", "ports", "runtime_flags"])


@dataclass(frozen=True)
class ImageInfo:
    id: str
    tags: tuple[str, ...] = field(default_factory=tuple)
    size: int = 0
    created: str | None = None
    labels: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _freeze_mapping(self, ["labels"])
        _freeze_sequence(self, ["tags"])


@dataclass(frozen=True)
class ContainerInfo:
    id: str
    name: str
    image: str
    state: ContainerState
    status: str
    created: str | None = None
    ports: tuple[PortMapping, ...] = field(default_factory=tuple)
    labels: Mapping[str, str] = field(default_factory=dict)
    exit_code: int | None = None

    def __post_init__(self) -> None:
        _freeze_mapping(self, ["labels"])
        _freeze_sequence(self, ["ports"])


@dataclass(frozen=True)
class VolumeInfo:
    name: str
    driver: str
    mountpoint: str | None = None
    labels: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _freeze_mapping(self, ["labels"])


@dataclass(frozen=True)
class NetworkInfo:
    id: str
    name: str
    driver: str
    scope: str
    labels: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _freeze_mapping(self, ["labels"])


@dataclass(frozen=True)
class PruneResult:
    deleted: int = 0
    reclaimed_bytes: int = 0


@dataclass(frozen=True)
class ExecResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class RawExecResult:
    returncode: int
    stdout: bytes
    stderr: bytes


@dataclass(frozen=True)
class RuntimePreference:
    """Explicit user declaration of what engine to use.

    No guessing, no fallback. The binary must be explicitly declared.
    Creation does NOT probe availability.
    """

    kind: RuntimeKind
    binary: str
