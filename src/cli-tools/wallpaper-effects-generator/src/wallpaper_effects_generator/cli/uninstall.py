from __future__ import annotations

from pathlib import Path

from wallpaper_effects_generator.domain.enums import ContainerEngine
from wallpaper_effects_generator.domain.exceptions import (
    ContainerRuntimeUnavailableError,
)
from wallpaper_effects_generator.domain.models import AppSettings, ContainerSettings
from wallpaper_effects_generator.factory import create_container_engine
from wallpaper_effects_generator.ports.config_resolver import ConfigResolverPort
from wallpaper_effects_generator.ports.output import OutputPort


def uninstall_command(
    config_resolver: ConfigResolverPort,
    output_adapter: OutputPort,
    config_path: str | None = None,
    container_engine: ContainerEngine | None = None,
) -> None:
    settings = config_resolver.resolve(explicit_path=Path(config_path) if config_path else None)
    if container_engine is not None:
        container = ContainerSettings(
            engine=container_engine.value,
            image_name=settings.container.image_name,
            image_tag=settings.container.image_tag,
            image_registry=settings.container.image_registry,
        )
        settings = AppSettings(
            version=settings.version,
            execution=settings.execution,
            output=settings.output,
            processing=settings.processing,
            backend=settings.backend,
            runtime=settings.runtime,
            container=container,
        )
    image = _build_image_name(settings.container)
    engine = create_container_engine(settings.container)

    if not engine.is_available():
        raise ContainerRuntimeUnavailableError(runtime=settings.container.engine)

    if engine.images.exists(image):
        engine.images.remove(image)
        output_adapter.message(f"Container image removed: {image}")
    else:
        output_adapter.message(f"Image not found — nothing to uninstall: {image}")


def _build_image_name(container_settings: object) -> str:
    registry = getattr(container_settings, "image_registry", "") or ""
    name = getattr(container_settings, "image_name", "weg")
    tag = getattr(container_settings, "image_tag", "latest")
    registry = registry.rstrip("/")
    if registry:
        return f"{registry}/{name}:{tag}"
    return f"{name}:{tag}"
