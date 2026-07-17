from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from color_scheme_generator.adapters.local_processor import LocalProcessor
from color_scheme_generator.domain.enums import Backend, ColorFormat
from color_scheme_generator.domain.exceptions import (
    BackendNotAvailableError,
    BackendNotRegisteredError,
)
from color_scheme_generator.domain.models import (
    Color,
    ColorScheme,
    GenerationRequest,
    GenerationResult,
    GeneratorConfig,
)
from color_scheme_generator.ports.processor import ColorSchemeProcessorPort


def _make_scheme() -> ColorScheme:
    return ColorScheme(
        background=Color("#000000", (0, 0, 0)),
        foreground=Color("#ffffff", (255, 255, 255)),
        cursor=Color("#00ff00", (0, 255, 0)),
        colors=tuple(Color("#000000", (0, 0, 0)) for _ in range(16)),
        source_image=Path("/tmp/test.png"),
        backend=Backend.CUSTOM,
        generated_at=datetime(2024, 1, 1),
    )


def _make_request(backend: Backend = Backend.CUSTOM) -> GenerationRequest:
    config = GeneratorConfig(
        backend=backend,
        params={},
        formats=(ColorFormat.JSON,),
        output_dir=Path("/tmp/output"),
    )
    return GenerationRequest(
        image_path=Path("/tmp/wallpaper.png"),
        config=config,
    )


class TestLocalProcessor:
    def test_process_generate_returns_successful_result(self) -> None:
        scheme = _make_scheme()
        mock_gen = MagicMock()
        mock_gen.is_available.return_value = True
        mock_gen.generate.return_value = scheme

        registry = {Backend.CUSTOM: mock_gen}
        processor = LocalProcessor(registry)

        result = processor.process_generate(_make_request(), object())

        assert isinstance(result, GenerationResult)
        assert result.success is True
        assert result.color_scheme == scheme
        assert result.output_files == ()
        assert result.backend == Backend.CUSTOM
        assert result.stderr == ""
        assert result.return_code == 0
        assert isinstance(result.duration, float)
        assert result.duration >= 0

    def test_process_generate_measures_duration(self) -> None:
        scheme = _make_scheme()
        mock_gen = MagicMock()
        mock_gen.is_available.return_value = True
        mock_gen.generate.return_value = scheme

        registry = {Backend.CUSTOM: mock_gen}
        processor = LocalProcessor(registry)

        result = processor.process_generate(_make_request(), object())

        assert result.duration > 0

    def test_process_show_returns_color_scheme(self) -> None:
        scheme = _make_scheme()
        mock_gen = MagicMock()
        mock_gen.is_available.return_value = True
        mock_gen.generate.return_value = scheme

        registry = {Backend.CUSTOM: mock_gen}
        processor = LocalProcessor(registry)

        result = processor.process_show(_make_request(), object())

        assert isinstance(result, GenerationResult)
        assert result.success is True
        assert result.color_scheme == scheme
        assert result.output_files == ()
        assert result.stderr == ""
        assert result.return_code == 0

    def test_unavailable_backend_raises_error_before_generate(self) -> None:
        mock_gen = MagicMock()
        mock_gen.is_available.return_value = False

        registry = {Backend.CUSTOM: mock_gen}
        processor = LocalProcessor(registry)

        with pytest.raises(BackendNotAvailableError) as exc_info:
            processor.process_generate(_make_request(), object())

        assert exc_info.value.backend == Backend.CUSTOM
        assert "pip install color-scheme-generator[custom]" in exc_info.value.hint
        mock_gen.generate.assert_not_called()

    def test_unavailable_backend_show_raises_before_generate(self) -> None:
        mock_gen = MagicMock()
        mock_gen.is_available.return_value = False

        registry = {Backend.CUSTOM: mock_gen}
        processor = LocalProcessor(registry)

        with pytest.raises(BackendNotAvailableError):
            processor.process_show(_make_request(), object())

        mock_gen.generate.assert_not_called()

    def test_unknown_backend_raises_backend_not_registered_error(self) -> None:
        registry: dict[Backend, MagicMock] = {}
        processor = LocalProcessor(registry)

        with pytest.raises(BackendNotRegisteredError) as exc_info:
            processor.process_generate(_make_request(), object())

        assert exc_info.value.backend == Backend.CUSTOM
        assert "not found in registry" in str(exc_info.value)

    def test_isinstance_check_passes(self) -> None:
        registry = {Backend.CUSTOM: MagicMock()}
        processor = LocalProcessor(registry)

        assert isinstance(processor, ColorSchemeProcessorPort)

    def test_availability_hint_custom(self) -> None:
        mock_gen = MagicMock()
        mock_gen.is_available.return_value = False
        registry = {Backend.CUSTOM: mock_gen}
        processor = LocalProcessor(registry)

        with pytest.raises(BackendNotAvailableError) as exc_info:
            processor.process_generate(_make_request(), object())

        assert exc_info.value.hint == "pip install color-scheme-generator[custom]"

    def test_availability_hint_pywal(self) -> None:
        mock_gen = MagicMock()
        mock_gen.is_available.return_value = False
        registry = {Backend.PYWAL: mock_gen}
        processor = LocalProcessor(registry)

        with pytest.raises(BackendNotAvailableError) as exc_info:
            processor.process_generate(_make_request(Backend.PYWAL), object())

        assert exc_info.value.hint == "pip install color-scheme-generator[pywal]"

    def test_availability_hint_wallust(self) -> None:
        mock_gen = MagicMock()
        mock_gen.is_available.return_value = False
        registry = {Backend.WALLUST: mock_gen}
        processor = LocalProcessor(registry)

        with pytest.raises(BackendNotAvailableError) as exc_info:
            processor.process_generate(_make_request(Backend.WALLUST), object())

        assert exc_info.value.hint == "Install wallust binary"

    def test_process_show_unknown_backend_raises_error(self) -> None:
        registry: dict[Backend, MagicMock] = {}
        processor = LocalProcessor(registry)

        with pytest.raises(BackendNotRegisteredError) as exc_info:
            processor.process_show(_make_request(), object())

        assert exc_info.value.backend == Backend.CUSTOM

    def test_generate_renders_templates(self) -> None:
        scheme = _make_scheme()
        mock_gen = MagicMock()
        mock_gen.is_available.return_value = True
        mock_gen.generate.return_value = scheme

        mock_renderer = MagicMock()
        registry = {Backend.CUSTOM: mock_gen}
        processor = LocalProcessor(registry, template_renderer=mock_renderer)

        result = processor.process_generate(_make_request(), object())

        assert mock_renderer.render.called
        assert result.output_files != ()

    def test_show_does_not_render_templates(self) -> None:
        scheme = _make_scheme()
        mock_gen = MagicMock()
        mock_gen.is_available.return_value = True
        mock_gen.generate.return_value = scheme

        mock_renderer = MagicMock()
        registry = {Backend.CUSTOM: mock_gen}
        processor = LocalProcessor(registry, template_renderer=mock_renderer)

        result = processor.process_show(_make_request(), object())

        mock_renderer.render.assert_not_called()
        assert result.output_files == ()

    def test_output_files_populated_in_result(self) -> None:
        scheme = _make_scheme()
        mock_gen = MagicMock()
        mock_gen.is_available.return_value = True
        mock_gen.generate.return_value = scheme

        mock_renderer = MagicMock()
        registry = {Backend.CUSTOM: mock_gen}
        processor = LocalProcessor(registry, template_renderer=mock_renderer)

        result = processor.process_generate(_make_request(), object())

        assert len(result.output_files) > 0
        assert all(isinstance(f, Path) for f in result.output_files)


class TestCreateBackendRegistry:
    def test_returns_dict_with_all_three_backends(self) -> None:
        from color_scheme_generator.factory import create_backend_registry

        registry = create_backend_registry()

        assert Backend.CUSTOM in registry
        assert Backend.PYWAL in registry
        assert Backend.WALLUST in registry
        assert len(registry) == 3
