from __future__ import annotations

from importlib.resources import files as package_files
from pathlib import Path

import typer

from wallpaper_effects_generator.cli.batch import batch_app
from wallpaper_effects_generator.cli.dump_config import dump_config_command
from wallpaper_effects_generator.cli.dump_effects import dump_effects_command
from wallpaper_effects_generator.cli.info import info_command
from wallpaper_effects_generator.cli.install import install_command
from wallpaper_effects_generator.cli.process import process_app
from wallpaper_effects_generator.cli.show import show_app
from wallpaper_effects_generator.cli.uninstall import uninstall_command
from wallpaper_effects_generator.cli.version_cmd import version_command
from wallpaper_effects_generator.domain.enums import ContainerEngine, OutputFormat, RuntimeMode, Verbosity
from wallpaper_effects_generator.factory import (
    CliDependencies,
    create_config_resolver,
    create_effect_loader,
    create_output_adapter,
    create_version_provider,
)
from wallpaper_effects_generator.ports.output import OutputPort

app = typer.Typer(
    name="weg",
    help="Wallpaper Effects Generator — apply effects to wallpapers",
)


@app.callback()
def main(
    ctx: typer.Context,
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to settings.toml",
    ),
    effects: Path | None = typer.Option(
        None,
        "--effects",
        "-e",
        help="Path to effects.yaml",
    ),
    runtime: str | None = typer.Option(
        None,
        "--runtime",
        "-r",
        help="Runtime mode (local/container)",
    ),
    container_engine: str | None = typer.Option(
        None,
        "--container-engine",
        help="Container engine (docker/podman)",
    ),
    output_format: str = typer.Option(
        "json",
        "--output-format",
        help="Output format (json/rich/plain)",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress output",
    ),
    verbose: int = typer.Option(
        0,
        "--verbose",
        "-v",
        count=True,
        help="Increase verbosity (use -v, -vv, -vvv)",
    ),
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["config"] = str(config) if config else None
    ctx.obj["effects"] = str(effects) if effects else None
    try:
        output_fmt = OutputFormat(output_format)
    except ValueError:
        valid = ", ".join(f"'{f.value}'" for f in OutputFormat)
        raise typer.BadParameter(
            f"Invalid value '{output_format}'. Choose from: {valid}"
        )
    ctx.obj["output_format"] = output_fmt
    if runtime is not None:
        try:
            ctx.obj["runtime"] = RuntimeMode(runtime)
        except ValueError:
            valid = ", ".join(m.value for m in RuntimeMode)
            raise typer.BadParameter(
                f"Invalid --runtime '{runtime}'. Choose from: {valid}"
            )
    else:
        ctx.obj["runtime"] = None
    if container_engine is not None:
        try:
            ctx.obj["container_engine"] = ContainerEngine(container_engine)
        except ValueError:
            valid = ", ".join(m.value for m in ContainerEngine)
            raise typer.BadParameter(
                f"Invalid --container-engine '{container_engine}'. Choose from: {valid}"
            )
    else:
        ctx.obj["container_engine"] = None
    if quiet:
        ctx.obj["verbosity"] = Verbosity.QUIET
    else:
        match verbose:
            case 0: ctx.obj["verbosity"] = Verbosity.NORMAL
            case 1: ctx.obj["verbosity"] = Verbosity.VERBOSE
            case _: ctx.obj["verbosity"] = Verbosity.DEBUG
    defaults_dir = package_files("wallpaper_effects_generator") / "defaults"
    deps = CliDependencies(
        config_resolver=create_config_resolver(
            default_settings_path=defaults_dir / "settings.toml"
        ),
        effect_loader=create_effect_loader(
            default_effects_path=defaults_dir / "effects.yaml"
        ),
    )
    deps.output_adapter = create_output_adapter(output_fmt)
    ctx.obj["deps"] = deps


def _get_output_adapter(ctx: typer.Context) -> OutputPort:
    return ctx.obj["deps"].output_adapter


@app.command()
def info(ctx: typer.Context) -> None:
    output_adapter = _get_output_adapter(ctx)
    deps = ctx.obj["deps"]
    info_command(
        config_path=ctx.obj["config"],
        effects_path=ctx.obj["effects"],
        output_adapter=output_adapter,
        config_resolver=deps.config_resolver,
        effect_loader=deps.effect_loader,
        catalog_cache=deps.catalog_cache,
    )


@app.command(name="dump-config")
def dump_config(
    ctx: typer.Context,
    output: Path | None = typer.Option(None, "--output", help="Write default config to path"),
) -> None:
    output_adapter = _get_output_adapter(ctx)
    deps = ctx.obj["deps"]
    dump_config_command(
        config_path=ctx.obj["config"],
        output_adapter=output_adapter,
        config_resolver=deps.config_resolver,
        output_path=output,
    )


@app.command(name="dump-effects")
def dump_effects(
    ctx: typer.Context,
    output: Path | None = typer.Option(None, "--output", help="Write default effects to path"),
) -> None:
    output_adapter = _get_output_adapter(ctx)
    deps = ctx.obj["deps"]
    dump_effects_command(
        effects_path=ctx.obj["effects"],
        output_adapter=output_adapter,
        effect_loader=deps.effect_loader,
        output_path=output,
    )


@app.command()
def version(ctx: typer.Context) -> None:
    version_command(ctx, create_version_provider())


@app.command()
def install(
    ctx: typer.Context,
    dump_config: bool = typer.Option(False, "--dump-config", help="Write default settings.toml"),
    dump_effects: bool = typer.Option(False, "--dump-effects", help="Write default effects.yaml"),
) -> None:
    deps = ctx.obj["deps"]
    install_command(
        config_resolver=deps.config_resolver,
        output_adapter=deps.output_adapter,
        config_path=ctx.obj.get("config"),
        dump_config=dump_config,
        dump_effects=dump_effects,
    )


@app.command()
def uninstall(ctx: typer.Context) -> None:
    deps = ctx.obj["deps"]
    uninstall_command(
        config_resolver=deps.config_resolver,
        output_adapter=deps.output_adapter,
        config_path=ctx.obj.get("config"),
    )


app.add_typer(process_app)
app.add_typer(show_app)
app.add_typer(batch_app)


if __name__ == "__main__":
    app()
