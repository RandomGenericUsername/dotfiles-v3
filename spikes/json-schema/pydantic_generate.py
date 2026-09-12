#!/usr/bin/env python3
"""Pydantic variant: generate the history schema from Python models.

Assessment artifact for spike item 5. ``model_json_schema()`` emits draft
2020-12, so the output can be fed to the SAME jsonschema/Ajv validators used
for the neutral schema. The generated document is written to
``generated/history.pydantic.schema.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Trigger = Literal["seed", "set", "reconcile", "force", "regenerate", "doctor", "prune"]
NonNegInt = Annotated[int, Field(ge=0)]


class HistoryDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    removed: NonNegInt | None = None
    failed: NonNegInt | None = None
    layers: dict[str, NonNegInt] | None = None


class HistoryLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ts: str
    trigger: Trigger
    wallpaper: str
    palette: str | None
    effects: str | None
    icons: str | None
    source_path: str
    details: HistoryDetails | None = None


def generate() -> dict[str, object]:
    return HistoryLine.model_json_schema()


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "generated" / "history.pydantic.schema.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(generate(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[pydantic] wrote {out.relative_to(Path.cwd())}")
