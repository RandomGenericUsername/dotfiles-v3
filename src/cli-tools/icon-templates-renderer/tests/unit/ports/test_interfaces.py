from __future__ import annotations

import pytest

from icon_templates_renderer.ports.color_scheme_loader import ColorSchemeLoaderPort
from icon_templates_renderer.ports.color_scheme_resolver import ColorSchemeResolverPort
from icon_templates_renderer.ports.config_resolver import ConfigResolverPort
from icon_templates_renderer.ports.icon_config_loader import IconConfigLoaderPort
from icon_templates_renderer.ports.icon_renderer import IconRendererPort
from icon_templates_renderer.ports.output import OutputPort
from icon_templates_renderer.ports.svg_renderer import SvgRendererPort
from icon_templates_renderer.ports.template_dir_resolver import TemplateDirResolverPort
from icon_templates_renderer.ports.vocabulary_loader import VocabularyLoaderPort


class _Stub:
    def load(self, *args, **kwargs) -> object:
        return None

    def load_one(self, *args, **kwargs) -> object:
        return None

    def get_resolved_path(self) -> None:
        return None

    def supports(self, *args, **kwargs) -> bool:
        return True

    def resolve(self, *args, **kwargs) -> object:
        return None

    def render_variant(self, *args, **kwargs) -> object:
        return None

    def render_string(self, *args, **kwargs) -> str:
        return ""

    def render(self, *args, **kwargs) -> object:
        return None

    def list(self, *args, **kwargs) -> object:
        return None

    def validate(self, *args, **kwargs) -> object:
        return None

    def mapping_show(self, *args, **kwargs) -> object:
        return None

    def mapping_set(self, *args, **kwargs) -> object:
        return None

    def mapping_set_default(self, *args, **kwargs) -> object:
        return None

    def render_result(self, *args, **kwargs) -> None:
        return None

    def mapping_show_result(self, *args, **kwargs) -> None:
        return None

    def mapping_set_result(self, *args, **kwargs) -> None:
        return None

    def mapping_set_default_result(self, *args, **kwargs) -> None:
        return None

    def list_result(self, *args, **kwargs) -> None:
        return None

    def validate_result(self, *args, **kwargs) -> None:
        return None

    def error(self, *args, **kwargs) -> None:
        return None

    def message(self, *args, **kwargs) -> None:
        return None


def _stub_with_missing_methods() -> object:
    class _Incomplete:
        pass

    return _Incomplete()


class TestInterfaces:
    @pytest.mark.parametrize(
        "port",
        [
            IconConfigLoaderPort,
            ColorSchemeLoaderPort,
            VocabularyLoaderPort,
            SvgRendererPort,
            IconRendererPort,
            ConfigResolverPort,
            TemplateDirResolverPort,
            ColorSchemeResolverPort,
            OutputPort,
        ],
    )
    def test_ports_are_runtime_checkable(self, port: type) -> None:
        assert isinstance(_Stub(), port), f"_Stub does not satisfy {port.__name__}"

    def test_incomplete_impl_fails(self) -> None:
        # runtime_checkable Protocol isinstance returns False (does not raise) for
        # structurally-incompatible objects.
        assert not isinstance(_stub_with_missing_methods(), IconRendererPort)
