from __future__ import annotations

from importlib.resources import files as resource_files
from pathlib import Path

from oci_runtime import BuildContext, RuntimeKind, RuntimePreference

from wallpaper_effects_generator.domain.exceptions import (
    BinaryNotFoundError,
    ContainerRuntimeUnavailableError,
)
from wallpaper_effects_generator.factory import create_container_engine
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
    image_name = _build_image_name(settings.container)
    engine = create_container_engine(settings.container)

    if not engine.is_available():
        raise ContainerRuntimeUnavailableError(runtime=settings.container.engine)

    df_path = (
        resource_files("wallpaper_effects_generator.adapters.docker")
        .joinpath("Dockerfile.imagemagick")
    )
    repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent

    output_adapter.message(f"Building container image {image_name}...")
    image_id = engine.images.build(
        BuildContext(build_file_path=str(df_path), context_path=str(repo_root)),
        image_name,
    )
    output_adapter.message(f"Image built: {image_id}")
    output_adapter.message(f"Container image installed: {image_name}")

    if dump_config:
        _dump_default_config()
    if dump_effects:
        _dump_default_effects()


def _build_image_name(container_settings: object) -> str:
    registry = getattr(container_settings, "image_registry", "") or ""
    name = getattr(container_settings, "image_name", "weg")
    tag = getattr(container_settings, "image_tag", "latest")
    registry = registry.rstrip("/")
    if registry:
        return f"{registry}/{name}:{tag}"
    return f"{name}:{tag}"


def _dump_default_config() -> None:
    content = (
        resource_files("wallpaper_effects_generator.defaults")
        .joinpath("settings.toml")
        .read_text()
    )
    path = Path("settings.toml")
    if path.exists():
        path = Path("settings.toml")
    path.write_text(content)


def _dump_default_effects() -> None:
    content = (
        resource_files("wallpaper_effects_generator.defaults")
        .joinpath("effects.yaml")
        .read_text()
    )
    path = Path("effects.yaml")
    if path.exists():
        path = Path("effects.yaml")
    path.write_text(content)
