from __future__ import annotations

from importlib.resources import files as resource_files
from pathlib import Path
from typing import Any

import typer

from wallpaper_effects_generator.domain.exceptions import (
    BinaryNotFoundError,
    ContainerRuntimeUnavailableError,
)
from wallpaper_effects_generator.factory import (
    create_command_runner,
    create_image_manager,
)
from wallpaper_effects_generator.ports.config_resolver import ConfigResolverPort
from wallpaper_effects_generator.ports.output import OutputPort


def install_command(
    config_resolver: ConfigResolverPort,
    output_adapter: OutputPort,
    config_path: str | None = None,
    dump_config: bool = False,
    dump_effects: bool = False,
) -> None:
    settings = config_resolver.resolve(explicit_path=Path(config_path) if config_path else None)
    image = _build_image_fqn(settings)

    try:
        runner = create_command_runner(settings)
    except BinaryNotFoundError as e:
        raise ContainerRuntimeUnavailableError(runtime=e.binary) from e

    mgr = create_image_manager(runner)
    mgr.pull(image)

    output_adapter.message(f"Container image installed: {image}")

    if dump_config:
        _dump_default_config()
    if dump_effects:
        _dump_default_effects()


def _build_image_fqn(settings: Any) -> str:
    registry = settings.container.image_registry.rstrip("/")
    tag = settings.container.image_tag
    return f"{registry}/weg-managed:{tag}"


def _dump_default_config() -> None:
    content = (
        resource_files("wallpaper_effects_generator.defaults")
        .joinpath("settings.toml")
        .read_text()
    )
    path = Path("settings.toml")
    if path.exists():
        typer.echo("settings.toml already exists (use --force to overwrite)")
        return
    path.write_text(content)
    typer.echo(f"Default config written to {path}")


def _dump_default_effects() -> None:
    content = (
        resource_files("wallpaper_effects_generator.defaults")
        .joinpath("effects.yaml")
        .read_text()
    )
    path = Path("effects.yaml")
    if path.exists():
        typer.echo("effects.yaml already exists (use --force to overwrite)")
        return
    path.write_text(content)
    typer.echo(f"Default effects written to {path}")
