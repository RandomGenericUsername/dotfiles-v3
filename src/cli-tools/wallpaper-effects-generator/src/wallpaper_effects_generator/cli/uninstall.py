from __future__ import annotations

from pathlib import Path
from typing import Any

from wallpaper_effects_generator.domain.exceptions import (
    BinaryNotFoundError,
    ContainerImageNotFoundError,
    ContainerRuntimeUnavailableError,
)
from wallpaper_effects_generator.factory import (
    create_command_runner,
    create_image_manager,
)
from wallpaper_effects_generator.ports.config_resolver import ConfigResolverPort
from wallpaper_effects_generator.ports.output import OutputPort


def uninstall_command(
    config_resolver: ConfigResolverPort,
    output_adapter: OutputPort,
    config_path: str | None = None,
) -> None:
    settings = config_resolver.resolve(explicit_path=Path(config_path) if config_path else None)
    image = _build_image_fqn(settings)

    try:
        runner = create_command_runner(settings)
    except BinaryNotFoundError as e:
        raise ContainerRuntimeUnavailableError(runtime=e.binary) from e

    mgr = create_image_manager(runner)
    try:
        mgr.remove(image)
    except ContainerImageNotFoundError:
        output_adapter.message(f"Image not found — nothing to uninstall: {image}")
        return

    output_adapter.message(f"Container image removed: {image}")


def _build_image_fqn(settings: Any) -> str:
    registry = settings.container.image_registry.rstrip("/")
    tag = settings.container.image_tag
    return f"{registry}/weg-managed:{tag}"
