from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from color_scheme_generator.adapters.backends.custom_generator import CustomGenerator
from color_scheme_generator.adapters.backends.pywal_generator import PywalGenerator
from color_scheme_generator.adapters.backends.wallust_generator import WallustGenerator
from color_scheme_generator.adapters.jinja_template_renderer import JinjaTemplateRenderer
from color_scheme_generator.adapters.settings.config_resolver import AssembledConfigResolver
from color_scheme_generator.adapters.template_dir_resolver import TemplateDirResolver
from color_scheme_generator.adapters.yaml_backend_catalog_loader import YamlBackendCatalogLoader
from color_scheme_generator.domain.enums import Backend, ContainerEngine, OutputFormat
from color_scheme_generator.ports.container_runtime import ContainerRuntimePort
from color_scheme_generator.ports.output import OutputPort
from color_scheme_generator.ports.palette_generator import PaletteGeneratorPort
from color_scheme_generator.ports.processor import ColorSchemeProcessorPort
from color_scheme_generator.ports.template_renderer import TemplateRendererPort

if TYPE_CHECKING:
    from pathlib import Path

    from color_scheme_generator.adapters.local_processor import LocalProcessor

BackendRegistry = dict[Backend, PaletteGeneratorPort]


@dataclass
class CliDependencies:
    backend_registry: BackendRegistry
    backend_catalog_loader: YamlBackendCatalogLoader | None = None
    config_resolver: AssembledConfigResolver | None = None
    container_engine: ContainerRuntimePort | None = None
    output_adapter: OutputPort | None = None
    processor: ColorSchemeProcessorPort | None = None
    template_dir_resolver: TemplateDirResolver | None = None
    template_renderer: TemplateRendererPort | None = None


def create_backend_registry() -> BackendRegistry:
    return {
        Backend.CUSTOM: CustomGenerator(),
        Backend.PYWAL: PywalGenerator(),
        Backend.WALLUST: WallustGenerator(),
    }


def create_backend_catalog_loader() -> YamlBackendCatalogLoader:
    return YamlBackendCatalogLoader()


def create_template_dir_resolver() -> TemplateDirResolver:
    return TemplateDirResolver()


def create_template_renderer() -> TemplateRendererPort:
    return JinjaTemplateRenderer(create_template_dir_resolver())


def create_config_resolver() -> AssembledConfigResolver:
    return AssembledConfigResolver()


def create_output_adapter(fmt: OutputFormat) -> OutputPort:
    from color_scheme_generator.adapters.output.json_output import JsonOutput
    from color_scheme_generator.adapters.output.plain_output import PlainOutput
    from color_scheme_generator.adapters.output.rich_output import RichOutput

    if fmt is OutputFormat.RICH:
        return RichOutput()
    if fmt is OutputFormat.PLAIN:
        return PlainOutput()
    return JsonOutput()


def create_local_processor(
    backend_registry: BackendRegistry,
    template_renderer: TemplateRendererPort | None = None,
) -> LocalProcessor:
    from color_scheme_generator.adapters.local_processor import LocalProcessor

    return LocalProcessor(backend_registry, template_renderer)


def create_container_engine(
    engine: ContainerEngine = ContainerEngine.DOCKER,
) -> ContainerRuntimePort:
    from oci_runtime.domain.enums import RuntimeKind
    from oci_runtime.domain.types import RuntimePreference
    from oci_runtime.factory import RuntimeFactory

    kind = RuntimeKind.DOCKER if engine is ContainerEngine.DOCKER else RuntimeKind.PODMAN
    runtime_engine = RuntimeFactory().create(RuntimePreference(kind=kind, binary=engine.value))
    from color_scheme_generator.adapters.oci_container_runtime import OciContainerRuntimeAdapter

    return OciContainerRuntimeAdapter(runtime_engine)


def create_container_processor(
    container_engine: ContainerRuntimePort,
    default_settings_path: Path | None = None,
) -> ColorSchemeProcessorPort:
    from color_scheme_generator.adapters.container_processor import ContainerProcessor

    return ContainerProcessor(container_engine, default_settings_path=default_settings_path)


def create_dry_run_processor() -> ColorSchemeProcessorPort:
    from color_scheme_generator.adapters.dry_run_processor import DryRunProcessor

    return DryRunProcessor()
