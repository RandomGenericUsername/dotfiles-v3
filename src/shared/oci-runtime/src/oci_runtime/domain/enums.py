from enum import StrEnum


class RuntimeKind(StrEnum):
    DOCKER = "docker"
    PODMAN = "podman"

    @classmethod
    def _missing_(cls, value: object) -> "RuntimeKind | None":
        if isinstance(value, str) and value:
            member = str.__new__(cls, value)
            member._name_ = value
            member._value_ = value
            return member
        return None


class ContainerState(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    RESTARTING = "restarting"
    REMOVING = "removing"
    EXITED = "exited"
    DEAD = "dead"
    UNKNOWN = "unknown"

    @classmethod
    def _missing_(cls, value: object) -> "ContainerState":
        return cls.UNKNOWN


class RestartPolicy(StrEnum):
    NO = "no"
    ON_FAILURE = "on-failure"
    ALWAYS = "always"
    UNLESS_STOPPED = "unless-stopped"


class NetworkMode(StrEnum):
    BRIDGE = "bridge"
    HOST = "host"
    NONE = "none"
    CONTAINER = "container"


class VolumeMountType(StrEnum):
    BIND = "bind"
    VOLUME = "volume"
    TMPFS = "tmpfs"


class Subcommand(StrEnum):
    RUN = "run"
    BUILD = "build"
    TAG = "tag"
    PUSH = "push"
    PULL = "pull"
    RMI = "rmi"
    RM = "rm"
    EXEC = "exec"
    LOGS = "logs"
    INSPECT = "inspect"
    STOP = "stop"
    START = "start"
    RESTART = "restart"
    PRUNE = "prune"
    CREATE = "create"
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    LIST = "list"
    IMAGE = "image"
    CONTAINER = "container"
    VOLUME = "volume"
    NETWORK = "network"
