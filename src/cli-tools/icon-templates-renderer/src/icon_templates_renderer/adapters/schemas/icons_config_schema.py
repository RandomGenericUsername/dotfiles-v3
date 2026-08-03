from __future__ import annotations

from pydantic import BaseModel


class VariantSchema(BaseModel):
    name: str
    template: str
    output: str
    color_mappings: dict[str, str] = {}


class IconGroupSchema(BaseModel):
    template_dir: str = "."
    output_dir: str = "."
    unsafe: bool = False
    color_mappings: dict[str, str] = {}
    variants: list[VariantSchema]
