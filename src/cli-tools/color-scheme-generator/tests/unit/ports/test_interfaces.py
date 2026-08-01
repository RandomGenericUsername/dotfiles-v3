from __future__ import annotations

from pathlib import Path

from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import ColorSchemeError
from color_scheme_generator.domain.models import (
    AppSettings,
    BackendDefinition,
    ColorScheme,
    ContainerMount,
    ContainerResult,
    GenerationRequest,
    GenerationResult,
    GeneratorConfig,
)
from color_scheme_generator.ports.backend_catalog_loader import BackendCatalogLoaderPort
from color_scheme_generator.ports.config_resolver import ConfigResolverPort
from color_scheme_generator.ports.container_runtime import ContainerRuntimePort
from color_scheme_generator.ports.output import OutputPort
from color_scheme_generator.ports.palette_generator import PaletteGeneratorPort
from color_scheme_generator.ports.processor import ColorSchemeProcessorPort
from color_scheme_generator.ports.settings_serializer import SettingsSerializerPort
from color_scheme_generator.ports.template_catalog_loader import TemplateCatalogLoaderPort
from color_scheme_generator.ports.template_dir_resolver import TemplateDirResolverPort
from color_scheme_generator.ports.template_renderer import TemplateRendererPort
from color_scheme_generator.ports.version_provider import VersionProviderPort

from .conftest import _scheme, _settings


class TestPaletteGeneratorPort:
    def test_valid_implementation_passes_isinstance(self) -> None:
        class MockGenerator:
            def generate(self, image_path: Path, config: GeneratorConfig) -> ColorScheme:
                return _scheme(image_path)

            def is_available(self) -> bool:
                return True

        assert isinstance(MockGenerator(), PaletteGeneratorPort)

    def test_invalid_implementation_fails_isinstance(self) -> None:
        class MissingAll:
            pass

        assert not isinstance(MissingAll(), PaletteGeneratorPort)

    def test_partial_implementation_missing_available_fails_isinstance(self) -> None:
        class MissingIsAvailable:
            def generate(self, image_path: Path, config: GeneratorConfig) -> ColorScheme:
                return _scheme(image_path)

        assert not isinstance(MissingIsAvailable(), PaletteGeneratorPort)


class TestColorSchemeProcessorPort:
    def test_valid_implementation_passes_isinstance(self) -> None:
        class MockProcessor:
            def process_generate(
                self, request: GenerationRequest, settings: object
            ) -> GenerationResult:
                return GenerationResult(
                    success=True,
                    color_scheme=None,
                    output_files=(),
                    backend=Backend.CUSTOM,
                    stderr="",
                    return_code=0,
                    duration=0.0,
                )

            def process_show(
                self, request: GenerationRequest, settings: object
            ) -> GenerationResult:
                return GenerationResult(
                    success=True,
                    color_scheme=None,
                    output_files=(),
                    backend=Backend.CUSTOM,
                    stderr="",
                    return_code=0,
                    duration=0.0,
                )

        assert isinstance(MockProcessor(), ColorSchemeProcessorPort)

    def test_invalid_implementation_fails_isinstance(self) -> None:
        class MissingAll:
            pass

        assert not isinstance(MissingAll(), ColorSchemeProcessorPort)

    def test_partial_implementation_missing_show_fails_isinstance(self) -> None:
        class MissingProcessShow:
            def process_generate(
                self, request: GenerationRequest, settings: object
            ) -> GenerationResult:
                return GenerationResult(
                    success=True,
                    color_scheme=None,
                    output_files=(),
                    backend=Backend.CUSTOM,
                    stderr="",
                    return_code=0,
                    duration=0.0,
                )

        assert not isinstance(MissingProcessShow(), ColorSchemeProcessorPort)


class TestOutputPort:
    def test_valid_implementation_passes_isinstance(self) -> None:
        class MockOutput:
            def process_result(self, result: GenerationResult) -> None:
                pass

            def error(self, exc: ColorSchemeError) -> None:
                pass

            def palette_display(self, scheme: ColorScheme) -> None:
                pass

            def message(self, msg: str) -> None:
                pass

            def config_info(
                self, settings: object, backends: dict, sources: list[str], templates: object = None
            ) -> None:
                pass

            def install_result(self, results: list[dict]) -> None:
                pass

            def uninstall_result(self, results: list[dict]) -> None:
                pass

            def version_info(self, version: str) -> None:
                pass

            def backends_catalog(self, backends: list[dict], hint: str = "") -> None:
                pass

        assert isinstance(MockOutput(), OutputPort)

    def test_invalid_implementation_fails_isinstance(self) -> None:
        class MissingAll:
            pass

        assert not isinstance(MissingAll(), OutputPort)

    def test_partial_implementation_missing_palette_display_fails_isinstance(self) -> None:
        class MissingPaletteDisplay:
            def process_result(self, result: GenerationResult) -> None:
                pass

            def error(self, exc: ColorSchemeError) -> None:
                pass

        assert not isinstance(MissingPaletteDisplay(), OutputPort)
class TestConfigResolverPort:
    def test_valid_implementation_passes_isinstance(self) -> None:
        class MockResolver:
            def resolve(self) -> AppSettings:
                return _settings()

        assert isinstance(MockResolver(), ConfigResolverPort)

    def test_invalid_implementation_fails_isinstance(self) -> None:
        class MissingAll:
            pass

        assert not isinstance(MissingAll(), ConfigResolverPort)


class TestTemplateRendererPort:
    def test_valid_implementation_passes_isinstance(self) -> None:
        class MockRenderer:
            def render(self, template_name: str, scheme: ColorScheme, output_path: Path) -> None:
                pass

        assert isinstance(MockRenderer(), TemplateRendererPort)

    def test_invalid_implementation_fails_isinstance(self) -> None:
        class MissingAll:
            pass

        assert not isinstance(MissingAll(), TemplateRendererPort)


class TestTemplateDirResolverPort:
    def test_valid_implementation_passes_isinstance(self) -> None:
        class MockResolver:
            def resolve(self) -> Path:
                return Path("/templates")

        assert isinstance(MockResolver(), TemplateDirResolverPort)

    def test_invalid_implementation_fails_isinstance(self) -> None:
        class MissingAll:
            pass

        assert not isinstance(MissingAll(), TemplateDirResolverPort)


class TestSettingsSerializerPort:
    def test_valid_implementation_passes_isinstance(self) -> None:
        class MockSerializer:
            def serialize(self, settings: AppSettings) -> str:
                return ""

            def deserialize(self, raw: str) -> AppSettings:
                return _settings()

        assert isinstance(MockSerializer(), SettingsSerializerPort)

    def test_invalid_implementation_fails_isinstance(self) -> None:
        class MissingAll:
            pass

        assert not isinstance(MissingAll(), SettingsSerializerPort)


class TestVersionProviderPort:
    def test_valid_implementation_passes_isinstance(self) -> None:
        class MockProvider:
            def get_version(self) -> str:
                return "1.0.0"

        assert isinstance(MockProvider(), VersionProviderPort)

    def test_invalid_implementation_fails_isinstance(self) -> None:
        class MissingAll:
            pass

        assert not isinstance(MissingAll(), VersionProviderPort)


class TestBackendCatalogLoaderPort:
    def test_valid_implementation_passes_isinstance(self) -> None:
        class MockLoader:
            def load(self) -> dict[Backend, BackendDefinition]:
                return {}

        assert isinstance(MockLoader(), BackendCatalogLoaderPort)

    def test_invalid_implementation_fails_isinstance(self) -> None:
        class MissingAll:
            pass

        assert not isinstance(MissingAll(), BackendCatalogLoaderPort)


class TestContainerRuntimePort:
    def test_valid_implementation_passes_isinstance(self) -> None:
        class MockRuntime:
            def run(
                self,
                image: str,
                command: list[str],
                mounts: list[ContainerMount],
                timeout: int,
            ) -> ContainerResult:
                return ContainerResult(
                    return_code=0, stdout="", stderr="", duration=0.0
                )

            def image_exists(self, image: str) -> bool:
                return True

            def pull_image(self, image: str) -> None:
                pass

            def build_image(
                self,
                context: object,
                image_name: str,
                timeout: int | None = 600,
                backend: object = None,
            ) -> str:
                return "sha256:mock"

            def remove_image(self, image: str, force: bool = False, backend: object = None) -> None:
                pass

        assert isinstance(MockRuntime(), ContainerRuntimePort)

    def test_invalid_implementation_fails_isinstance(self) -> None:
        class MissingAll:
            pass

        assert not isinstance(MissingAll(), ContainerRuntimePort)

    def test_partial_implementation_missing_pull_fails_isinstance(self) -> None:
        class MissingPullImage:
            def run(
                self,
                image: str,
                command: list[str],
                mounts: list[ContainerMount],
                timeout: int,
            ) -> ContainerResult:
                return ContainerResult(
                    return_code=0, stdout="", stderr="", duration=0.0
                )

            def image_exists(self, image: str) -> bool:
                return True

        assert not isinstance(MissingPullImage(), ContainerRuntimePort)


class TestTemplateCatalogLoaderPort:
    def test_valid_implementation_passes_isinstance(self) -> None:
        from color_scheme_generator.domain.enums import ColorFormat
        from color_scheme_generator.domain.models import ColorSchemeTemplate, TemplateCatalog

        tpl = ColorSchemeTemplate(name="colors.json.j2", format=ColorFormat.JSON)

        class MockLoader:
            def load(self, explicit_dir: Path | None = None) -> TemplateCatalog:
                return TemplateCatalog(templates=(tpl,))

            def get_resolved_path(self) -> Path | None:
                return None

        assert isinstance(MockLoader(), TemplateCatalogLoaderPort)

    def test_invalid_implementation_fails_isinstance(self) -> None:
        class MissingAll:
            pass

        assert not isinstance(MissingAll(), TemplateCatalogLoaderPort)

    def test_partial_implementation_missing_get_resolved_path_fails_isinstance(self) -> None:
        class MissingGetResolvedPath:
            def load(self, explicit_dir: Path | None = None) -> object:
                return object()

        assert not isinstance(MissingGetResolvedPath(), TemplateCatalogLoaderPort)
