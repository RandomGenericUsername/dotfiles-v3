from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from color_scheme_generator.domain.models import AppSettings


def _value_to_toml(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, Enum):
        return f'"{v.value}"'
    if isinstance(v, Path):
        return f'"{v!s}"'
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, int | float):
        return str(v)
    if isinstance(v, tuple | list):
        if not v:
            return "[]"
        return "[" + ", ".join(_value_to_toml(x) for x in v) + "]"
    if v is None:
        return ""
    return f'"{v!s}"'


def _skip_none(v: Any) -> bool:
    return v is None


def _dataclass_to_toml_section(obj: Any, section_name: str) -> str:
    lines: list[str] = []
    lines.append(f"[{section_name}]")
    for field_name in [f.name for f in obj.__dataclass_fields__.values()]:
        val = getattr(obj, field_name)
        if _skip_none(val):
            continue
        lines.append(f'{field_name} = {_value_to_toml(val)}')
    lines.append("")
    return "\n".join(lines)


class SettingsSerializer:
    def serialize(self, settings: AppSettings) -> str:
        sections: list[str] = []
        sections.append(_dataclass_to_toml_section(settings.output, "output"))
        sections.append(_dataclass_to_toml_section(settings.generation, "generation"))
        sections.append(_dataclass_to_toml_section(settings.template, "template"))
        sections.append(_dataclass_to_toml_section(settings.runtime, "runtime"))
        sections.append(_dataclass_to_toml_section(settings.container, "container"))
        return "\n".join(sections)

    def deserialize(self, raw: str) -> AppSettings:
        raise NotImplementedError("deserialize not needed for operational commands")
