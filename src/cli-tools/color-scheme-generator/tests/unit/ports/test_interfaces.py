from __future__ import annotations

from datetime import datetime
from pathlib import Path

from color_scheme_generator.domain.enums import Backend, ContainerEngine, RuntimeMode
from color_scheme_generator.domain.exceptions import ColorSchemeError
from color_scheme_generator.domain.models import (
    AppSettings,
    BackendDefinition,
    Color,
    ColorScheme,
    ContainerMount,
    ContainerResult,
    ContainerSettings,
    GenerationRequest,
    GenerationResult,
    GenerationSettings,
    GeneratorConfig,
    OutputSettings,
    RuntimeSettings,
    TemplateSettings,
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

_now = datetime.now()


def _scheme(overrides: object = None) -> ColorScheme:
    return ColorScheme(
        background=Color("#000000", (0, 0, 0)),
        foreground=Color("#ffffff", (255, 255, 255)),
        cursor=Color("#00ff00", (0, 255, 0)),
        colors=tuple(Color("#000000", (0, 0, 0)) for _ in range(16)),
        source_image=Path("/tmp/test.png"),
        backend=Backend.CUSTOM,
        generated_at=_now,
    )


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


def _settings() -> AppSettings:
    return AppSettings(
        output=OutputSettings(
            directory=Path("/tmp/output"),
            default_formats=(),
            overwrite=False,
        ),
        generation=GenerationSettings(backend=Backend.CUSTOM, default_params={}),
        template=TemplateSettings(templates_dir=None, custom_templates_dir=None),
        runtime=RuntimeSettings(
            mode=RuntimeMode.LOCAL, engine=ContainerEngine.DOCKER
        ),
        container=ContainerSettings(
            image_prefix="csg",
            image_tag="latest",
            timeout_seconds=300,
            memory_limit="512m",
            mount_timeout_seconds=30,
        ),
    )


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
