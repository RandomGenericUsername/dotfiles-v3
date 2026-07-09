import tomllib
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints

from wallpaper_effects_generator.domain.models import (
    AppSettings,
    BackendSettings,
    ContainerSettings,
    ExecutionSettings,
    OutputSettings,
    ProcessingSettings,
    RuntimeSettings,
)

_SETTINGS_CLS_MAP: dict[str, type[Any]] = {
    "execution": ExecutionSettings,
    "output": OutputSettings,
    "processing": ProcessingSettings,
    "backend": BackendSettings,
    "runtime": RuntimeSettings,
    "container": ContainerSettings,
}


def _has_path_type(ftype: Any) -> bool:
    origin = get_origin(ftype)
    if origin is None:
        return ftype is Path
    args = get_args(ftype)
    return any(_has_path_type(a) for a in args)


def _dataclass_to_toml(obj: Any, prefix: str = "") -> str:
    lines: list[str] = []
    for f in fields(obj):
        val = getattr(obj, f.name)
        if val is None:
            continue
        key = f.name
        if is_dataclass(val.__class__):
            table_name = f"{prefix}{key}" if prefix else key
            lines.append(f"\n[{table_name}]")
            lines.append(_dataclass_to_toml(val, prefix="  "))
        elif isinstance(val, Enum):
            lines.append(f"{prefix}{key} = \"{val.value}\"")
        elif isinstance(val, bool):
            lines.append(f"{prefix}{key} = {str(val).lower()}")
        elif isinstance(val, int | float):
            lines.append(f"{prefix}{key} = {val}")
        else:
            lines.append(f"{prefix}{key} = \"{val}\"")
    return "\n".join(lines)


def _find_enum_type(ftype: Any) -> type[Enum] | None:
    origin = get_origin(ftype)
    if origin is None:
        if isinstance(ftype, type) and issubclass(ftype, Enum):
            return ftype
        return None
    args = get_args(ftype)
    for arg in args:
        result = _find_enum_type(arg)
        if result is not None:
            return result
    return None


def _coerce_value(val: Any, ftype: Any) -> Any:
    if is_dataclass(ftype):
        return _toml_to_dataclass(val, ftype)
    enum_cls = _find_enum_type(ftype)
    if enum_cls is not None:
        if isinstance(val, str):
            try:
                return enum_cls(val)
            except ValueError:
                for member in enum_cls:
                    if str(member.value) == val:
                        return member
                try:
                    return enum_cls(int(val))
                except (ValueError, TypeError):
                    return enum_cls(val)
        return enum_cls(val)
    if _has_path_type(ftype) and isinstance(val, str):
        return Path(val)
    return val


def _toml_to_dataclass(data: dict[str, Any], model_cls: type[Any]) -> Any:
    hints = get_type_hints(model_cls)
    field_map = {f.name: hints.get(f.name, f.type) for f in fields(model_cls)}
    kwargs: dict[str, Any] = {}
    for key, val in data.items():
        if key in field_map:
            kwargs[key] = _coerce_value(val, field_map[key])
    return model_cls(**kwargs)


class SettingsSerializer:
    def serialize(self, settings: AppSettings, path: Path) -> None:
        content = _dataclass_to_toml(settings)
        path.write_text(content, encoding="utf-8")

    def deserialize(self, path: Path) -> AppSettings:
        raw = path.read_bytes()
        data = tomllib.loads(raw.decode("utf-8"))
        root: dict[str, Any] = {}
        for key in ("version",):
            root[key] = data.get(key, AppSettings().version)
        for section_key, cls in _SETTINGS_CLS_MAP.items():
            section_data = data.get(section_key, {})
            root[section_key] = _toml_to_dataclass(section_data, cls)
        return AppSettings(**root)
