from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from color_scheme_generator.adapters.backends.custom_generator import CustomGenerator
from color_scheme_generator.adapters.backends.pywal_generator import PywalGenerator
from color_scheme_generator.adapters.backends.wallust_generator import WallustGenerator
from color_scheme_generator.adapters.container_processor import ContainerProcessor
from color_scheme_generator.adapters.dry_run_processor import DryRunProcessor
from color_scheme_generator.adapters.jinja_template_renderer import (
    JinjaTemplateRenderer,
)
from color_scheme_generator.adapters.local_processor import LocalProcessor
from color_scheme_generator.adapters.oci_container_runtime import (
    OciContainerRuntimeAdapter,
)
from color_scheme_generator.adapters.output.json_output import JsonOutput
from color_scheme_generator.adapters.output.plain_output import PlainOutput
from color_scheme_generator.adapters.output.rich_output import RichOutput
from color_scheme_generator.adapters.settings.config_resolver import (
    AssembledConfigResolver,
)
from color_scheme_generator.adapters.settings.settings_serializer import (
    SettingsSerializer,
)
from color_scheme_generator.adapters.template_dir_resolver import TemplateDirResolver
from color_scheme_generator.adapters.yaml_backend_catalog_loader import (
    YamlBackendCatalogLoader,
)
from color_scheme_generator.ports.backend_catalog_loader import BackendCatalogLoaderPort
from color_scheme_generator.ports.config_resolver import ConfigResolverPort
from color_scheme_generator.ports.container_runtime import ContainerRuntimePort
from color_scheme_generator.ports.output import OutputPort
from color_scheme_generator.ports.palette_generator import PaletteGeneratorPort
from color_scheme_generator.ports.processor import ColorSchemeProcessorPort
from color_scheme_generator.ports.settings_serializer import SettingsSerializerPort
from color_scheme_generator.ports.template_dir_resolver import TemplateDirResolverPort
from color_scheme_generator.ports.template_renderer import TemplateRendererPort
from color_scheme_generator.ports.version_provider import VersionProviderPort

from .conftest import (
    assert_interface_method_count,
    assert_isinstance,
    assert_signature_compatible,
)


class TestPaletteGeneratorContract:
    @pytest.mark.parametrize(
        "impl",
        [
            CustomGenerator(),
            PywalGenerator(),
            WallustGenerator(),
        ],
    )
    def test_valid_isinstance_check(self, impl: object) -> None:
        assert_isinstance(impl, PaletteGeneratorPort)

    def test_signature_generate(self) -> None:
        assert_signature_compatible(CustomGenerator(), PaletteGeneratorPort)
        assert_signature_compatible(PywalGenerator(), PaletteGeneratorPort)
        assert_signature_compatible(WallustGenerator(), PaletteGeneratorPort)

    def test_signature_is_available(self) -> None:
        assert_signature_compatible(CustomGenerator(), PaletteGeneratorPort)
        assert_signature_compatible(PywalGenerator(), PaletteGeneratorPort)
        assert_signature_compatible(WallustGenerator(), PaletteGeneratorPort)

    @pytest.mark.parametrize(
        "impl",
        [
            CustomGenerator(),
            PywalGenerator(),
            WallustGenerator(),
        ],
    )
    def test_interface_method_count(self, impl: object) -> None:
        assert_interface_method_count(impl, PaletteGeneratorPort)


class TestColorSchemeProcessorContract:
    @pytest.mark.parametrize(
        "impl",
        [
            LocalProcessor(backend_registry={}),
            ContainerProcessor(container_runtime=MagicMock()),
            DryRunProcessor(backend_catalog_loader=MagicMock()),
        ],
    )
    def test_valid_isinstance_check(self, impl: object) -> None:
        assert_isinstance(impl, ColorSchemeProcessorPort)

    def test_signature_process_generate(self) -> None:
        assert_signature_compatible(
            LocalProcessor(backend_registry={}), ColorSchemeProcessorPort
        )
        assert_signature_compatible(
            ContainerProcessor(container_runtime=MagicMock()),
            ColorSchemeProcessorPort,
        )
        assert_signature_compatible(
            DryRunProcessor(backend_catalog_loader=MagicMock()),
            ColorSchemeProcessorPort,
        )

    def test_signature_process_show(self) -> None:
        assert_signature_compatible(
            LocalProcessor(backend_registry={}), ColorSchemeProcessorPort
        )
        assert_signature_compatible(
            ContainerProcessor(container_runtime=MagicMock()),
            ColorSchemeProcessorPort,
        )
        assert_signature_compatible(
            DryRunProcessor(backend_catalog_loader=MagicMock()),
            ColorSchemeProcessorPort,
        )

    @pytest.mark.parametrize(
        "impl",
        [
            LocalProcessor(backend_registry={}),
            ContainerProcessor(container_runtime=MagicMock()),
            DryRunProcessor(backend_catalog_loader=MagicMock()),
        ],
    )
    def test_interface_method_count(self, impl: object) -> None:
        assert_interface_method_count(impl, ColorSchemeProcessorPort)


class TestOutputContract:
    @pytest.mark.parametrize(
        "impl",
        [
            JsonOutput(),
            RichOutput(),
            PlainOutput(),
        ],
    )
    def test_valid_isinstance_check(self, impl: object) -> None:
        assert_isinstance(impl, OutputPort)

    def test_signature_process_result(self) -> None:
        assert_signature_compatible(JsonOutput(), OutputPort)
        assert_signature_compatible(RichOutput(), OutputPort)
        assert_signature_compatible(PlainOutput(), OutputPort)

    def test_signature_error(self) -> None:
        assert_signature_compatible(JsonOutput(), OutputPort)
        assert_signature_compatible(RichOutput(), OutputPort)
        assert_signature_compatible(PlainOutput(), OutputPort)

    def test_signature_palette_display(self) -> None:
        assert_signature_compatible(JsonOutput(), OutputPort)
        assert_signature_compatible(RichOutput(), OutputPort)
        assert_signature_compatible(PlainOutput(), OutputPort)

    @pytest.mark.parametrize(
        "impl",
        [
            JsonOutput(),
            RichOutput(),
            PlainOutput(),
        ],
    )
    def test_interface_method_count(self, impl: object) -> None:
        assert_interface_method_count(impl, OutputPort)


class TestConfigResolverContract:
    @pytest.mark.parametrize(
        "impl",
        [
            AssembledConfigResolver(),
        ],
    )
    def test_valid_isinstance_check(self, impl: object) -> None:
        assert_isinstance(impl, ConfigResolverPort)

    def test_signature_resolve(self) -> None:
        assert_signature_compatible(AssembledConfigResolver(), ConfigResolverPort)

    def test_interface_method_count(self) -> None:
        assert_interface_method_count(AssembledConfigResolver(), ConfigResolverPort)


class TestTemplateRendererContract:
    @pytest.mark.parametrize(
        "impl",
        [
            JinjaTemplateRenderer(resolver=TemplateDirResolver()),
        ],
    )
    def test_valid_isinstance_check(self, impl: object) -> None:
        assert_isinstance(impl, TemplateRendererPort)

    def test_signature_render(self) -> None:
        assert_signature_compatible(
            JinjaTemplateRenderer(resolver=TemplateDirResolver()),
            TemplateRendererPort,
        )

    def test_interface_method_count(self) -> None:
        assert_interface_method_count(
            JinjaTemplateRenderer(resolver=TemplateDirResolver()),
            TemplateRendererPort,
        )


class TestTemplateDirResolverContract:
    @pytest.mark.parametrize(
        "impl",
        [
            TemplateDirResolver(),
        ],
    )
    def test_valid_isinstance_check(self, impl: object) -> None:
        assert_isinstance(impl, TemplateDirResolverPort)

    def test_signature_resolve(self) -> None:
        assert_signature_compatible(TemplateDirResolver(), TemplateDirResolverPort)

    def test_interface_method_count(self) -> None:
        assert_interface_method_count(TemplateDirResolver(), TemplateDirResolverPort)


class TestSettingsSerializerContract:
    @pytest.mark.parametrize(
        "impl",
        [
            SettingsSerializer(),
        ],
    )
    def test_valid_isinstance_check(self, impl: object) -> None:
        assert_isinstance(impl, SettingsSerializerPort)

    def test_signature_serialize(self) -> None:
        assert_signature_compatible(SettingsSerializer(), SettingsSerializerPort)

    def test_signature_deserialize(self) -> None:
        assert_signature_compatible(SettingsSerializer(), SettingsSerializerPort)

    def test_interface_method_count(self) -> None:
        assert_interface_method_count(SettingsSerializer(), SettingsSerializerPort)


class TestVersionProviderContract:
    class _TestVersionProvider:
        def get_version(self) -> str:
            return "0.0.0"

    @pytest.fixture
    def impl(self) -> _TestVersionProvider:
        return self._TestVersionProvider()

    def test_valid_isinstance_check(self) -> None:
        impl = self._TestVersionProvider()
        assert_isinstance(impl, VersionProviderPort)

    def test_signature_get_version(self) -> None:
        impl = self._TestVersionProvider()
        assert_signature_compatible(impl, VersionProviderPort)

    def test_interface_method_count(self) -> None:
        impl = self._TestVersionProvider()
        assert_interface_method_count(impl, VersionProviderPort)


class TestBackendCatalogLoaderContract:
    @pytest.mark.parametrize(
        "impl",
        [
            YamlBackendCatalogLoader(),
        ],
    )
    def test_valid_isinstance_check(self, impl: object) -> None:
        assert_isinstance(impl, BackendCatalogLoaderPort)

    def test_signature_load(self) -> None:
        assert_signature_compatible(
            YamlBackendCatalogLoader(), BackendCatalogLoaderPort
        )

    def test_interface_method_count(self) -> None:
        assert_interface_method_count(
            YamlBackendCatalogLoader(), BackendCatalogLoaderPort
        )


class TestContainerRuntimeContract:
    @pytest.mark.parametrize(
        "impl",
        [
            OciContainerRuntimeAdapter(engine=MagicMock()),
        ],
    )
    def test_valid_isinstance_check(self, impl: object) -> None:
        assert_isinstance(impl, ContainerRuntimePort)

    def test_signature_run(self) -> None:
        assert_signature_compatible(
            OciContainerRuntimeAdapter(engine=MagicMock()), ContainerRuntimePort
        )

    def test_signature_image_exists(self) -> None:
        assert_signature_compatible(
            OciContainerRuntimeAdapter(engine=MagicMock()), ContainerRuntimePort
        )

    def test_signature_pull_image(self) -> None:
        assert_signature_compatible(
            OciContainerRuntimeAdapter(engine=MagicMock()), ContainerRuntimePort
        )

    def test_signature_build_image(self) -> None:
        assert_signature_compatible(
            OciContainerRuntimeAdapter(engine=MagicMock()), ContainerRuntimePort
        )

    def test_signature_remove_image(self) -> None:
        assert_signature_compatible(
            OciContainerRuntimeAdapter(engine=MagicMock()), ContainerRuntimePort
        )

    def test_interface_method_count(self) -> None:
        assert_interface_method_count(
            OciContainerRuntimeAdapter(engine=MagicMock()), ContainerRuntimePort
        )
