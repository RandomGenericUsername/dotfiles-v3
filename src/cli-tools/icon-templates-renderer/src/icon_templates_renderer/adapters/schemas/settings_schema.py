from __future__ import annotations

from pydantic import BaseModel

from icon_templates_renderer.domain.enums import Verbosity


class OutputSettingsSchema(BaseModel):
    verbosity: int = Verbosity.NORMAL.value


class CoreSettingsSchema(BaseModel):
    output: OutputSettingsSchema = OutputSettingsSchema()
