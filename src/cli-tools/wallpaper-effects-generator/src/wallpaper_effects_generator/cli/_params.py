from __future__ import annotations

import typer

from wallpaper_effects_generator.domain.enums import ItemType
from wallpaper_effects_generator.domain.exceptions import UnknownParamError
from wallpaper_effects_generator.domain.models import (
    EffectDefinition,
    EffectsCatalog,
)


def parse_params(raw: list[str]) -> dict[str, str]:
    params: dict[str, str] = {}
    for item in raw:
        if "=" not in item:
            raise typer.BadParameter(f"Invalid param format '{item}', expected key=value")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise typer.BadParameter(f"Invalid param format '{item}', expected key=value")
        params[key] = value
    return params


def assert_params_known(
    user_params: dict[str, str],
    scope_units: list[EffectDefinition],
    scope_label: str,
) -> None:
    union: set[str] = set()
    for unit in scope_units:
        union |= {p.key for p in unit.parameters}
    unknown = set(user_params) - union
    if unknown:
        raise UnknownParamError(sorted(unknown), scope_label, sorted(union))


def build_scope_units(
    catalog: EffectsCatalog,
    item_types: tuple[ItemType, ...],
) -> list[EffectDefinition]:
    units_by_name: dict[str, EffectDefinition] = {}
    if ItemType.EFFECT in item_types or ItemType.ALL in item_types:
        for effect in catalog.effects:
            units_by_name[effect.name] = effect
    if ItemType.COMPOSITE in item_types or ItemType.ALL in item_types:
        for composite in catalog.composites:
            for step in composite.steps:
                effect = catalog.find_effect(step.effect_name)
                units_by_name[effect.name] = effect
    if ItemType.PRESET in item_types or ItemType.ALL in item_types:
        for preset in catalog.presets:
            for effect_name in preset.effects:
                effect = catalog.find_effect(effect_name)
                units_by_name[effect.name] = effect
    return list(units_by_name.values())


def batch_scope_label(item_types: tuple[ItemType, ...]) -> str:
    if ItemType.ALL in item_types:
        return "all"
    labels = {
        ItemType.EFFECT: "effects",
        ItemType.COMPOSITE: "composites",
        ItemType.PRESET: "presets",
    }
    return ", ".join(labels[t] for t in item_types if t in labels)
