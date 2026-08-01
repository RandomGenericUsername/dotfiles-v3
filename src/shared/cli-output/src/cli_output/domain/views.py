from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console


@dataclass(frozen=True)
class MessageView:
    text: str


@dataclass(frozen=True)
class ResultView:
    success: bool
    fields: dict[str, Any]
    title: str | None = None


@dataclass(frozen=True)
class ListView:
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    title: str | None = None
    summary: dict[str, Any] | None = None


@dataclass(frozen=True)
class ErrorView:
    kind: str
    message: str
    details: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ConfigInfoView:
    resolved_path: str | None
    sources: tuple[str, ...]
    sections: tuple[tuple[str, dict[str, Any]], ...]
    applied_overrides: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class RawView:
    content: str
    content_type: str | None = None


@dataclass(frozen=True)
class ProgressEvent:
    phase: str
    message: str
    done: int | None = None
    total: int | None = None


@dataclass(frozen=True)
class CustomView:
    plain: str
    object: Any
    rich: str | Callable[[Console], None]
