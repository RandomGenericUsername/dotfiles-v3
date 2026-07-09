from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console

from wallpaper_effects_generator.adapters.assembled_config_resolver import (
    AssembledConfigResolver,
)
from wallpaper_effects_generator.adapters.catalog_cache import CatalogCache
from wallpaper_effects_generator.adapters.container_processor import (
    ContainerProcessor,
)
from wallpaper_effects_generator.adapters.context_validator import (
    InputContextValidator,
)
from wallpaper_effects_generator.adapters.docker_image_manager import (
    DockerImageManager,
)
from wallpaper_effects_generator.adapters.dry_run_processor import DryRunProcessor
from wallpaper_effects_generator.adapters.importlib_version_provider import (
    ImportlibVersionProvider,
)
from wallpaper_effects_generator.adapters.local_processor import LocalProcessor
from wallpaper_effects_generator.adapters.oci_command_runner import OCICommandRunner
from wallpaper_effects_generator.adapters.output.json_output import JsonOutputAdapter
from wallpaper_effects_generator.adapters.output.plain_output import PlainOutputAdapter
from wallpaper_effects_generator.adapters.output.rich_output import RichOutputAdapter
from wallpaper_effects_generator.adapters.subprocess_runner import (
    SubprocessCommandRunner,
)
from wallpaper_effects_generator.adapters.yaml_effect_loader import YamlEffectLoader
from wallpaper_effects_generator.domain.enums import OutputFormat, RuntimeMode
from wallpaper_effects_generator.domain.models import (
    AppSettings,
    ContainerSettings,
    EffectsCatalog,
)
from wallpaper_effects_generator.ports.command_runner import CommandRunnerPort
from wallpaper_effects_generator.ports.config_resolver import ConfigResolverPort
from wallpaper_effects_generator.ports.context_validator import (
    ContextValidatorPort,
)
from wallpaper_effects_generator.ports.effect_loader import EffectLoaderPort
from wallpaper_effects_generator.ports.image_manager import ImageManagerPort
from wallpaper_effects_generator.ports.output import OutputPort
from wallpaper_effects_generator.ports.processor import EffectProcessorPort
from wallpaper_effects_generator.ports.version_provider import VersionProviderPort


@dataclass
class CliDependencies:
    config_resolver: ConfigResolverPort = field(default_factory=AssembledConfigResolver)
    effect_loader: EffectLoaderPort = field(default_factory=YamlEffectLoader)
    catalog_cache: CatalogCache | None = None
    output_adapter: OutputPort | None = None
    context_validator: ContextValidatorPort | None = None
    command_runner: CommandRunnerPort | None = None

    def __post_init__(self) -> None:
        if self.catalog_cache is None:
            self.catalog_cache = CatalogCache(self.effect_loader)


def create_config_resolver(
    default_settings_path: Path | None = None,
) -> ConfigResolverPort:
    return AssembledConfigResolver(default_settings_path=default_settings_path)


def create_effect_loader(
    default_effects_path: Path | None = None,
) -> EffectLoaderPort:
    return YamlEffectLoader(default_effects_path=default_effects_path)


def create_command_runner(
    settings: AppSettings,
) -> CommandRunnerPort:
    if settings.runtime.mode == RuntimeMode.CONTAINER:
        return create_oci_command_runner(settings)
    return SubprocessCommandRunner(binary=settings.backend.binary)


def create_oci_command_runner(settings: AppSettings) -> CommandRunnerPort:
    return OCICommandRunner(engine=settings.container.engine)


def create_image_manager(command_runner: CommandRunnerPort) -> ImageManagerPort:
    return DockerImageManager(command_runner=command_runner)


def create_local_processor(
    command_runner: CommandRunnerPort,
    catalog: EffectsCatalog,
    output_dir: Path,
) -> EffectProcessorPort:
    return LocalProcessor(
        command_runner=command_runner,
        catalog=catalog,
        output_dir=output_dir,
    )


def create_dry_run_processor(
    command_runner: CommandRunnerPort,
    catalog: EffectsCatalog,
    output_dir: Path,
) -> EffectProcessorPort:
    return DryRunProcessor(
        command_runner=command_runner,
        catalog=catalog,
        output_dir=output_dir,
    )


def create_container_processor(
    command_runner: CommandRunnerPort,
    catalog: EffectsCatalog,
    output_dir: Path,
    container_settings: ContainerSettings | None = None,
    settings: AppSettings | None = None,
    context_validator: ContextValidatorPort | None = None,
) -> EffectProcessorPort:
    return ContainerProcessor(
        command_runner=command_runner,
        catalog=catalog,
        output_dir=output_dir,
        container_settings=container_settings,
        settings=settings,
        context_validator=context_validator,
    )


def create_output_adapter(
    output_format: OutputFormat,
    console: Console | None = None,
) -> OutputPort:
    if output_format == OutputFormat.JSON:
        return JsonOutputAdapter()
    if output_format == OutputFormat.RICH:
        return RichOutputAdapter(console=console)
    if output_format == OutputFormat.PLAIN:
        return PlainOutputAdapter()
    raise ValueError(f"Unsupported output format: {output_format}")


def create_version_provider() -> VersionProviderPort:
    return ImportlibVersionProvider()


def create_context_validator(
    command_runner: CommandRunnerPort,
    image_manager: ImageManagerPort | None = None,
) -> ContextValidatorPort:
    return InputContextValidator(
        command_runner=command_runner,
        image_manager=image_manager,
    )


def create_catalog_cache(loader: EffectLoaderPort) -> CatalogCache:
    return CatalogCache(loader=loader)
