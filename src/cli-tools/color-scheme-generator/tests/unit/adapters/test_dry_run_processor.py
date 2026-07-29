from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from color_scheme_generator.adapters.dry_run_processor import DryRunProcessor
from color_scheme_generator.domain.enums import (
    Backend,
    ColorFormat,
    RuntimeMode,
)
from color_scheme_generator.domain.exceptions import (
    BackendNotRegisteredError,
    ContainerImageNotFoundError,
    ContainerRuntimeUnavailableError,
    InvalidImageError,
    PaletteGenerationError,
)
from color_scheme_generator.domain.models import (
    AppSettings,
    BackendDefinition,
    BackendParameterDefinition,
    ContainerSettings,
    GenerationRequest,
    GenerationSettings,
    GeneratorConfig,
    OutputSettings,
    RuntimeSettings,
    TemplateSettings,
)


def _make_settings(
    runtime_mode: RuntimeMode = RuntimeMode.LOCAL,
) -> AppSettings:
    return AppSettings(
        output=OutputSettings(
            directory=Path("/tmp/out"),
            default_formats=(ColorFormat.JSON,),
            overwrite=False,
        ),
        generation=GenerationSettings(
            backend=Backend.CUSTOM,
            default_params={},
        ),
        template=TemplateSettings(
            templates_dir=Path("/templates"),
            custom_templates_dir=None,
        ),
        runtime=RuntimeSettings(
            mode=runtime_mode,
        ),
        container=ContainerSettings(
            engine="docker",
            image_prefix="ghcr.io/user/",
            image_tag="latest",
            timeout_seconds=120,
            memory_limit="512m",
            mount_timeout_seconds=30,
        ),
    )


def _make_custom_backend_def() -> BackendDefinition:
    return BackendDefinition(
        backend=Backend.CUSTOM,
        display_name="Custom",
        description="Custom backend",
        parameters=(
            BackendParameterDefinition(
                name="saturation",
                type_="float",
                description="Saturation factor",
                required=False,
                choices=None,
                default=1.0,
            ),
            BackendParameterDefinition(
                name="n_clusters",
                type_="int",
                description="Number of clusters",
                required=False,
                choices=None,
                default=16,
            ),
            BackendParameterDefinition(
                name="algorithm",
                type_="str",
                description="Algorithm",
                required=False,
                choices=("kmeans",),
                default="kmeans",
            ),
        ),
        min_version="0.0.0",
    )


@pytest.fixture
def mock_catalog_loader() -> MagicMock:
    loader = MagicMock()
    loader.load.return_value = {Backend.CUSTOM: _make_custom_backend_def()}
    return loader


@pytest.fixture
def mock_output_adapter() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_container_runtime() -> MagicMock:
    runtime = MagicMock()
    runtime.image_exists.return_value = True
    return runtime


@pytest.fixture
def mock_template_dir_resolver() -> MagicMock:
    resolver = MagicMock()
    resolver.resolve.return_value = Path("/templates")
    return resolver


@pytest.fixture
def mock_backend_registry() -> dict[Backend, MagicMock]:
    return {Backend.CUSTOM: MagicMock()}


@pytest.fixture
def processor(
    mock_catalog_loader: MagicMock,
    mock_output_adapter: MagicMock,
    mock_template_dir_resolver: MagicMock,
    mock_backend_registry: dict[Backend, MagicMock],
) -> DryRunProcessor:
    return DryRunProcessor(
        backend_catalog_loader=mock_catalog_loader,
        container_runtime=None,
        output_adapter=mock_output_adapter,
        template_dir_resolver=mock_template_dir_resolver,
        backend_registry=mock_backend_registry,
    )


@pytest.fixture
def valid_request(tmp_path: Path) -> GenerationRequest:
    input_file = tmp_path / "input.png"
    input_file.write_text("dummy")
    return GenerationRequest(
        image_path=input_file,
        config=GeneratorConfig(
            backend=Backend.CUSTOM,
            params={},
            formats=(ColorFormat.JSON,),
            output_dir=tmp_path / "output",
        ),
    )


class TestPreFlightInput:
    def test_pre_flight_input_not_found(
        self, processor: DryRunProcessor, tmp_path: Path
    ) -> None:
        request = GenerationRequest(
            image_path=tmp_path / "nonexistent.png",
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={},
                formats=(ColorFormat.JSON,),
                output_dir=tmp_path / "output",
            ),
        )
        settings = _make_settings()

        with pytest.raises(InvalidImageError):
            processor.process_generate(request, settings)


class TestPreFlightLocalBackend:
    def test_pre_flight_local_backend_not_available(
        self,
        mock_catalog_loader: MagicMock,
        mock_output_adapter: MagicMock,
        tmp_path: Path,
    ) -> None:
        processor = DryRunProcessor(
            backend_catalog_loader=mock_catalog_loader,
            container_runtime=None,
            output_adapter=mock_output_adapter,
            template_dir_resolver=None,
            backend_registry={},
        )
        input_file = tmp_path / "input.png"
        input_file.write_text("dummy")
        request = GenerationRequest(
            image_path=input_file,
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={},
                formats=(ColorFormat.JSON,),
                output_dir=tmp_path / "output",
            ),
        )
        settings = _make_settings(RuntimeMode.LOCAL)

        with pytest.raises(BackendNotRegisteredError):
            processor.process_generate(request, settings)


class TestPreFlightContainerMode:
    def test_pre_flight_container_mode_checks_engine(
        self,
        mock_catalog_loader: MagicMock,
        mock_output_adapter: MagicMock,
        mock_container_runtime: MagicMock,
        mock_backend_registry: dict[Backend, MagicMock],
        tmp_path: Path,
    ) -> None:
        processor = DryRunProcessor(
            backend_catalog_loader=mock_catalog_loader,
            container_runtime=None,
            output_adapter=mock_output_adapter,
            template_dir_resolver=None,
            backend_registry=mock_backend_registry,
        )
        input_file = tmp_path / "input.png"
        input_file.write_text("dummy")
        request = GenerationRequest(
            image_path=input_file,
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={},
                formats=(ColorFormat.JSON,),
                output_dir=tmp_path / "output",
            ),
        )
        settings = _make_settings(RuntimeMode.CONTAINER)

        with pytest.raises(ContainerRuntimeUnavailableError):
            processor.process_generate(request, settings)

    def test_pre_flight_container_mode_image_not_found(
        self,
        mock_catalog_loader: MagicMock,
        mock_output_adapter: MagicMock,
        mock_container_runtime: MagicMock,
        mock_backend_registry: dict[Backend, MagicMock],
        tmp_path: Path,
    ) -> None:
        mock_container_runtime.image_exists.return_value = False
        processor = DryRunProcessor(
            backend_catalog_loader=mock_catalog_loader,
            container_runtime=mock_container_runtime,
            output_adapter=mock_output_adapter,
            template_dir_resolver=None,
            backend_registry=mock_backend_registry,
        )
        input_file = tmp_path / "input.png"
        input_file.write_text("dummy")
        request = GenerationRequest(
            image_path=input_file,
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={},
                formats=(ColorFormat.JSON,),
                output_dir=tmp_path / "output",
            ),
        )
        settings = _make_settings(RuntimeMode.CONTAINER)

        with pytest.raises(ContainerImageNotFoundError):
            processor.process_generate(request, settings)

    def test_pre_flight_container_mode_does_not_pull(
        self,
        mock_catalog_loader: MagicMock,
        mock_output_adapter: MagicMock,
        mock_container_runtime: MagicMock,
        mock_backend_registry: dict[Backend, MagicMock],
        tmp_path: Path,
    ) -> None:
        processor = DryRunProcessor(
            backend_catalog_loader=mock_catalog_loader,
            container_runtime=mock_container_runtime,
            output_adapter=mock_output_adapter,
            template_dir_resolver=None,
            backend_registry=mock_backend_registry,
        )
        input_file = tmp_path / "input.png"
        input_file.write_text("dummy")
        request = GenerationRequest(
            image_path=input_file,
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={},
                formats=(ColorFormat.JSON,),
                output_dir=tmp_path / "output",
            ),
        )
        settings = _make_settings(RuntimeMode.CONTAINER)

        result = processor.process_generate(request, settings)

        assert result.success
        mock_container_runtime.pull_image.assert_not_called()

    def test_pre_flight_container_mode_skips_host_check(
        self,
        mock_catalog_loader: MagicMock,
        mock_output_adapter: MagicMock,
        mock_container_runtime: MagicMock,
        tmp_path: Path,
    ) -> None:
        processor = DryRunProcessor(
            backend_catalog_loader=mock_catalog_loader,
            container_runtime=mock_container_runtime,
            output_adapter=mock_output_adapter,
            template_dir_resolver=None,
            backend_registry={},
        )
        input_file = tmp_path / "input.png"
        input_file.write_text("dummy")
        request = GenerationRequest(
            image_path=input_file,
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={},
                formats=(ColorFormat.JSON,),
                output_dir=tmp_path / "output",
            ),
        )
        settings = _make_settings(RuntimeMode.CONTAINER)

        result = processor.process_generate(request, settings)

        assert result.success


class TestValidateParams:
    def test_validate_params_invalid_type(
        self,
        mock_catalog_loader: MagicMock,
        mock_output_adapter: MagicMock,
        tmp_path: Path,
    ) -> None:
        processor = DryRunProcessor(
            backend_catalog_loader=mock_catalog_loader,
            container_runtime=None,
            output_adapter=mock_output_adapter,
            template_dir_resolver=None,
            backend_registry={Backend.CUSTOM: MagicMock()},
        )
        input_file = tmp_path / "input.png"
        input_file.write_text("dummy")
        request = GenerationRequest(
            image_path=input_file,
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={"n_clusters": "abc"},
                formats=(ColorFormat.JSON,),
                output_dir=tmp_path / "output",
            ),
        )
        settings = _make_settings(RuntimeMode.LOCAL)

        with pytest.raises(PaletteGenerationError) as exc_info:
            processor.process_generate(request, settings)

        assert "n_clusters" in str(exc_info.value)

    def test_validate_params_unknown_param(
        self,
        mock_catalog_loader: MagicMock,
        mock_output_adapter: MagicMock,
        tmp_path: Path,
    ) -> None:
        processor = DryRunProcessor(
            backend_catalog_loader=mock_catalog_loader,
            container_runtime=None,
            output_adapter=mock_output_adapter,
            template_dir_resolver=None,
            backend_registry={Backend.CUSTOM: MagicMock()},
        )
        input_file = tmp_path / "input.png"
        input_file.write_text("dummy")
        request = GenerationRequest(
            image_path=input_file,
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={"nonexistent_param": "value"},
                formats=(ColorFormat.JSON,),
                output_dir=tmp_path / "output",
            ),
        )
        settings = _make_settings(RuntimeMode.LOCAL)

        with pytest.raises(PaletteGenerationError) as exc_info:
            processor.process_generate(request, settings)

        assert "nonexistent_param" in str(exc_info.value)


class TestProcessGenerate:
    def test_process_generate_returns_success_with_command(
        self,
        processor: DryRunProcessor,
        valid_request: GenerationRequest,
    ) -> None:
        settings = _make_settings(RuntimeMode.LOCAL)

        result = processor.process_generate(valid_request, settings)

        assert result.success
        assert "csg" in result.stderr
        assert str(valid_request.image_path) in result.stderr
        assert result.color_scheme is None


class TestProcessShow:
    def test_process_show_returns_success_with_command(
        self,
        processor: DryRunProcessor,
        valid_request: GenerationRequest,
    ) -> None:
        settings = _make_settings(RuntimeMode.LOCAL)

        result = processor.process_show(valid_request, settings)

        assert result.success
        assert "csg" in result.stderr
        assert "show" in result.stderr
        assert result.color_scheme is None


class TestInstanceCheck:
    def test_isinstance_check_passes(
        self, processor: DryRunProcessor
    ) -> None:
        from color_scheme_generator.ports.processor import ColorSchemeProcessorPort

        assert isinstance(processor, ColorSchemeProcessorPort)
