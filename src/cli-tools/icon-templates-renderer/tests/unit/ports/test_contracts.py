from __future__ import annotations

import pytest

from icon_templates_renderer.adapters.assembled_config_resolver import AssembledConfigResolver
from icon_templates_renderer.adapters.color_scheme_resolver import ColorSchemeResolver
from icon_templates_renderer.adapters.file_color_scheme_loader import FileColorSchemeLoader
from icon_templates_renderer.adapters.file_svg_renderer import FileSvgRenderer
from icon_templates_renderer.adapters.icon_renderer import IconRenderer
from icon_templates_renderer.adapters.template_dir_resolver import TemplateDirResolver
from icon_templates_renderer.adapters.yaml_icon_config_loader import YamlIconConfigLoader
from icon_templates_renderer.adapters.yaml_vocabulary_loader import YamlVocabularyLoader
from icon_templates_renderer.domain.enums import OutputFormat, Verbosity
from icon_templates_renderer.domain.models import ResolvedRoots
from icon_templates_renderer.factory import create_output_adapter
from icon_templates_renderer.ports.color_scheme_loader import ColorSchemeLoaderPort
from icon_templates_renderer.ports.color_scheme_resolver import ColorSchemeResolverPort
from icon_templates_renderer.ports.config_resolver import ConfigResolverPort
from icon_templates_renderer.ports.icon_config_loader import IconConfigLoaderPort
from icon_templates_renderer.ports.icon_renderer import IconRendererPort
from icon_templates_renderer.ports.output import OutputPort
from icon_templates_renderer.ports.svg_renderer import SvgRendererPort
from icon_templates_renderer.ports.template_dir_resolver import TemplateDirResolverPort
from icon_templates_renderer.ports.vocabulary_loader import VocabularyLoaderPort
from tests.unit.ports.conftest import (
    assert_interface_method_count,
    assert_isinstance,
    assert_signature_compatible,
)


class _StubLoader:
    def load(self, yaml_path, roots=None):
        return None

    def load_one(self, yaml_path, icon, roots=None):
        return None

    def get_resolved_path(self):
        return None


class _StubColor:
    def load(self, path):
        return None

    def supports(self, path):
        return True


class _StubVocab:
    def load(self, path):
        return None


class _StubSvg:
    def render_variant(self, variant, scheme, unsafe, color_mappings):
        return variant.output

    def render_string(self, svg_body, scheme, unsafe, color_mappings):
        return svg_body


CONFIG_PAIRS = [
    (YamlIconConfigLoader(), IconConfigLoaderPort),
    (FileColorSchemeLoader(), ColorSchemeLoaderPort),
    (YamlVocabularyLoader(), VocabularyLoaderPort),
    (FileSvgRenderer(), SvgRendererPort),
    (
        IconRenderer(_StubLoader(), _StubColor(), _StubVocab(), _StubSvg()),
        IconRendererPort,
    ),
    (AssembledConfigResolver(), ConfigResolverPort),
    (TemplateDirResolver(), TemplateDirResolverPort),
    (ColorSchemeResolver(), ColorSchemeResolverPort),
    (
        create_output_adapter(OutputFormat.PLAIN, Verbosity.NORMAL),
        OutputPort,
    ),
]


class TestAdapterContracts:
    @pytest.mark.parametrize(
        "impl,port",
        CONFIG_PAIRS,
        ids=[f"{p.__name__}<-{type(i).__name__}" for i, p in CONFIG_PAIRS],
    )
    def test_adapters_satisfy_ports(self, impl: object, port: type) -> None:
        assert_isinstance(impl, port)
        assert_signature_compatible(impl, port)
        assert_interface_method_count(impl, port)

    def test_icon_renderer_builds_from_default_ports(self) -> None:
        renderer = IconRenderer(
            YamlIconConfigLoader(),
            FileColorSchemeLoader(),
            YamlVocabularyLoader(),
            FileSvgRenderer(),
        )
        assert_isinstance(renderer, IconRendererPort)
        assert ResolvedRoots() is not None
