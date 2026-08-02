from __future__ import annotations

from pathlib import Path

import typer

from icon_templates_renderer.domain.exceptions import IconRendererError
from icon_templates_renderer.domain.models import PathOverrides


def to_optional_path(value: Path | None) -> Path | None:
    if value is None:
        return None
    return Path(value).expanduser().resolve()


def build_overrides(
    template_dir: Path | None,
    color_scheme: Path | None,
    output_dir: Path | None,
) -> PathOverrides:
    return PathOverrides(
        template_dir=to_optional_path(template_dir),
        color_scheme=to_optional_path(color_scheme),
        output_dir=to_optional_path(output_dir),
    )


def handle_error(exc: IconRendererError, output_adapter: object) -> None:
    output_adapter.error(exc)  # type: ignore[attr-defined]
    raise typer.Exit(code=1) from None
