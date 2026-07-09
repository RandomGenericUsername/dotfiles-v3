from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from wallpaper_effects_generator.adapters.container_processor import (
    ContainerProcessor,
)
from wallpaper_effects_generator.domain.models import (
    CommandResult,
    ContainerSettings,
    EffectsCatalog,
    ProcessingRequest,
)


@pytest.fixture
def mock_runner() -> Mock:
    runner = Mock()
    runner.execute.return_value = CommandResult(
        stdout="ok", stderr="", return_code=0, duration=0.1
    )
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
def processor(mock_runner: Mock, catalog: EffectsCatalog) -> ContainerProcessor:
    return ContainerProcessor(
        command_runner=mock_runner,
        catalog=catalog,
        output_dir=Path("/tmp/out"),
        container_settings=ContainerSettings(engine="docker"),
    )


class TestContainerProcessor:
    def test_process_effect_success(self, processor: ContainerProcessor, mock_runner: Mock) -> None:
        request = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        result = processor.process_effect("blur", request, {"radius": "0x8"})
        assert result.success
        assert "weg process effect blur" in result.command
        mock_runner.execute.assert_called_once()
        cmd_list = mock_runner.execute.call_args[0][0]
        assert isinstance(cmd_list, list)
        assert "docker" in cmd_list[0]
        assert "/input/img.png" in " ".join(cmd_list)

    def test_process_effect_not_found(self, processor: ContainerProcessor) -> None:
        request = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        from wallpaper_effects_generator.domain.exceptions import EffectNotFoundError
        with pytest.raises(EffectNotFoundError):
            processor.process_effect("nonexistent", request)

    def test_process_composite_success(
        self, processor: ContainerProcessor, mock_runner: Mock
    ) -> None:
        request = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        result = processor.process_composite("blur-resize", request)
        assert result.success
        assert mock_runner.execute.call_count >= 1

    def test_process_composite_not_found(self, processor: ContainerProcessor) -> None:
        request = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        from wallpaper_effects_generator.domain.exceptions import CompositeNotFoundError
        with pytest.raises(CompositeNotFoundError):
            processor.process_composite("nonexistent", request)

    def test_process_preset_success(
        self, processor: ContainerProcessor, mock_runner: Mock
    ) -> None:
        request = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        result = processor.process_preset("social", request)
        assert result.success
        mock_runner.execute.assert_called_once()

    def test_process_preset_not_found(self, processor: ContainerProcessor) -> None:
        request = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        from wallpaper_effects_generator.domain.exceptions import PresetNotFoundError
        with pytest.raises(PresetNotFoundError):
            processor.process_preset("nonexistent", request)

    def test_process_batch_not_implemented(self, processor: ContainerProcessor) -> None:
        with pytest.raises(NotImplementedError):
            processor.process_batch(None)

    def test_uses_oci_command_runner(
        self, catalog: EffectsCatalog
    ) -> None:
        mock_runner = Mock()
        mock_runner.execute.return_value = CommandResult(
            stdout="ok", stderr="", return_code=0, duration=0.1
        )
        processor = ContainerProcessor(
            command_runner=mock_runner,
            catalog=catalog,
            output_dir=Path("/tmp/out"),
            container_settings=ContainerSettings(engine="podman"),
        )
        request = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        processor.process_effect("blur", request, {"radius": "0x8"})
        cmd_list = mock_runner.execute.call_args[0][0]
        assert isinstance(cmd_list, list)
        assert cmd_list[0] == "podman"

    def test_temp_cleanup_on_success(
        self, processor: ContainerProcessor, mock_runner: Mock
    ) -> None:
        request = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        with patch(
            "wallpaper_effects_generator.adapters.container_processor.tempfile.NamedTemporaryFile",
        ) as mock_temp:
            mock_temp.return_value.__enter__.return_value.name = "/tmp/test_weg.toml"
            result = processor.process_effect("blur", request, {"radius": "0x8"})
            assert result.success
