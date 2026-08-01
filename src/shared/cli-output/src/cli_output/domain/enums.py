from __future__ import annotations

from enum import Enum


class OutputFormat(Enum):
    JSON = "json"
    RICH = "rich"
    PLAIN = "plain"

    def __str__(self) -> str:
        return self.value
