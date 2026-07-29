from __future__ import annotations

import logging
import os
from pathlib import Path

import typer

from color_scheme_generator.adapters.local_processor import LocalProcessor
from color_scheme_generator.cli._helpers import (
    default_app_settings,
    parse_params,
    resolve_backend_params,
    resolve_container_engine,
)
from color_scheme_generator.cli.dump_config_cmd import dump_config
from color_scheme_generator.cli.dump_templates_cmd import dump_templates
from color_scheme_generator.cli.info_cmd import info
from color_scheme_generator.cli.install_cmd import install
from color_scheme_generator.cli.list_backends_cmd import list_backends
from color_scheme_generator.cli.show import show
from color_scheme_generator.cli.uninstall_cmd import uninstall
from color_scheme_generator.cli.version_cmd import version
from color_scheme_generator.domain.enums import (
    Backend,
    ColorFormat,
    ContainerEngine,
    OutputFormat,
    RuntimeMode,
    Verbosity,
)
from color_scheme_generator.domain.exceptions import ColorSchemeError
from color_scheme_generator.domain.models import (
    GenerationRequest,
    GeneratorConfig,
)
from color_scheme_generator.factory import (
    CliDependencies,
    create_backend_catalog_loader,
    create_backend_registry,
    create_config_resolver,
    create_container_engine,
    create_container_processor,
    create_local_processor,
    create_output_adapter,
    create_template_dir_resolver,
    create_template_renderer,
)

_xdg_config_home = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
_xdg_settings_path = Path(_xdg_config_home) / "color-scheme-generator" / "settings.toml"
_xdg_templates_path = Path(_xdg_config_home) / "color-scheme" / "templates"

app = typer.Typer(
    name="csg",
    help=(
        "Color Scheme Generator — extract color palettes from images.\n\n"
        "Configuration discovery (highest priority first):\n"
        "  Settings (settings.toml):\n"
        "    1. Explicit --config flag\n"
        "    2. COLORSCHEME_CONFIG_FILE_PATH env var\n"
        "    3. settings.toml in CWD or up to 3 parent levels\n"
        f"    4. XDG default: {_xdg_settings_path}\n"
        "    5. Package-bundled defaults\n"
        "  Templates directory:\n"
        "    1. Explicit --templates-dir flag\n"
        "    2. COLORSCHEME_TEMPLATES_TEMPLATES_DIR env var\n"
        "    3. templates/ in CWD or up to 3 parent levels\n"
        f"    4. XDG default: {_xdg_templates_path}\n"
        "    5. Package-bundled defaults\n\n"
        "ENV overrides: COLORSCHEME__SECTION__KEY=value (double underscore = nesting)"
    ),
)


def build_deps() -> CliDependencies:
    registry = create_backend_registry()
    renderer = create_template_renderer()
    return CliDependencies(
        backend_registry=registry,
        backend_catalog_loader=create_backend_catalog_loader(),
        config_resolver=create_config_resolver(),
        processor=LocalProcessor(registry, renderer),
        template_dir_resolver=create_template_dir_resolver(),
        template_renderer=renderer,
    )


@app.callback()
def main_callback(
    ctx: typer.Context,
    output_format: OutputFormat = typer.Option(  # noqa: B008
        OutputFormat.JSON,
        "--output-format",
        help="Output format for command results",
        case_sensitive=False,
    ),
    runtime: RuntimeMode = typer.Option(  # noqa: B008
        RuntimeMode.LOCAL,
        "--runtime",
        help="Execution runtime mode",
        case_sensitive=False,
    ),
    container_engine: ContainerEngine | None = typer.Option(  # noqa: B008
        None,
        "--container-engine",
        help="Container engine to use (only for container runtime)",
        case_sensitive=False,
    ),
    config_path: Path | None = typer.Option(  # noqa: B008
        None,
        "--config",
        help="Path to settings.toml config file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    ),
    templates_dir: Path | None = typer.Option(  # noqa: B008
        None,
        "--templates-dir",
        help="Path to directory containing .j2 template files",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
    ),
    verbose: int = typer.Option(  # noqa: B008
        0,
        "--verbose",
        "-v",
        count=True,
        help="Increase verbosity (use -v, -vv, -vvv)",
    ),
    quiet: bool = typer.Option(  # noqa: B008
        False,
        "--quiet",
        "-q",
        help="Suppress all non-error output",
    ),
) -> None:
    deps = build_deps()

    if quiet:
        verbosity = Verbosity.QUIET
    elif verbose > 0:
        match verbose:
            case 1: verbosity = Verbosity.VERBOSE
            case _: verbosity = Verbosity.DEBUG
    else:
        verbosity = None  # use TOML default

    cli_overrides = {}
    if templates_dir is not None:
        cli_overrides["template.templates_dir"] = str(templates_dir)
    if verbosity is not None:
        cli_overrides["output.verbosity"] = str(verbosity.value)
    if container_engine is not None:
        cli_overrides["container.engine"] = container_engine.value

    if runtime is RuntimeMode.LOCAL and deps.processor is None:
        deps.processor = create_local_processor(deps.backend_registry, deps.template_renderer)
    elif runtime is RuntimeMode.CONTAINER:
        engine = resolve_container_engine(container_engine, deps.config_resolver, config_path, cli_overrides)
        container_runtime = create_container_engine(engine=engine)
        deps.container_engine = container_runtime
        deps.processor = create_container_processor(
            container_runtime, template_dir_resolver=deps.template_dir_resolver
        )

    ctx.obj = {
        "deps": deps,
        "config_path": str(config_path) if config_path else None,
        "container_engine": container_engine,
        "cli_overrides": cli_overrides,
        "verbosity": verbosity,
    }

    effective_verbosity = verbosity if verbosity is not None else Verbosity.NORMAL
    log_level = {
        Verbosity.QUIET: logging.ERROR,
        Verbosity.NORMAL: logging.WARNING,
        Verbosity.VERBOSE: logging.INFO,
        Verbosity.DEBUG: logging.DEBUG,
    }[effective_verbosity]
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    ctx.obj["deps"].output_adapter = create_output_adapter(
        output_format,
        verbosity=verbosity if verbosity is not None else Verbosity.NORMAL,
    )


@app.command(help="Extract a color palette from an image")
def generate(
    ctx: typer.Context,
    image_path: Path = typer.Argument(..., help="Path to the input image file"),  # noqa: B008
    backend: Backend | None = typer.Option(None, "--backend", help="Extraction backend"),  # noqa: B008
    param: list[str] = typer.Option([], "--param", help="Backend parameter overrides"),  # noqa: B008
    formats: list[ColorFormat] | None = typer.Option(  # noqa: B008
        None, "--format", "-f", help="Output formats"
    ),
    output_dir: Path | None = typer.Option(  # noqa: B008
        None, "--output-dir", "-o", help="Output directory"
    ),
) -> None:
    deps: CliDependencies = ctx.obj["deps"]
    try:
        config_path = ctx.obj.get("config_path")
        cli_overrides = ctx.obj.get("cli_overrides", {})
        settings = (
            deps.config_resolver.resolve(
                explicit_path=config_path, cli_overrides=cli_overrides
            )
            if deps.config_resolver
            else default_app_settings()
        )
    except ColorSchemeError:
        typer.echo("Warning: config resolution failed, using defaults", err=True)
        settings = default_app_settings()

    if ctx.obj.get("verbosity") is None and deps.output_adapter is not None:
        settings_verbosity = settings.output.verbosity
        deps.output_adapter._verbosity = settings_verbosity
        logging.getLogger().setLevel({
            Verbosity.QUIET: logging.ERROR,
            Verbosity.NORMAL: logging.WARNING,
            Verbosity.VERBOSE: logging.INFO,
            Verbosity.DEBUG: logging.DEBUG,
        }[settings_verbosity])

    if settings.template.templates_dir is not None and deps.template_renderer is not None:
        deps.template_renderer.update_templates_dir(settings.template.templates_dir)

    try:
        raw_params = parse_params(param)

        resolved_backend = backend or settings.generation.backend or Backend.CUSTOM

        resolved_params = resolve_backend_params(
            raw_params, resolved_backend, deps.backend_catalog_loader
        )

        resolved_formats: tuple[ColorFormat, ...]
        if formats is not None:
            resolved_formats = tuple(
                ColorFormat(f) if isinstance(f, str) else f for f in formats
            )
        else:
            resolved_formats = tuple(
                ColorFormat(f) if isinstance(f, str) else f
                for f in settings.output.default_formats
            )

        resolved_output_dir = output_dir or settings.output.directory

        config = GeneratorConfig(
            backend=resolved_backend,
            params=resolved_params,
            formats=resolved_formats,
            output_dir=resolved_output_dir,
        )
        request = GenerationRequest(image_path=image_path, config=config)
        result = deps.processor.process_generate(request, settings)
        deps.output_adapter.process_result(result)
    except ColorSchemeError as exc:
        deps.output_adapter.error(exc)
        raise typer.Exit(code=1) from None
    except Exception:
        import json as _json
        import sys
        print(_json.dumps({"error": "unexpected error"}), file=sys.stderr)
        raise typer.Exit(code=1) from None


app.command(help="Show system configuration, backends, and sources")(info)
app.command(help="Print or save current settings to a TOML file")(dump_config)
app.command(help="Copy bundled Jinja2 templates to a local directory")(dump_templates)
app.command(help="Build container images for extraction backends")(install)
app.command(help="List available extraction backends and their status")(list_backends)
app.command(help="Display a color palette preview in the terminal")(show)
app.command(help="Remove container images for extraction backends")(uninstall)
app.command(help="Show the installed package version")(version)
