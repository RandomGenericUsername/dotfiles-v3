from __future__ import annotations

from pathlib import Path
from typing import Any

from config_assembler_engine import (
    ResolutionPolicy,
)
from config_assembler_engine.adapters.factories import create_standard_assembler
from config_assembler_engine.adapters.parsers.yaml_parser import YamlConfigParser
from config_assembler_engine.adapters.strategies.cli_path import CliPathStrategy
from config_assembler_engine.adapters.strategies.default_file import DefaultFileStrategy
from config_assembler_engine.adapters.strategies.directory import DirectoryTraversalStrategy
from config_assembler_engine.adapters.strategies.env_path import EnvPathStrategy
from config_assembler_engine.adapters.strategies.xdg import XdgStrategy

from wallpaper_effects_generator.adapters.schemas.effects_schema import (
    EffectsConfigSchema,
    ParameterDefSchema,
    ParameterTypeSchema,
)
from wallpaper_effects_generator.constants import (
    EFFECTS_FILENAME,
    EFFECTS_TRAVERSAL_DEPTH,
    EFFECTS_XDG_SUBDIR,
)
from wallpaper_effects_generator.domain.enums import ItemType
from wallpaper_effects_generator.domain.exceptions import EffectsValidationError
from wallpaper_effects_generator.domain.models import (
    ChainStep,
    CompositeDefinition,
    EffectDefinition,
    EffectsCatalog,
    ParameterDefinition,
    PresetDefinition,
)
from wallpaper_effects_generator.domain.services import CatalogValidationService


def _resolve_param_default(
    pdef: ParameterDefSchema, param_types: dict[str, ParameterTypeSchema]
) -> Any:
    if pdef.default is not None:
        return pdef.default
    type_def = param_types.get(pdef.type)
    if type_def is not None:
        return type_def.default
    return None


def _resolve_param_bound(
    pdef: ParameterDefSchema, param_types: dict[str, ParameterTypeSchema], attr: str
) -> float | None:
    val = getattr(pdef, attr)
    if val is not None:
        return val
    type_def = param_types.get(pdef.type)
    if type_def is not None:
        return getattr(type_def, attr)
    return None


def _schema_to_catalog(schema: EffectsConfigSchema) -> EffectsCatalog:
    param_types = schema.parameter_types
    return EffectsCatalog(
        effects=tuple(
            EffectDefinition(
                name=e.name,
                description=e.description,
                command=e.command,
                parameters=tuple(
                    ParameterDefinition(
                        key=k,
                        description=v.description,
                        default=_resolve_param_default(v, param_types),
                        min=_resolve_param_bound(v, param_types, "min"),
                        max=_resolve_param_bound(v, param_types, "max"),
                    )
                    for k, v in e.parameters.items()
                ),
                item_type=(
                    ItemType(e.item_type)
                    if e.item_type in {"effect", "composite", "preset"}
                    else ItemType.EFFECT
                ),
            )
            for e in schema.effects
        ),
        composites=tuple(
            CompositeDefinition(
                name=c.name,
                description=c.description,
                steps=tuple(
                    ChainStep(effect_name=s.effect_name, parameters=dict(s.parameters))
                    for s in c.steps
                ),
            )
            for c in schema.composites
        ),
        presets=tuple(
            PresetDefinition(
                name=p.name,
                description=p.description,
                effects=tuple(p.effects),
                parameters=dict(p.parameters),
            )
            for p in schema.presets
        ),
    )


_STRATEGIES = [
    CliPathStrategy(),
    EnvPathStrategy(),
    DirectoryTraversalStrategy(filename=EFFECTS_FILENAME, max_levels=EFFECTS_TRAVERSAL_DEPTH),
    XdgStrategy(xdg_subdir=EFFECTS_XDG_SUBDIR, filename=EFFECTS_FILENAME),
]


class YamlEffectLoader:
    def __init__(self, default_effects_path: Path | None = None) -> None:
        strategies = list(_STRATEGIES)
        if default_effects_path:
            strategies.append(DefaultFileStrategy(path=default_effects_path))
        self._assembler = create_standard_assembler(
            parser=YamlConfigParser(),
            strategies=strategies,
        )
        self._resolved_path: Path | None = None

    def load(self, path: Path | None = None) -> EffectsCatalog:
        result = self._assembler.execute(
            policy=ResolutionPolicy(env_prefix="WALLPAPER_EFFECTS"),
            rules=[],
            schema=EffectsConfigSchema,
            explicit_path=str(path) if path else None,
        )
        self._resolved_path = result.resolved_path.path
        catalog = _schema_to_catalog(result.config)
        errors = CatalogValidationService().validate(catalog)
        if errors:
            raise EffectsValidationError("; ".join(errors))
        return catalog

    def get_default_path(self) -> Path:
        return Path("effects.yaml")

    def get_resolved_path(self) -> Path | None:
        return self._resolved_path
