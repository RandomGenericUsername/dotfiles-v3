from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from wallpaper_effects_generator.adapters.dry_run_processor import DryRunProcessor
from wallpaper_effects_generator.domain.exceptions import (
    CompositeNotFoundError,
    EffectNotFoundError,
    PresetNotFoundError,
)
from wallpaper_effects_generator.domain.models import EffectsCatalog, ProcessingRequest


@pytest.fixture
def mock_runner() -> Mock:
    runner = Mock()
    runner.is_available.return_value = True
    runner.get_binary.return_value = "magick"
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
def processor(mock_runner: Mock, catalog: EffectsCatalog, tmp_path: Path) -> DryRunProcessor:
    output_dir = tmp_path / "out"
    output_dir.mkdir(parents=True, exist_ok=True)
    return DryRunProcessor(
        command_runner=mock_runner,
        catalog=catalog,
        output_dir=output_dir,
    )


class TestDryRunProcessor:
    def test_process_effect_renders_command(
        self, processor: DryRunProcessor, tmp_path: Path
    ) -> None:
        input_file = tmp_path / "img.png"
        input_file.write_text("dummy")
        request = ProcessingRequest(
            input_path=input_file,
            output_path=tmp_path / "out.png",
        )
        result = processor.process_effect("blur", request, {"radius": "0x8"})
        assert result.success
        assert "magick" in result.command
        assert "{{" not in result.command

    def test_process_effect_not_found(self, processor: DryRunProcessor, tmp_path: Path) -> None:
        input_file = tmp_path / "img.png"
        input_file.write_text("dummy")
        request = ProcessingRequest(
            input_path=input_file,
            output_path=tmp_path / "out.png",
        )
        with pytest.raises(EffectNotFoundError):
            processor.process_effect("nonexistent", request)

    def test_process_composite_renders_commands(
        self, processor: DryRunProcessor, tmp_path: Path
    ) -> None:
        input_file = tmp_path / "img.png"
        input_file.write_text("dummy")
        request = ProcessingRequest(
            input_path=input_file,
            output_path=tmp_path / "out.png",
        )
        result = processor.process_composite("blur-resize", request)
        assert result.success
        assert ";" in result.command

    def test_process_composite_not_found(self, processor: DryRunProcessor, tmp_path: Path) -> None:
        input_file = tmp_path / "img.png"
        input_file.write_text("dummy")
        request = ProcessingRequest(
            input_path=input_file,
            output_path=tmp_path / "out.png",
        )
        with pytest.raises(CompositeNotFoundError):
            processor.process_composite("nonexistent", request)

    def test_process_preset_renders_commands(
        self, processor: DryRunProcessor, tmp_path: Path
    ) -> None:
        input_file = tmp_path / "img.png"
        input_file.write_text("dummy")
        request = ProcessingRequest(
            input_path=input_file,
            output_path=tmp_path / "out.png",
        )
        result = processor.process_preset("social", request)
        assert result.success
        assert "magick" in result.command

    def test_process_preset_not_found(self, processor: DryRunProcessor, tmp_path: Path) -> None:
        input_file = tmp_path / "img.png"
        input_file.write_text("dummy")
        request = ProcessingRequest(
            input_path=input_file,
            output_path=tmp_path / "out.png",
        )
        with pytest.raises(PresetNotFoundError):
            processor.process_preset("nonexistent", request)

    def test_pre_flight_input_not_found(self, processor: DryRunProcessor, tmp_path: Path) -> None:
        request = ProcessingRequest(
            input_path=tmp_path / "nonexistent.png",
            output_path=tmp_path / "out.png",
        )
        result = processor.process_effect("blur", request)
        assert not result.success
        assert "Input not found" in result.stderr

    def test_pre_flight_binary_unavailable(
        self, mock_runner: Mock, catalog: EffectsCatalog, tmp_path: Path
    ) -> None:
        mock_runner.is_available.return_value = False
        processor = DryRunProcessor(
            command_runner=mock_runner,
            catalog=catalog,
            output_dir=tmp_path,
        )
        input_file = tmp_path / "img.png"
        input_file.write_text("dummy")
        request = ProcessingRequest(
            input_path=input_file,
            output_path=tmp_path / "out.png",
        )
        result = processor.process_effect("blur", request)
        assert not result.success
        assert "Binary not available" in result.stderr

    def test_process_batch_not_implemented(self, processor: DryRunProcessor) -> None:
        with pytest.raises(NotImplementedError):
            processor.process_batch(None)  # type: ignore[arg-type]
