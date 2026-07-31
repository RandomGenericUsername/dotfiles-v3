from __future__ import annotations

import os
from importlib.resources import files as package_files
from pathlib import Path

import typer

from wallpaper_effects_generator.cli.batch import batch_app
from wallpaper_effects_generator.cli.dump_config import dump_config_command
from wallpaper_effects_generator.cli.dump_effects import dump_effects_command
from wallpaper_effects_generator.cli.info import info_command
from wallpaper_effects_generator.cli.install import install_command
from wallpaper_effects_generator.cli.options import CONFIG_OPT, EFFECTS_OPT, ENGINE_OPT
from wallpaper_effects_generator.cli.process import process_app
from wallpaper_effects_generator.cli.show import show_app
from wallpaper_effects_generator.cli.uninstall import uninstall_command
from wallpaper_effects_generator.cli.version_cmd import version_command
from wallpaper_effects_generator.constants import (
    CONFIG_FILENAME,
    CONFIG_TRAVERSAL_DEPTH,
    CONFIG_XDG_SUBDIR,
    EFFECTS_FILENAME,
    EFFECTS_TRAVERSAL_DEPTH,
    EFFECTS_XDG_SUBDIR,
)
from wallpaper_effects_generator.domain.enums import ContainerEngine, OutputFormat, Verbosity
from wallpaper_effects_generator.factory import (
    CliDependencies,
    create_config_resolver,
    create_effect_loader,
    create_output_adapter,
    create_version_provider,
)
from wallpaper_effects_generator.ports.output import OutputPort

_test_deps: CliDependencies | None = None

_xdg_config_home = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
_xdg_settings_path = Path(_xdg_config_home) / CONFIG_XDG_SUBDIR / CONFIG_FILENAME
_xdg_effects_path = Path(_xdg_config_home) / EFFECTS_XDG_SUBDIR / EFFECTS_FILENAME

app = typer.Typer(
    name="weg",
    help=(
        "Wallpaper Effects Generator — apply effects to wallpapers.\n\n"
        "Configuration discovery (highest priority first):\n"
        "  Settings (settings.toml):\n"
        "    1. WALLPAPER_CONFIG_FILE_PATH env var\n"
        f"    2. {CONFIG_FILENAME} in CWD or up to {CONFIG_TRAVERSAL_DEPTH} parent levels\n"
        f"    3. XDG default: {_xdg_settings_path}\n"
        "    4. Package-bundled defaults\n"
        "  Effects (effects.yaml):\n"
        "    1. WALLPAPER_EFFECTS_CONFIG_FILE_PATH env var\n"
        f"    2. {EFFECTS_FILENAME} in CWD or up to {EFFECTS_TRAVERSAL_DEPTH} parent levels\n"
        f"    3. XDG default: {_xdg_effects_path}\n"
        "    4. Package-bundled defaults\n\n"
        f"ENV overrides: WALLPAPER__SECTION__KEY=value (double underscore = nesting)"
    ),
)


@app.callback()
def main(
    ctx: typer.Context,
    output_format: OutputFormat = typer.Option(
        OutputFormat.JSON,
        "--output-format",
        help="Output format for command results",
        case_sensitive=False,
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress all non-error output",
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
    ctx.obj["output_format"] = output_format
    if quiet:
        ctx.obj["verbosity"] = Verbosity.QUIET
    else:
        match verbose:
            case 0:
                ctx.obj["verbosity"] = Verbosity.NORMAL
            case 1:
                ctx.obj["verbosity"] = Verbosity.VERBOSE
            case _:
                ctx.obj["verbosity"] = Verbosity.DEBUG
    defaults_dir = package_files("wallpaper_effects_generator") / "defaults"
    deps = CliDependencies(
        config_resolver=create_config_resolver(
            default_settings_path=defaults_dir / "settings.toml"
        ),
        effect_loader=create_effect_loader(default_effects_path=defaults_dir / "effects.yaml"),
    )
    deps.output_adapter = create_output_adapter(output_format)
    if os.environ.get("WEG_TEST_DEPS") and _test_deps is not None:
        deps = _test_deps
    ctx.obj["deps"] = deps


def set_test_deps(deps: CliDependencies) -> None:
    global _test_deps
    _test_deps = deps
    os.environ["WEG_TEST_DEPS"] = "1"


def _get_output_adapter(
    ctx: typer.Context, default: OutputFormat = OutputFormat.JSON
) -> OutputPort:
    deps = ctx.obj["deps"]
    if deps.output_adapter is not None:
        return deps.output_adapter
    adapter = create_output_adapter(default)
    deps.output_adapter = adapter
    return adapter


@app.command(help="Show resolved configuration, catalog, and source paths")
def info(
    ctx: typer.Context,
    config_path: Path | None = CONFIG_OPT,
    effects_path: Path | None = EFFECTS_OPT,
) -> None:
    output_adapter = _get_output_adapter(ctx)
    deps = ctx.obj["deps"]
    info_command(
        config_path=str(config_path) if config_path else None,
        effects_path=str(effects_path) if effects_path else None,
        output_adapter=output_adapter,
        config_resolver=deps.config_resolver,
        effect_loader=deps.effect_loader,
        catalog_cache=deps.catalog_cache,
        cli_overrides=None,
    )


@app.command(name="dump-config", help="Print the packaged default settings.toml template")
def dump_config(
    ctx: typer.Context,
    output: Path | None = typer.Option(None, "--output", help="Write default config to path"),
) -> None:
    message_adapter = _get_output_adapter(ctx)
    dump_config_command(
        output_adapter=message_adapter,
        output_path=output,
    )


@app.command(name="dump-effects", help="Print the packaged default effects.yaml template")
def dump_effects(
    ctx: typer.Context,
    output: Path | None = typer.Option(None, "--output", help="Write default effects to path"),
) -> None:
    message_adapter = _get_output_adapter(ctx)
    dump_effects_command(
        output_adapter=message_adapter,
        output_path=output,
    )


@app.command(help="Print wallpaper-effects-generator version")
def version(ctx: typer.Context) -> None:
    output_adapter = _get_output_adapter(ctx)
    version_command(ctx, create_version_provider(), output_adapter)


@app.command(help="Build and install the container image")
def install(
    ctx: typer.Context,
    config_path: Path | None = CONFIG_OPT,
    container_engine: ContainerEngine | None = ENGINE_OPT,
    dump_config: bool = typer.Option(False, "--dump-config", help="Write default settings.toml"),
    dump_effects: bool = typer.Option(False, "--dump-effects", help="Write default effects.yaml"),
) -> None:
    deps = ctx.obj["deps"]
    install_command(
        config_resolver=deps.config_resolver,
        output_adapter=_get_output_adapter(ctx),
        config_path=str(config_path) if config_path else None,
        dump_config=dump_config,
        dump_effects=dump_effects,
        container_engine=container_engine,
    )


@app.command(help="Remove the installed container image")
def uninstall(
    ctx: typer.Context,
    config_path: Path | None = CONFIG_OPT,
    container_engine: ContainerEngine | None = ENGINE_OPT,
) -> None:
    deps = ctx.obj["deps"]
    uninstall_command(
        config_resolver=deps.config_resolver,
        output_adapter=_get_output_adapter(ctx),
        config_path=str(config_path) if config_path else None,
        container_engine=container_engine,
    )


app.add_typer(process_app)
app.add_typer(show_app)
app.add_typer(batch_app)


if __name__ == "__main__":
    app()
