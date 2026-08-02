from __future__ import annotations

from dataclasses import dataclass, field

from icon_templates_renderer.adapters.assembled_config_resolver import AssembledConfigResolver
from icon_templates_renderer.adapters.file_color_scheme_loader import FileColorSchemeLoader
from icon_templates_renderer.adapters.file_svg_renderer import FileSvgRenderer
from icon_templates_renderer.adapters.icon_renderer import IconRenderer
from icon_templates_renderer.adapters.yaml_icon_config_loader import YamlIconConfigLoader
from icon_templates_renderer.adapters.yaml_vocabulary_loader import YamlVocabularyLoader
from icon_templates_renderer.domain.enums import OutputFormat, Verbosity
from icon_templates_renderer.ports.color_scheme_loader import ColorSchemeLoaderPort
from icon_templates_renderer.ports.config_resolver import ConfigResolverPort
from icon_templates_renderer.ports.icon_config_loader import IconConfigLoaderPort
from icon_templates_renderer.ports.icon_renderer import IconRendererPort
from icon_templates_renderer.ports.output import OutputPort
from icon_templates_renderer.ports.svg_renderer import SvgRendererPort
from icon_templates_renderer.ports.vocabulary_loader import VocabularyLoaderPort


@dataclass
class CliDependencies:
    config_loader: IconConfigLoaderPort = field(default_factory=YamlIconConfigLoader)
    color_loader: ColorSchemeLoaderPort = field(default_factory=FileColorSchemeLoader)
    vocab_loader: VocabularyLoaderPort = field(default_factory=YamlVocabularyLoader)
    svg_renderer: SvgRendererPort = field(default_factory=FileSvgRenderer)
    icon_renderer: IconRendererPort | None = None
    config_resolver: ConfigResolverPort | None = None
    output_adapter: OutputPort | None = None

    def __post_init__(self) -> None:
        if self.icon_renderer is None:
            self.icon_renderer = IconRenderer(
                self.config_loader,
                self.color_loader,
                self.vocab_loader,
                self.svg_renderer,
            )


def create_config_loader() -> IconConfigLoaderPort:
    return YamlIconConfigLoader()


def create_color_loader() -> ColorSchemeLoaderPort:
    return FileColorSchemeLoader()


def create_vocab_loader() -> VocabularyLoaderPort:
    return YamlVocabularyLoader()


def create_svg_renderer() -> SvgRendererPort:
    return FileSvgRenderer()


def create_config_resolver() -> AssembledConfigResolver:
    return AssembledConfigResolver()


def create_output_adapter(
    fmt: OutputFormat,
    verbosity: Verbosity = Verbosity.NORMAL,
) -> OutputPort:
    from cli_output.adapters.factory import create_renderer
    from cli_output.domain.enums import OutputFormat as SharedOutputFormat

    from icon_templates_renderer.adapters.output.json_output import JsonOutput
    from icon_templates_renderer.adapters.output.plain_output import PlainOutput
    from icon_templates_renderer.adapters.output.rich_output import RichOutput

    renderer = create_renderer(SharedOutputFormat(fmt.value))
    if fmt is OutputFormat.RICH:
        return RichOutput(verbosity=verbosity, renderer=renderer)
    if fmt is OutputFormat.PLAIN:
        return PlainOutput(verbosity=verbosity, renderer=renderer)
    return JsonOutput(verbosity=verbosity, renderer=renderer)
