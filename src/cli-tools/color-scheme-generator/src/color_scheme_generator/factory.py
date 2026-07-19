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
from color_scheme_generator.domain.enums import Backend, OutputFormat
from color_scheme_generator.ports.output import OutputPort
from color_scheme_generator.ports.palette_generator import PaletteGeneratorPort
from color_scheme_generator.ports.template_renderer import TemplateRendererPort

if TYPE_CHECKING:
    from color_scheme_generator.adapters.local_processor import LocalProcessor

BackendRegistry = dict[Backend, PaletteGeneratorPort]


@dataclass
class CliDependencies:
    backend_registry: BackendRegistry
    backend_catalog_loader: YamlBackendCatalogLoader | None = None
    config_resolver: AssembledConfigResolver | None = None
    output_adapter: OutputPort | None = None
    processor: LocalProcessor | None = None
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
