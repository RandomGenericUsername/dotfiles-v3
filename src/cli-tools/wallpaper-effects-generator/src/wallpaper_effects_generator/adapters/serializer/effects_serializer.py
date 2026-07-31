from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from wallpaper_effects_generator.domain.enums import ItemType
from wallpaper_effects_generator.domain.models import (
    ChainStep,
    CompositeDefinition,
    EffectDefinition,
    EffectsCatalog,
    ParameterDefinition,
    PresetDefinition,
)


def _catalog_to_dict(catalog: EffectsCatalog) -> dict[str, Any]:
    return {
        "effects": [
            {
                "name": e.name,
                "description": e.description,
                "command": e.command,
                "item_type": e.item_type.value,
                "parameters": {
                    p.key: {
                        "type": str(type(p.default).__name__)
                        if p.default is not None
                        else "string",
                        "default": p.default,
                        "description": p.description,
                        "required": p.required,
                        "min": p.min,
                        "max": p.max,
                    }
                    for p in e.parameters
                },
            }
            for e in catalog.effects
        ],
        "composites": [
            {
                "name": c.name,
                "description": c.description,
                "steps": [
                    {
                        "effect_name": s.effect_name,
                        "parameters": dict(s.parameters),
                    }
                    for s in c.steps
                ],
            }
            for c in catalog.composites
        ],
        "presets": [
            {
                "name": p.name,
                "description": p.description,
                "effects": list(p.effects),
            }
            for p in catalog.presets
        ],
    }


def _dict_to_catalog(data: dict[str, Any]) -> EffectsCatalog:
    effects = tuple(
        EffectDefinition(
            name=e["name"],
            description=e.get("description", ""),
            command=e["command"],
            item_type=(
                ItemType(e["item_type"])
                if "item_type" in e and e["item_type"] in {"effect", "composite", "preset"}
                else ItemType.EFFECT
            ),
            parameters=tuple(
                ParameterDefinition(
                    key=k,
                    description=v.get("description", ""),
                    default=v.get("default"),
                    required=v.get("required", False),
                    min=v.get("min"),
                    max=v.get("max"),
                )
                for k, v in e.get("parameters", {}).items()
            ),
        )
        for e in data.get("effects", [])
    )
    composites = tuple(
        CompositeDefinition(
            name=c["name"],
            description=c.get("description", ""),
            steps=tuple(
                ChainStep(
                    effect_name=s["effect_name"],
                    parameters=dict(s.get("parameters", {})),
                )
                for s in c.get("steps", [])
            ),
        )
        for c in data.get("composites", [])
    )
    presets = tuple(
        PresetDefinition(
            name=p["name"],
            description=p.get("description", ""),
            effects=tuple(p.get("effects", [])),
        )
        for p in data.get("presets", [])
    )
    return EffectsCatalog(effects=effects, composites=composites, presets=presets)


class EffectsSerializer:
    def serialize(self, catalog: EffectsCatalog, path: Path) -> None:
        data = _catalog_to_dict(catalog)
        with path.open("w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def deserialize(self, path: Path) -> EffectsCatalog:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data is None:
            return EffectsCatalog()
        return _dict_to_catalog(data)
