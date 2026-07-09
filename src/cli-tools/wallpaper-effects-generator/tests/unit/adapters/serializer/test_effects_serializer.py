from __future__ import annotations

from pathlib import Path

from wallpaper_effects_generator.adapters.serializer.effects_serializer import (
    EffectsSerializer,
)
from wallpaper_effects_generator.domain.models import (
    ChainStep,
    CompositeDefinition,
    EffectDefinition,
    EffectsCatalog,
    ParameterDefinition,
    PresetDefinition,
)


class TestEffectsSerializer:
    def test_round_trip_empty(self, tmp_path: Path) -> None:
        original = EffectsCatalog()
        path = tmp_path / "effects.yaml"
        serializer = EffectsSerializer()
        serializer.serialize(original, path)
        restored = serializer.deserialize(path)
        assert len(restored.effects) == 0
        assert len(restored.composites) == 0
        assert len(restored.presets) == 0

    def test_round_trip_with_effects(self, tmp_path: Path) -> None:
        original = EffectsCatalog(
            effects=(
                EffectDefinition(
                    name="blur",
                    description="Blur effect",
                    command="magick {{input}} -blur {{radius}} {{output}}",
                    parameters=(
                        ParameterDefinition(key="radius", description="Radius", default="0x8"),
                    ),
                ),
            ),
        )
        path = tmp_path / "effects.yaml"
        serializer = EffectsSerializer()
        serializer.serialize(original, path)
        restored = serializer.deserialize(path)
        assert len(restored.effects) == 1
        assert restored.effects[0].name == "blur"
        assert restored.effects[0].command == "magick {{input}} -blur {{radius}} {{output}}"

    def test_round_trip_full_catalog(self, tmp_path: Path) -> None:
        original = EffectsCatalog(
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
                    parameters=(
                        ParameterDefinition(key="size", description="Size", default="50%"),
                    ),
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
        path = tmp_path / "effects.yaml"
        serializer = EffectsSerializer()
        serializer.serialize(original, path)
        restored = serializer.deserialize(path)
        assert len(restored.effects) == 2
        assert len(restored.composites) == 1
        assert len(restored.presets) == 1
        assert restored.composites[0].name == "blur-resize"
        assert len(restored.composites[0].steps) == 2
        assert restored.presets[0].name == "social"
        assert restored.presets[0].effects == ("resize",)

    def test_serialize_creates_yaml(self, tmp_path: Path) -> None:
        catalog = EffectsCatalog(
            effects=(
                EffectDefinition(name="test", description="Test", command="echo"),
            ),
        )
        serializer = EffectsSerializer()
        path = tmp_path / "out.yaml"
        serializer.serialize(catalog, path)
        assert path.exists()
        content = path.read_text()
        assert "name: test" in content

    def test_deserialize_missing_file(self, tmp_path: Path) -> None:
        import pytest
        serializer = EffectsSerializer()
        path = tmp_path / "nonexistent.yaml"
        assert not path.exists()
        with pytest.raises(FileNotFoundError):
            serializer.deserialize(path)
