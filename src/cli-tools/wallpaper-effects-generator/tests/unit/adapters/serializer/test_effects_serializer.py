from __future__ import annotations

from pathlib import Path

import yaml

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
            effects=(EffectDefinition(name="test", description="Test", command="echo"),),
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

    def test_round_trip_zero_parameters(self, tmp_path: Path) -> None:
        original = EffectsCatalog(
            effects=(
                EffectDefinition(
                    name="noop",
                    description="No-op effect",
                    command="true",
                    parameters=(),
                ),
            ),
        )
        path = tmp_path / "effects.yaml"
        serializer = EffectsSerializer()
        serializer.serialize(original, path)
        restored = serializer.deserialize(path)
        assert len(restored.effects) == 1
        assert restored.effects[0].parameters == ()

    def test_round_trip_bounded_parameters(self, tmp_path: Path) -> None:
        original = EffectsCatalog(
            effects=(
                EffectDefinition(
                    name="contrast",
                    description="Adjust contrast",
                    command="magick {{input}} -contrast {{level}} {{output}}",
                    parameters=(
                        ParameterDefinition(
                            key="level", description="Contrast level", default="50", min=0, max=100
                        ),
                    ),
                ),
            ),
        )
        path = tmp_path / "effects.yaml"
        serializer = EffectsSerializer()
        serializer.serialize(original, path)
        restored = serializer.deserialize(path)
        assert len(restored.effects) == 1
        param = restored.effects[0].parameters[0]
        assert param.min == 0
        assert param.max == 100
        assert param.key == "level"

    def test_round_trip_required_parameter(self, tmp_path: Path) -> None:
        original = EffectsCatalog(
            effects=(
                EffectDefinition(
                    name="crop",
                    description="Crop image",
                    command="magick {{input}} -crop {{size}} {{output}}",
                    parameters=(
                        ParameterDefinition(
                            key="size", description="Crop size", default="800x600", required=True
                        ),
                    ),
                ),
            ),
        )
        path = tmp_path / "effects.yaml"
        serializer = EffectsSerializer()
        serializer.serialize(original, path)
        restored = serializer.deserialize(path)
        assert len(restored.effects) == 1
        param = restored.effects[0].parameters[0]
        assert param.required is True
        assert param.key == "size"

    def test_round_trip_type_variants(self, tmp_path: Path) -> None:
        original = EffectsCatalog(
            effects=(
                EffectDefinition(
                    name="multi-param",
                    description="Effect with all param types",
                    command="magick {{input}} {{args}} {{output}}",
                    parameters=(
                        ParameterDefinition(
                            key="string_val", description="A string", default="hello"
                        ),
                        ParameterDefinition(key="int_val", description="An int", default=42),
                        ParameterDefinition(key="float_val", description="A float", default=3.14),
                        ParameterDefinition(key="bool_val", description="A bool", default=True),
                        ParameterDefinition(key="no_default", description="No default"),
                    ),
                ),
            ),
        )
        path = tmp_path / "effects.yaml"
        serializer = EffectsSerializer()
        serializer.serialize(original, path)
        restored = serializer.deserialize(path)
        assert len(restored.effects) == 1
        params = {p.key: p for p in restored.effects[0].parameters}
        assert params["string_val"].default == "hello"
        assert params["int_val"].default == 42
        assert params["float_val"].default == 3.14
        assert params["bool_val"].default is True
        assert params["no_default"].default is None

    def test_round_trip_yaml_contains_parameter_bounds(self, tmp_path: Path) -> None:
        original = EffectsCatalog(
            effects=(
                EffectDefinition(
                    name="bounded",
                    description="Bounded effect",
                    command="true",
                    parameters=(
                        ParameterDefinition(
                            key="level",
                            description="Level",
                            default="5",
                            min=1,
                            max=10,
                            required=True,
                        ),
                    ),
                ),
            ),
        )
        path = tmp_path / "effects.yaml"
        serializer = EffectsSerializer()
        serializer.serialize(original, path)
        content = path.read_text()
        data = yaml.safe_load(content)
        param = data["effects"][0]["parameters"]["level"]
        assert param["min"] == 1
        assert param["max"] == 10
        assert param["required"] is True
        assert param["type"] == "str"
