from enum import Enum, StrEnum


class RuntimeKind(StrEnum):
    DOCKER = "docker"
    PODMAN = "podman"


class ContainerState(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    RESTARTING = "restarting"
    REMOVING = "removing"
    EXITED = "exited"
    DEAD = "dead"


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
