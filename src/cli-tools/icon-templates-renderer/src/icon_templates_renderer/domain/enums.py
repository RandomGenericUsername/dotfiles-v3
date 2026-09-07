from __future__ import annotations

from enum import Enum


class OutputFormat(Enum):
    JSON = "json"
    RICH = "rich"
    PLAIN = "plain"

    def __str__(self) -> str:
        return self.value


class Verbosity(Enum):
    QUIET = 0
    NORMAL = 1
    VERBOSE = 2
    DEBUG = 3


class MappingOrigin(Enum):
    VOCABULARY = "vocabulary"
    GROUP = "group"
    VARIANT = "variant"

    def __str__(self) -> str:
        return self.value


class TemplateMode(Enum):
    TEMPLATED = "templated"
    BARE = "bare"

    def __str__(self) -> str:
        return self.value
