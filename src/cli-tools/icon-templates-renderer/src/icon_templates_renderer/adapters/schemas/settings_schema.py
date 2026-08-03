from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, field_validator

from icon_templates_renderer.domain.enums import Verbosity


class OutputSettingsSchema(BaseModel):
    output_dir: Path
    verbosity: int = Verbosity.NORMAL.value

    @field_validator("output_dir", mode="before")
    @classmethod
    def _reject_empty_output_dir(cls, v: object) -> object:
        if v is None or (isinstance(v, str) and v.strip() == ""):
            raise ValueError("output_dir must not be empty")
        return v


class TemplatesSettingsSchema(BaseModel):
    dir: Path | None = None


class ColorSchemeSettingsSchema(BaseModel):
    path: Path | None = None


class CoreSettingsSchema(BaseModel):
    output: OutputSettingsSchema = OutputSettingsSchema(
        output_dir=Path("/tmp/icon-templates-renderer")
    )
    templates: TemplatesSettingsSchema = TemplatesSettingsSchema()
    color_scheme: ColorSchemeSettingsSchema = ColorSchemeSettingsSchema()
