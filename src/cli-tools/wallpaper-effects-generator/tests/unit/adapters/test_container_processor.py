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
def mock_engine() -> Mock:
    engine = Mock()
    engine.images.exists.return_value = True
    caps = Mock()
    caps.default_run_flags = []
    engine.capabilities = caps

    def _run_container(run_config: object) -> None:
        for vol in run_config.volumes:
            if vol.target == "/output":
                out_dir = Path(vol.source)
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "img.png").write_text("")
                break

    engine.containers.run.side_effect = _run_container
    return engine


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
def processor(mock_engine: Mock, catalog: EffectsCatalog, tmp_path: Path) -> ContainerProcessor:
    return ContainerProcessor(
        command_runner=Mock(),
        catalog=catalog,
        output_dir=tmp_path,
        container_engine=mock_engine,
        container_settings=ContainerSettings(engine="docker"),
    )


class TestContainerProcessor:
    def test_process_effect_success(self, processor: ContainerProcessor, tmp_path: Path) -> None:
        request = ProcessingRequest(
            input_path=tmp_path / "img.png",
            output_path=tmp_path / "img.png",
        )
        result = processor.process_effect("blur", request, {"radius": "0x8"})
        assert result.success
        assert "process effect blur" in result.command
        assert "/input/img.png" in result.command

    def test_process_effect_not_found(self, processor: ContainerProcessor) -> None:
        request = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        from wallpaper_effects_generator.domain.exceptions import EffectNotFoundError
        with pytest.raises(EffectNotFoundError):
            processor.process_effect("nonexistent", request)

    def test_process_composite_success(self, processor: ContainerProcessor, tmp_path: Path) -> None:
        request = ProcessingRequest(
            input_path=tmp_path / "img.png",
            output_path=tmp_path / "img.png",
        )
        result = processor.process_composite("blur-resize", request)
        assert result.success

    def test_process_composite_not_found(self, processor: ContainerProcessor) -> None:
        request = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        from wallpaper_effects_generator.domain.exceptions import CompositeNotFoundError
        with pytest.raises(CompositeNotFoundError):
            processor.process_composite("nonexistent", request)

    def test_process_preset_success(self, processor: ContainerProcessor, tmp_path: Path) -> None:
        request = ProcessingRequest(
            input_path=tmp_path / "img.png",
            output_path=tmp_path / "img.png",
        )
        result = processor.process_preset("social", request)
        assert result.success

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

    def test_uses_oci_command_runner(self, catalog: EffectsCatalog, tmp_path: Path) -> None:
        mock_engine = Mock()
        mock_engine.images.exists.return_value = True
        caps = Mock()
        caps.default_run_flags = []
        mock_engine.capabilities = caps

        def _run_container(run_config: object) -> None:
            for vol in run_config.volumes:
                if vol.target == "/output":
                    Path(vol.source).mkdir(parents=True, exist_ok=True)
                    (Path(vol.source) / "img.png").write_text("")
                    break

        mock_engine.containers.run.side_effect = _run_container

        processor = ContainerProcessor(
            command_runner=Mock(),
            catalog=catalog,
            output_dir=tmp_path,
            container_engine=mock_engine,
            container_settings=ContainerSettings(engine="podman"),
        )
        request = ProcessingRequest(
            input_path=tmp_path / "img.png",
            output_path=tmp_path / "img.png",
        )
        result = processor.process_effect("blur", request, {"radius": "0x8"})
        assert result.success
        assert "process effect blur" in result.command

    def test_temp_cleanup_on_success(self, processor: ContainerProcessor, tmp_path: Path) -> None:
        request = ProcessingRequest(
            input_path=tmp_path / "img.png",
            output_path=tmp_path / "img.png",
        )
        with patch(
            "wallpaper_effects_generator.adapters.container_processor.tempfile.NamedTemporaryFile",
        ) as mock_temp:
            mock_temp.return_value.__enter__.return_value.name = "/tmp/test_weg.toml"
            result = processor.process_effect("blur", request, {"radius": "0x8"})
            assert result.success
