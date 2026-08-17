from __future__ import annotations

import logging
import os
from pathlib import Path

import typer

from color_scheme_generator.cli._helpers import (
    default_app_settings,
    parse_params,
    resolve_backend_params,
)
from color_scheme_generator.cli.dump_config_cmd import dump_config
from color_scheme_generator.cli.dump_templates_cmd import dump_templates
from color_scheme_generator.cli.info_cmd import info
from color_scheme_generator.cli.install_cmd import install
from color_scheme_generator.cli.list_backends_cmd import list_backends
from color_scheme_generator.cli.options import (
    CONFIG_OPT,
    ENGINE_OPT,
    RUNTIME_OPT,
    TEMPLATES_DIR_OPT,
)
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
    create_template_catalog_loader,
    create_template_dir_resolver,
    create_template_renderer,
)

_xdg_config_home = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
_xdg_settings_path = Path(_xdg_config_home) / "color-scheme-generator" / "settings.toml"

app = typer.Typer(
    name="csg",
    help=(
        "Color Scheme Generator — extract color palettes from images.\n\n"
        "Configuration discovery (highest priority first):\n"
        "  Settings (settings.toml):\n"
        "    1. --config flag\n"
        "    2. COLORSCHEME_CONFIG_FILE_PATH env var\n"
        "    3. settings.toml in CWD or up to 3 parent levels\n"
        f"    4. XDG default: {_xdg_settings_path}\n"
        "    5. Package-bundled defaults\n"
        "  Templates directory:\n"
        "    1. COLORSCHEME_TEMPLATES_TEMPLATES_DIR env var\n"
        "    2. templates/ in CWD or up to 3 parent levels\n"
        "    3. XDG default\n"
        "    4. Package-bundled defaults\n\n"
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
        template_catalog_loader=create_template_catalog_loader(),
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
    if verbosity is not None:
        cli_overrides["output.verbosity"] = str(verbosity.value)

    ctx.obj = {
        "deps": deps,
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
    image_path: Path = typer.Argument(..., help="Path to the input image file"),
    config_path: Path | None = CONFIG_OPT,
    templates_dir: Path | None = TEMPLATES_DIR_OPT,
    runtime: RuntimeMode | None = RUNTIME_OPT,
    container_engine: ContainerEngine | None = ENGINE_OPT,
    backend: Backend | None = typer.Option(None, "--backend", help="Extraction backend"),
    param: list[str] = typer.Option([], "--param", help="Backend parameter overrides"),
    formats: list[ColorFormat] | None = typer.Option(
        None, "--format", "-f", help="Output formats"
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", "-o", help="Output directory"
    ),
) -> None:
    deps: CliDependencies = ctx.obj["deps"]
    try:
        cli_overrides = ctx.obj.get("cli_overrides", {})
        if runtime is not None:
            cli_overrides["runtime.mode"] = runtime.value
        if container_engine is not None:
            cli_overrides["container.engine"] = container_engine.value
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

    if templates_dir is not None and deps.template_renderer is not None:
        deps.template_renderer.update_templates_dir(str(templates_dir))

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
            default_formats = settings.output.default_formats
            if not default_formats and deps.template_catalog_loader is not None:
                catalog = deps.template_catalog_loader.load(explicit_dir=templates_dir)
                default_formats = tuple(t.format for t in catalog.templates)
            resolved_formats = tuple(
                ColorFormat(f) if isinstance(f, str) else f
                for f in default_formats
            )

        resolved_output_dir = output_dir or settings.output.directory

        config = GeneratorConfig(
            backend=resolved_backend,
            params=resolved_params,
            formats=resolved_formats,
            output_dir=resolved_output_dir,
        )
        request = GenerationRequest(image_path=image_path, config=config)
        effective_runtime = runtime or settings.runtime.mode
        if deps.processor is not None:
            processor = deps.processor
        elif effective_runtime == RuntimeMode.CONTAINER:
            engine_value = container_engine or settings.container.engine or ContainerEngine.DOCKER
            engine_obj = ContainerEngine(engine_value) if isinstance(engine_value, str) else engine_value
            container_runtime = create_container_engine(engine=engine_obj)
            processor = create_container_processor(
                container_runtime,
                template_dir_resolver=deps.template_dir_resolver,
                engine_value=engine_obj.value,
            )
        else:
            processor = create_local_processor(deps.backend_registry, deps.template_renderer)
        result = processor.process_generate(request, settings)
        # Apply the generated sequences to the live terminal (event-driven, no
        # shell polling): controlled by the apply_to_terminal SETTING (default
        # true). No CLI flag — the terminal_applier guards enforce the other
        # conditions (sequences produced this run + stdout is a TTY).
        if result.output_files and result.success and settings.output.apply_to_terminal:
            from color_scheme_generator.adapters.terminal_applier import apply_to_terminal as _apply

            _apply(result.output_files, True)
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
