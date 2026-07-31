from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from wallpaper_effects_generator.adapters.local_processor import LocalProcessor
from wallpaper_effects_generator.domain.exceptions import (
    CompositeNotFoundError,
    EffectNotFoundError,
    PresetNotFoundError,
)
from wallpaper_effects_generator.domain.models import (
    CommandResult,
    EffectsCatalog,
    ProcessingRequest,
)


@pytest.fixture
def mock_runner() -> Mock:
    runner = Mock()
    runner.execute.return_value = CommandResult(stdout="ok", stderr="", return_code=0, duration=0.1)
    return runner


@pytest.fixture
def catalog() -> EffectsCatalog:
    from wallpaper_effects_generator.domain.models import (
        ChainStep,
        CompositeDefinition,
        EffectDefinition,
        ParameterDefinition,
        PresetDefinition,
    )

    return EffectsCatalog(
        effects=(
            EffectDefinition(
                name="blur",
                description="Blur effect",
                command="magick {{input}} -blur {{radius}} {{output}}",
                parameters=(
                    ParameterDefinition(key="radius", description="Radius", default="0x8"),
                ),
            ),
            EffectDefinition(
                name="resize",
                description="Resize effect",
                command="magick {{input}} -resize {{size}} {{output}}",
                parameters=(ParameterDefinition(key="size", description="Size", default="50%"),),
            ),
        ),
        composites=(
            CompositeDefinition(
                name="blur-resize",
                description="Blur then resize",
                steps=(
                    ChainStep(effect_name="blur", parameters={"radius": "0x4"}),
                    ChainStep(effect_name="resize", parameters={"size": "800"}),
                ),
            ),
        ),
        presets=(
            PresetDefinition(
                name="social",
                description="Social media preset",
                effects=("resize",),
            ),
        ),
    )


@pytest.fixture
def processor(mock_runner: Mock, catalog: EffectsCatalog) -> LocalProcessor:
    return LocalProcessor(
        command_runner=mock_runner,
        catalog=catalog,
        output_dir=Path("/tmp/out"),
    )


class TestLocalProcessor:
    def test_process_effect_success(self, processor: LocalProcessor, mock_runner: Mock) -> None:
        request = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        result = processor.process_effect("blur", request, {"radius": "0x8"})
        assert result.success
        assert "magick" in result.command
        mock_runner.execute.assert_called_once()

    def test_process_effect_not_found(self, processor: LocalProcessor) -> None:
        request = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        with pytest.raises(EffectNotFoundError):
            processor.process_effect("nonexistent", request)

    def test_process_composite_success(self, processor: LocalProcessor, mock_runner: Mock) -> None:
        request = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        result = processor.process_composite("blur-resize", request)
        assert result.success
        assert mock_runner.execute.call_count == 2

    def test_process_composite_not_found(self, processor: LocalProcessor) -> None:
        request = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        with pytest.raises(CompositeNotFoundError):
            processor.process_composite("nonexistent", request)

    def test_process_preset_success(self, processor: LocalProcessor, mock_runner: Mock) -> None:
        request = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        result = processor.process_preset("social", request)
        assert result.success
        mock_runner.execute.assert_called_once()

    def test_process_preset_not_found(self, processor: LocalProcessor) -> None:
        request = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        with pytest.raises(PresetNotFoundError):
            processor.process_preset("nonexistent", request)

    def test_process_effect_with_output_path(
        self, processor: LocalProcessor, mock_runner: Mock
    ) -> None:
        request = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        result = processor.process_effect("blur", request, {"radius": "0x8"})
        assert result.output_path is not None

    def test_process_composite_step_failure(
        self, processor: LocalProcessor, mock_runner: Mock
    ) -> None:
        mock_runner.execute.return_value = CommandResult(
            stdout="", stderr="error", return_code=1, duration=0.1
        )
        request = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        result = processor.process_composite("blur-resize", request)
        assert not result.success

    def test_process_batch_not_implemented(self, processor: LocalProcessor) -> None:
        with pytest.raises(NotImplementedError):
            processor.process_batch(None)  # type: ignore[arg-type]
