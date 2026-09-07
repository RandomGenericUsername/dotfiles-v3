from __future__ import annotations

from pathlib import Path

import typer

from icon_templates_renderer.cli._helpers import resolve_roots, to_optional_path
from icon_templates_renderer.cli.options import (
    COLOR_SCHEME_OPT,
    CONFIG_OPT,
    DIFF_OPT,
    DRY_RUN_OPT,
    ICON_OPT,
    ICONS_MANIFEST_OPT,
    PLACEHOLDER_OPT,
    TEMPLATE_DIR_OPT,
    TOKEN_OPT,
    UNSAFE_OPT,
    VARIANT_OPT,
)
from icon_templates_renderer.domain.exceptions import IconRendererError
from icon_templates_renderer.domain.models import (
    MappingSetDefaultRequest,
    MappingSetRequest,
    MappingShowRequest,
    ResolvedRoots,
)
from icon_templates_renderer.factory import CliDependencies

mapping_app = typer.Typer(help="Inspect icon color mappings (read-only).")


@mapping_app.command("show")
def show_command(
    ctx: typer.Context,
    yaml_file: Path = typer.Argument(..., help="Path to the icons YAML file"),  # noqa: B008
    icon: str | None = ICON_OPT,
    template_dir: Path | None = TEMPLATE_DIR_OPT,
    color_scheme: Path | None = COLOR_SCHEME_OPT,
    config: Path | None = CONFIG_OPT,
) -> None:
    """Show merged color mappings with per-entry origin as JSON-friendly output."""
    deps: CliDependencies = ctx.obj["deps"]
    try:
        roots: ResolvedRoots = resolve_roots(
            deps,
            config,
            template_dir,
            color_scheme,
            None,
            required=False,
        )
        request = MappingShowRequest(
            yaml_path=Path(yaml_file).resolve(),
            icon=icon,
            roots=roots,
        )
        result = deps.icon_renderer.mapping_show(request)
        deps.output_adapter.mapping_show_result(result)
    except IconRendererError as exc:
        deps.output_adapter.error(exc)
        raise typer.Exit(code=1) from None


@mapping_app.command("set")
def set_command(
    ctx: typer.Context,
    yaml_file: Path = typer.Argument(..., help="Path to the icons YAML file"),  # noqa: B008
    icon: str | None = ICON_OPT,
    placeholder: str = PLACEHOLDER_OPT,
    token: str = TOKEN_OPT,
    variant: str | None = VARIANT_OPT,
    unsafe: bool = UNSAFE_OPT,
    dry_run: bool = DRY_RUN_OPT,
    diff: bool = DIFF_OPT,
    template_dir: Path | None = TEMPLATE_DIR_OPT,
    color_scheme: Path | None = COLOR_SCHEME_OPT,
    config: Path | None = CONFIG_OPT,
) -> None:
    """Set one color mapping entry (group scope, or variant override with --variant)."""
    deps: CliDependencies = ctx.obj["deps"]
    try:
        if icon is None:
            raise IconRendererError("--icon is required for mapping set")
        roots: ResolvedRoots = resolve_roots(
            deps,
            config,
            template_dir,
            color_scheme,
            None,
            required=False,
        )
        request = MappingSetRequest(
            yaml_path=Path(yaml_file).resolve(),
            group=icon,
            placeholder=placeholder,
            token=token,
            variant=variant,
            roots=roots,
            unsafe=unsafe,
            dry_run=dry_run,
            show_diff=diff,
        )
        result = deps.icon_renderer.mapping_set(request)
        deps.output_adapter.mapping_set_result(result)
    except IconRendererError as exc:
        deps.output_adapter.error(exc)
        raise typer.Exit(code=1) from None


@mapping_app.command("set-default")
def set_default_command(
    ctx: typer.Context,
    defaults_file: Path = typer.Argument(  # noqa: B008
        ..., help="Path to the vocabulary defaults YAML file"
    ),
    placeholder: str = PLACEHOLDER_OPT,
    token: str = TOKEN_OPT,
    icons: Path | None = ICONS_MANIFEST_OPT,
    unsafe: bool = UNSAFE_OPT,
    dry_run: bool = DRY_RUN_OPT,
    diff: bool = DIFF_OPT,
    color_scheme: Path | None = COLOR_SCHEME_OPT,
    config: Path | None = CONFIG_OPT,
) -> None:
    """Retarget one vocabulary default; reports groups shadowing the placeholder."""
    deps: CliDependencies = ctx.obj["deps"]
    try:
        roots: ResolvedRoots = resolve_roots(
            deps,
            config,
            None,
            color_scheme,
            None,
            required=False,
        )
        request = MappingSetDefaultRequest(
            defaults_path=Path(defaults_file).resolve(),
            placeholder=placeholder,
            token=token,
            icons_path=to_optional_path(icons),
            roots=roots,
            unsafe=unsafe,
            dry_run=dry_run,
            show_diff=diff,
        )
        result = deps.icon_renderer.mapping_set_default(request)
        deps.output_adapter.mapping_set_default_result(result)
    except IconRendererError as exc:
        deps.output_adapter.error(exc)
        raise typer.Exit(code=1) from None
