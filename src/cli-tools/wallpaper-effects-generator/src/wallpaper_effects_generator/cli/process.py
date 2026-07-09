from __future__ import annotations

from pathlib import Path

import typer

from wallpaper_effects_generator.domain.enums import OutputFormat, RuntimeMode
from wallpaper_effects_generator.domain.exceptions import (
    ConfigResolutionError,
    EffectsLoadError,
)
from wallpaper_effects_generator.domain.models import (
    AppSettings,
    ContainerSettings,
    EffectsCatalog,
    ProcessingRequest,
    RuntimeSettings,
)
from wallpaper_effects_generator.factory import (
    create_command_runner,
    create_container_processor,
    create_context_validator,
    create_dry_run_processor,
    create_image_manager,
    create_local_processor,
    create_output_adapter,
)
from wallpaper_effects_generator.ports.output import OutputPort
from wallpaper_effects_generator.ports.processor import EffectProcessorPort

process_app = typer.Typer(
    name="process",
    help="Apply effects to wallpapers",
)


def _parse_params(param: list[str]) -> dict[str, str]:
    params: dict[str, str] = {}
    for p in param:
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        key = k.strip()
        if key:
            params[key] = v
    return params


def _resolve_context(ctx: typer.Context, input_path: Path) -> tuple[AppSettings, EffectsCatalog]:
    if not input_path.is_file():
        raise typer.BadParameter(f"Input file not found: {input_path}")
    try:
        config_resolver = ctx.obj["deps"].config_resolver
        effect_loader = ctx.obj["deps"].effect_loader
        settings = config_resolver.resolve(
            explicit_path=Path(ctx.obj["config"]) if ctx.obj.get("config") else None
        )
        runtime_override = ctx.obj.get("runtime")
        engine_override = ctx.obj.get("container_engine")
        container = settings.container
        if engine_override is not None:
            container = ContainerSettings(
                engine=engine_override.value,
                image_tag=container.image_tag,
                image_registry=container.image_registry,
            )
        if runtime_override is not None:
            settings = AppSettings(
                version=settings.version,
                execution=settings.execution,
                output=settings.output,
                processing=settings.processing,
                backend=settings.backend,
                runtime=RuntimeSettings(mode=runtime_override),
                container=container,
            )
        elif engine_override is not None:
            settings = AppSettings(
                version=settings.version,
                execution=settings.execution,
                output=settings.output,
                processing=settings.processing,
                backend=settings.backend,
                runtime=settings.runtime,
                container=container,
            )
        catalog = effect_loader.load(
            path=Path(ctx.obj["effects"]) if ctx.obj.get("effects") else None
        )
        return settings, catalog
    except (OSError, ValueError, ConfigResolutionError, EffectsLoadError) as e:
        raise typer.BadParameter(f"Configuration error: {e}") from e


def _resolve_processor(
    settings: AppSettings,
    catalog: EffectsCatalog,
    output_dir: Path,
    dry_run: bool = False,
) -> EffectProcessorPort:
    runner = create_command_runner(settings)
    if dry_run:
        return create_dry_run_processor(
            command_runner=runner, catalog=catalog, output_dir=output_dir
        )
    if settings.runtime.mode == RuntimeMode.CONTAINER:
        image_manager = create_image_manager(runner)
        context_validator = create_context_validator(
            command_runner=runner, image_manager=image_manager
        )
        return create_container_processor(
            command_runner=runner,
            catalog=catalog,
            output_dir=output_dir,
            container_settings=settings.container,
            settings=settings,
            context_validator=context_validator,
        )
    return create_local_processor(
        command_runner=runner, catalog=catalog, output_dir=output_dir
    )


def _get_output_adapter(ctx: typer.Context) -> OutputPort:
    output_format = ctx.obj.get("output_format", OutputFormat.JSON)
    return create_output_adapter(output_format)


@process_app.command()
def effect(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Effect name"),
    input: Path = typer.Argument(..., help="Input image path"),
    output: Path | None = typer.Option(
        None, "-o", "--output", help="Output directory"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview commands only"),
    param: list[str] = typer.Option(
        [], "--param", help="Parameter overrides (key=value)"
    ),
    effect_name: str | None = typer.Option(
        None, "-e", "--effect", help="Effect name (overrides positional)"
    ),
) -> None:
    output_adapter = _get_output_adapter(ctx)
    name = effect_name or name
    output_dir = output or Path("/tmp/wallpaper-effects")
    params = _parse_params(param)
    settings, catalog = _resolve_context(ctx, input)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = (output_dir / input.name).resolve()
    request = ProcessingRequest(
        input_path=input.resolve(),
        output_path=output_path,
        params=params,
    )
    processor = _resolve_processor(settings, catalog, output_dir, dry_run)
    if dry_run:
        output_adapter.message("Dry run mode")
    result = processor.process_effect(name, request)
    output_adapter.process_result(result)


@process_app.command()
def composite(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Composite name"),
    input: Path = typer.Argument(..., help="Input image path"),
    output: Path | None = typer.Option(
        None, "-o", "--output", help="Output directory"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview commands only"),
    param: list[str] = typer.Option(
        [], "--param", help="Parameter overrides (key=value)"
    ),
    composite_name: str | None = typer.Option(
        None, "-c", "--composite", help="Composite name (overrides positional)"
    ),
) -> None:
    output_adapter = _get_output_adapter(ctx)
    name = composite_name or name
    output_dir = output or Path("/tmp/wallpaper-effects")
    params = _parse_params(param)
    settings, catalog = _resolve_context(ctx, input)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = (output_dir / input.name).resolve()
    request = ProcessingRequest(
        input_path=input.resolve(),
        output_path=output_path,
        params=params,
    )
    processor = _resolve_processor(settings, catalog, output_dir, dry_run)
    if dry_run:
        output_adapter.message("Dry run mode")
    result = processor.process_composite(name, request)
    output_adapter.process_result(result)


@process_app.command()
def preset(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Preset name"),
    input: Path = typer.Argument(..., help="Input image path"),
    output: Path | None = typer.Option(
        None, "-o", "--output", help="Output directory"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview commands only"),
    param: list[str] = typer.Option(
        [], "--param", help="Parameter overrides (key=value)"
    ),
    preset_name: str | None = typer.Option(
        None, "-p", "--preset", help="Preset name (overrides positional)"
    ),
) -> None:
    output_adapter = _get_output_adapter(ctx)
    name = preset_name or name
    output_dir = output or Path("/tmp/wallpaper-effects")
    params = _parse_params(param)
    settings, catalog = _resolve_context(ctx, input)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = (output_dir / input.name).resolve()
    request = ProcessingRequest(
        input_path=input.resolve(),
        output_path=output_path,
        params=params,
    )
    processor = _resolve_processor(settings, catalog, output_dir, dry_run)
    if dry_run:
        output_adapter.message("Dry run mode")
    result = processor.process_preset(name, request)
    output_adapter.process_result(result)
