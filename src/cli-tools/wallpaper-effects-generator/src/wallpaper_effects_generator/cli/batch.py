from __future__ import annotations

from pathlib import Path

import typer

from wallpaper_effects_generator.cli.options import CONFIG_OPT, EFFECTS_OPT, ENGINE_OPT, RUNTIME_OPT
from wallpaper_effects_generator.constants import MAX_WORKERS_AUTO
from wallpaper_effects_generator.domain.enums import (
    ContainerEngine,
    ItemType,
    OutputFormat,
    RuntimeMode,
)
from wallpaper_effects_generator.domain.models import BatchRequest
from wallpaper_effects_generator.factory import create_batch_processor, create_output_adapter
from wallpaper_effects_generator.ports.output import OutputPort

from .process import _resolve_context, _resolve_processor

_DEFAULT_OUTPUT_DIR = Path("/tmp/wallpaper-effects")

batch_app = typer.Typer(
    name="batch",
    help="Batch process effects, composites, presets, or all at once",
)


@batch_app.callback()
def batch_callback(
    ctx: typer.Context,
    config: Path | None = CONFIG_OPT,
    effects: Path | None = EFFECTS_OPT,
    runtime: RuntimeMode | None = RUNTIME_OPT,
    container_engine: ContainerEngine | None = ENGINE_OPT,
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["config"] = str(config) if config else None
    ctx.obj["effects"] = str(effects) if effects else None
    ctx.obj["runtime"] = runtime
    ctx.obj["container_engine"] = container_engine


def _get_output_adapter(
    ctx: typer.Context, default: OutputFormat = OutputFormat.JSON
) -> OutputPort:
    fmt = ctx.obj.get("output_format")
    return create_output_adapter(fmt if fmt is not None else default)


def _parse_params(raw: list[str]) -> dict[str, str]:
    params: dict[str, str] = {}
    for item in raw:
        if "=" not in item:
            raise typer.BadParameter(f"Invalid param format '{item}', expected key=value")
        key, value = item.split("=", 1)
        params[key] = value
    return params


def _run_batch(
    ctx: typer.Context,
    input: Path,
    output: Path | None,
    flat: bool,
    explicit_output: bool,
    strict: bool,
    parallel: bool,
    max_workers: int,
    item_types: tuple[ItemType, ...],
    params: dict[str, str] | None = None,
) -> None:
    output_adapter = _get_output_adapter(ctx)
    settings, catalog = _resolve_context(ctx, input)
    if explicit_output and output is None:
        explicit_output = False
    output_dir = output or settings.output.directory or _DEFAULT_OUTPUT_DIR
    processor = _resolve_processor(settings, catalog, output_dir, deps=ctx.obj.get("deps"))
    batch_processor = create_batch_processor(processor, catalog)

    request = BatchRequest(
        input_path=input.resolve(),
        output_dir=output_dir.resolve(),
        item_types=item_types,
        flat=flat,
        explicit_output=explicit_output,
        parallel=parallel,
        strict=strict,
        max_workers=max_workers,
        params=params or {},
    )
    result = batch_processor.process_batch(request)
    output_adapter.batch_result(result)


@batch_app.command()
def effects(
    ctx: typer.Context,
    input: Path = typer.Argument(..., help="Input image or directory path"),
    output: Path | None = typer.Option(None, "-o", "--output", help="Output directory"),
    flat: bool = typer.Option(False, "--flat", help="Flatten output directory structure"),
    explicit_output: bool = typer.Option(
        False, "--explicit-output", help="Write directly to output dir"
    ),
    strict: bool = typer.Option(False, "--strict", help="Stop on first failure"),
    parallel: bool = typer.Option(
        True, "--parallel/--no-parallel", help="Enable parallel execution"
    ),
    max_workers: int = typer.Option(
        MAX_WORKERS_AUTO, "--max-workers", help="Maximum parallel workers (0 = auto)"
    ),
    param: list[str] = typer.Option([], "--param", help="Parameter overrides (key=value)"),
) -> None:
    _run_batch(
        ctx,
        input,
        output,
        flat,
        explicit_output,
        strict,
        parallel,
        max_workers,
        (ItemType.EFFECT,),
        params=_parse_params(param),
    )


@batch_app.command()
def composites(
    ctx: typer.Context,
    input: Path = typer.Argument(..., help="Input image or directory path"),
    output: Path | None = typer.Option(None, "-o", "--output", help="Output directory"),
    flat: bool = typer.Option(False, "--flat", help="Flatten output directory structure"),
    explicit_output: bool = typer.Option(
        False, "--explicit-output", help="Write directly to output dir"
    ),
    strict: bool = typer.Option(False, "--strict", help="Stop on first failure"),
    parallel: bool = typer.Option(
        True, "--parallel/--no-parallel", help="Enable parallel execution"
    ),
    max_workers: int = typer.Option(
        MAX_WORKERS_AUTO, "--max-workers", help="Maximum parallel workers (0 = auto)"
    ),
    param: list[str] = typer.Option([], "--param", help="Parameter overrides (key=value)"),
) -> None:
    _run_batch(
        ctx,
        input,
        output,
        flat,
        explicit_output,
        strict,
        parallel,
        max_workers,
        (ItemType.COMPOSITE,),
        params=_parse_params(param),
    )


@batch_app.command()
def presets(
    ctx: typer.Context,
    input: Path = typer.Argument(..., help="Input image or directory path"),
    output: Path | None = typer.Option(None, "-o", "--output", help="Output directory"),
    flat: bool = typer.Option(False, "--flat", help="Flatten output directory structure"),
    explicit_output: bool = typer.Option(
        False, "--explicit-output", help="Write directly to output dir"
    ),
    strict: bool = typer.Option(False, "--strict", help="Stop on first failure"),
    parallel: bool = typer.Option(
        True, "--parallel/--no-parallel", help="Enable parallel execution"
    ),
    max_workers: int = typer.Option(
        MAX_WORKERS_AUTO, "--max-workers", help="Maximum parallel workers (0 = auto)"
    ),
    param: list[str] = typer.Option([], "--param", help="Parameter overrides (key=value)"),
) -> None:
    _run_batch(
        ctx,
        input,
        output,
        flat,
        explicit_output,
        strict,
        parallel,
        max_workers,
        (ItemType.PRESET,),
        params=_parse_params(param),
    )


@batch_app.command(name="all")
def run_all(
    ctx: typer.Context,
    input: Path = typer.Argument(..., help="Input image or directory path"),
    output: Path | None = typer.Option(None, "-o", "--output", help="Output directory"),
    flat: bool = typer.Option(False, "--flat", help="Flatten output directory structure"),
    explicit_output: bool = typer.Option(
        False, "--explicit-output", help="Write directly to output dir"
    ),
    strict: bool = typer.Option(False, "--strict", help="Stop on first failure"),
    parallel: bool = typer.Option(
        True, "--parallel/--no-parallel", help="Enable parallel execution"
    ),
    max_workers: int = typer.Option(
        MAX_WORKERS_AUTO, "--max-workers", help="Maximum parallel workers (0 = auto)"
    ),
    param: list[str] = typer.Option([], "--param", help="Parameter overrides (key=value)"),
) -> None:
    _run_batch(
        ctx,
        input,
        output,
        flat,
        explicit_output,
        strict,
        parallel,
        max_workers,
        (ItemType.ALL,),
        params=_parse_params(param),
    )
