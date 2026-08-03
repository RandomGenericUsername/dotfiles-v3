from __future__ import annotations

from pathlib import Path

import typer

from icon_templates_renderer.domain.exceptions import (
    ConfigResolutionError,
    IconRendererError,
)
from icon_templates_renderer.domain.models import ResolvedRoots
from icon_templates_renderer.factory import CliDependencies


def to_optional_path(value: Path | None) -> Path | None:
    if value is None:
        return None
    return Path(value).expanduser().resolve()


def resolve_roots(
    deps: CliDependencies,
    config_flag: Path | None,
    template_dir_flag: Path | None,
    color_scheme_flag: Path | None,
    output_dir_flag: Path | None,
    *,
    required: bool,
) -> ResolvedRoots:
    """Orchestrate settings -> discovery -> ResolvedRoots (design D7).

    Precedence per root: CLI flag > env (ICON_RENDERER__...) > settings.toml
    field > discovery (templates/color_scheme) / bundled default (output_dir).
    When ``required`` is True, a missing templates root or color scheme raises
    a clear ``ConfigResolutionError`` naming the levers.
    """
    cli_overrides: dict[str, str] = {}
    if template_dir_flag is not None:
        cli_overrides["templates.dir"] = str(to_optional_path(template_dir_flag))
    if color_scheme_flag is not None:
        cli_overrides["color_scheme.path"] = str(to_optional_path(color_scheme_flag))
    if output_dir_flag is not None:
        cli_overrides["output.output_dir"] = str(to_optional_path(output_dir_flag))

    settings = deps.config_resolver.resolve(
        explicit_path=str(config_flag) if config_flag is not None else None,
        cli_overrides=cli_overrides,
    )

    templates_dir = settings.templates.dir
    if templates_dir is None:
        templates_dir = deps.template_dir_resolver.resolve()

    color_scheme = settings.color_scheme.path
    if color_scheme is None:
        color_scheme = deps.color_scheme_resolver.resolve()

    output_root = settings.output.output_dir

    roots = ResolvedRoots(
        template_root=templates_dir,
        color_scheme=color_scheme,
        output_root=output_root,
    )

    if required:
        if roots.template_root is None:
            raise ConfigResolutionError(
                "templates_dir",
                ("--template-dir", "ICON_RENDERER__TEMPLATES__DIR", "[templates] dir", "discovery"),
            )
        if roots.color_scheme is None:
            raise ConfigResolutionError(
                "color_scheme",
                (
                    "--color-scheme",
                    "ICON_RENDERER__COLOR_SCHEME__PATH",
                    "[color_scheme] path",
                    "discovery",
                ),
            )
        if roots.output_root is None:
            raise ConfigResolutionError(
                "output_dir",
                ("--output-dir", "ICON_RENDERER__OUTPUT__OUTPUT_DIR", "[output] output_dir"),
            )
    return roots


def handle_error(exc: IconRendererError, output_adapter: object) -> None:
    output_adapter.error(exc)  # type: ignore[attr-defined]
    raise typer.Exit(code=1) from None
