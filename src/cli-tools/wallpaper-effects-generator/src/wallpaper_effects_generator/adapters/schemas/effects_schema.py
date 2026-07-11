from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ParameterTypeSchema(BaseModel):
    type: str
    pattern: str = ""
    default: Any = None
    description: str = ""


class ParameterDefSchema(BaseModel):
    type: str = "string"
    cli_flag: str = ""
    default: Any = None
    description: str = ""


class EffectSchema(BaseModel):
    name: str
    description: str
    command: str
    parameters: dict[str, ParameterDefSchema] = {}
    item_type: str = "effect"


class ChainStepSchema(BaseModel):
    effect_name: str
    parameters: dict[str, str] = {}


class CompositeSchema(BaseModel):
    name: str
    description: str
    steps: list[ChainStepSchema] = []


class PresetSchema(BaseModel):
    name: str
    description: str
    effects: list[str] = []
    parameters: dict[str, str] = {}


class EffectsConfigSchema(BaseModel):
    version: str = "1.0"
    parameter_types: dict[str, ParameterTypeSchema] = {}
    effects: list[EffectSchema] = []
    composites: list[CompositeSchema] = []
    presets: list[PresetSchema] = []
