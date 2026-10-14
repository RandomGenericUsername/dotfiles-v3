from __future__ import annotations

from pathlib import Path

import typer

from wallpaper_effects_generator.cli._params import (
    assert_params_known,
    batch_scope_label,
    build_scope_units,
    parse_params,
)
from wallpaper_effects_generator.cli.options import CONFIG_OPT, EFFECTS_OPT, ENGINE_OPT, RUNTIME_OPT
from wallpaper_effects_generator.domain.enums import (
    ContainerEngine,
    ItemType,
    OutputFormat,
    RuntimeMode,
)
from wallpaper_effects_generator.domain.exceptions import UnknownParamError
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


def _run_batch(
    ctx: typer.Context,
    input: Path,
    output: Path | None,
    flat: bool,
    explicit_output: bool,
    strict: bool | None,
    parallel: bool | None,
    max_workers: int | None,
    item_types: tuple[ItemType, ...],
    params: dict[str, str] | None = None,
) -> None:
    output_adapter = _get_output_adapter(ctx)
    settings, catalog = _resolve_context(ctx, input)
    # ``execution.*`` from the resolved settings is the default; an explicit
    # CLI flag still wins. This is what makes the setting authoritative for the
    # runtime's ``weg batch all`` invocation (which passes no flags).
    execution = settings.execution
    strict = execution.strict if strict is None else strict
    parallel = execution.parallel if parallel is None else parallel
    max_workers = execution.max_workers if max_workers is None else max_workers
    if explicit_output and output is None:
        raise typer.BadParameter("--explicit-output requires -o/--output")
    if params:
        try:
            assert_params_known(
                params,
                build_scope_units(catalog, item_types),
                f"batch {batch_scope_label(item_types)}",
            )
        except UnknownParamError as e:
            raise typer.BadParameter(str(e)) from e
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
    strict: bool | None = typer.Option(
        None, "--strict", help="Stop on first failure (default: settings.execution.strict)"
    ),
    parallel: bool | None = typer.Option(
        None,
        "--parallel/--no-parallel",
        help="Enable parallel execution (default: settings.execution.parallel)",
    ),
    max_workers: int | None = typer.Option(
        None,
        "--max-workers",
        help="Maximum parallel workers, 0 = auto (default: settings.execution.max_workers)",
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
        params=parse_params(param),
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
    strict: bool | None = typer.Option(
        None, "--strict", help="Stop on first failure (default: settings.execution.strict)"
    ),
    parallel: bool | None = typer.Option(
        None,
        "--parallel/--no-parallel",
        help="Enable parallel execution (default: settings.execution.parallel)",
    ),
    max_workers: int | None = typer.Option(
        None,
        "--max-workers",
        help="Maximum parallel workers, 0 = auto (default: settings.execution.max_workers)",
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
        params=parse_params(param),
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
    strict: bool | None = typer.Option(
        None, "--strict", help="Stop on first failure (default: settings.execution.strict)"
    ),
    parallel: bool | None = typer.Option(
        None,
        "--parallel/--no-parallel",
        help="Enable parallel execution (default: settings.execution.parallel)",
    ),
    max_workers: int | None = typer.Option(
        None,
        "--max-workers",
        help="Maximum parallel workers, 0 = auto (default: settings.execution.max_workers)",
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
        params=parse_params(param),
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
    strict: bool | None = typer.Option(
        None, "--strict", help="Stop on first failure (default: settings.execution.strict)"
    ),
    parallel: bool | None = typer.Option(
        None,
        "--parallel/--no-parallel",
        help="Enable parallel execution (default: settings.execution.parallel)",
    ),
    max_workers: int | None = typer.Option(
        None,
        "--max-workers",
        help="Maximum parallel workers, 0 = auto (default: settings.execution.max_workers)",
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
        params=parse_params(param),
    )
