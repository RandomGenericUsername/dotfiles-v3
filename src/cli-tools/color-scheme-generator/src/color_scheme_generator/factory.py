from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from color_scheme_generator.adapters.backends.custom_generator import CustomGenerator
from color_scheme_generator.adapters.backends.pywal_generator import PywalGenerator
from color_scheme_generator.adapters.backends.wallust_generator import WallustGenerator
from color_scheme_generator.adapters.jinja_template_renderer import JinjaTemplateRenderer
from color_scheme_generator.adapters.settings.config_resolver import AssembledConfigResolver
from color_scheme_generator.adapters.template_catalog_loader import DirectoryTemplateCatalogLoader
from color_scheme_generator.adapters.template_dir_resolver import TemplateDirResolver
from color_scheme_generator.adapters.yaml_backend_catalog_loader import YamlBackendCatalogLoader
from color_scheme_generator.domain.enums import Backend, ContainerEngine, OutputFormat, Verbosity
from color_scheme_generator.ports.container_runtime import ContainerRuntimePort
from color_scheme_generator.ports.output import OutputPort
from color_scheme_generator.ports.palette_generator import PaletteGeneratorPort
from color_scheme_generator.ports.processor import ColorSchemeProcessorPort
from color_scheme_generator.ports.template_catalog_loader import TemplateCatalogLoaderPort
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
    template_catalog_loader: TemplateCatalogLoaderPort | None = None
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


def create_template_catalog_loader() -> TemplateCatalogLoaderPort:
    return DirectoryTemplateCatalogLoader(create_template_dir_resolver())


def create_template_renderer() -> TemplateRendererPort:
    return JinjaTemplateRenderer(create_template_dir_resolver())


def create_config_resolver() -> AssembledConfigResolver:
    return AssembledConfigResolver()


def create_output_adapter(
    fmt: OutputFormat,
    verbosity: Verbosity = Verbosity.NORMAL,
) -> OutputPort:
    from cli_output.adapters.factory import create_renderer
    from cli_output.domain.enums import OutputFormat as SharedOutputFormat

    from color_scheme_generator.adapters.output.json_output import JsonOutput
    from color_scheme_generator.adapters.output.plain_output import PlainOutput
    from color_scheme_generator.adapters.output.rich_output import RichOutput

    renderer = create_renderer(SharedOutputFormat(fmt.value))
    if fmt is OutputFormat.RICH:
        return RichOutput(verbosity=verbosity, renderer=renderer)
    if fmt is OutputFormat.PLAIN:
        return PlainOutput(verbosity=verbosity, renderer=renderer)
    return JsonOutput(verbosity=verbosity, renderer=renderer)


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

    from color_scheme_generator.domain.exceptions import ContainerRuntimeUnavailableError

    kind = RuntimeKind.DOCKER if engine is ContainerEngine.DOCKER else RuntimeKind.PODMAN
    try:
        runtime_engine = RuntimeFactory().create(RuntimePreference(kind=kind, binary=engine.value))
    except Exception as exc:
        raise ContainerRuntimeUnavailableError(runtime=engine.value) from exc
    from color_scheme_generator.adapters.oci_container_runtime import OciContainerRuntimeAdapter

    return OciContainerRuntimeAdapter(runtime_engine)


def create_container_processor(
    container_engine: ContainerRuntimePort,
    template_dir_resolver: TemplateDirResolver | None = None,
    default_settings_path: Path | None = None,
    engine_value: str | None = None,
    templates_dir: Path | str | None = None,
) -> ColorSchemeProcessorPort:
    from color_scheme_generator.adapters.container_processor import ContainerProcessor

    return ContainerProcessor(
        container_engine,
        template_dir_resolver=template_dir_resolver,
        default_settings_path=default_settings_path,
        engine_value=engine_value,
        templates_dir=templates_dir,
    )


def create_dry_run_processor(
    backend_catalog_loader: YamlBackendCatalogLoader,
    output_adapter: OutputPort | None = None,
    container_runtime: ContainerRuntimePort | None = None,
    template_dir_resolver: TemplateDirResolver | None = None,
    backend_registry: BackendRegistry | None = None,
) -> ColorSchemeProcessorPort:
    from color_scheme_generator.adapters.dry_run_processor import DryRunProcessor

    return DryRunProcessor(
        backend_catalog_loader=backend_catalog_loader,
        container_runtime=container_runtime,
        output_adapter=output_adapter,
        template_dir_resolver=template_dir_resolver,
        backend_registry=backend_registry or create_backend_registry(),
    )
