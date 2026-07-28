from enum import Enum


class ItemType(Enum):
    EFFECT = "effect"
    COMPOSITE = "composite"
    PRESET = "preset"
    ALL = "all"

    @property
    def subdir_name(self) -> str:
        return self.value


class CatalogQuery(Enum):
    EFFECT = "effect"
    COMPOSITE = "composite"
    PRESET = "preset"
    ALL = "all"


class Verbosity(Enum):
    QUIET = 0
    NORMAL = 1
    VERBOSE = 2
    DEBUG = 3


class RuntimeMode(Enum):
    LOCAL = "local"
    CONTAINER = "container"

    def __str__(self) -> str:
        return self.value


class ContainerEngine(Enum):
    DOCKER = "docker"
    PODMAN = "podman"

    def __str__(self) -> str:
        return self.value


class OutputFormat(Enum):
    JSON = "json"
    RICH = "rich"
    PLAIN = "plain"

    def __str__(self) -> str:
        return self.value
