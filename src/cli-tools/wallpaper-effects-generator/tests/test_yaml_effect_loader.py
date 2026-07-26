from __future__ import annotations

from pathlib import Path

import pytest
from config_assembler_engine import ConfigAssemblerError

from wallpaper_effects_generator.adapters.yaml_effect_loader import YamlEffectLoader
from wallpaper_effects_generator.domain.enums import ItemType
from wallpaper_effects_generator.domain.exceptions import EffectsValidationError
from wallpaper_effects_generator.ports.effect_loader import EffectLoaderPort


def test_is_effect_loader_port():
    assert isinstance(YamlEffectLoader(), EffectLoaderPort)


def test_load_effects_from_explicit_path(tmp_path: Path):
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text("""
version: "1.0"
parameter_types:
  radius:
    type: int
    description: "Blur radius"
effects:
  - name: blur
    description: "Gaussian blur"
    command: "convert {input} -blur {radius}x{sigma} {output}"
    parameters:
      radius:
        type: int
        description: "Blur radius"
      sigma:
        type: float
        description: "Blur sigma"
    item_type: "effect"
composites:
  - name: vintage
    description: "Vintage photo effect"
    steps:
      - effect_name: blur
        parameters:
          radius: "3"
          sigma: "0.8"
presets:
  - name: cinematic
    description: "Cinematic look"
    effects:
      - blur
""")

    loader = YamlEffectLoader()
    catalog = loader.load(path=effects_file)

    assert len(catalog.effects) == 1
    blur = catalog.effects[0]
    assert blur.name == "blur"
    assert blur.description == "Gaussian blur"
    assert "convert {input}" in blur.command
    assert blur.item_type == ItemType.EFFECT
    assert loader.get_resolved_path() == effects_file.resolve()

    assert len(catalog.composites) == 1
    assert catalog.composites[0].name == "vintage"
    assert len(catalog.composites[0].steps) == 1
    assert catalog.composites[0].steps[0].effect_name == "blur"

    assert len(catalog.presets) == 1
    assert catalog.presets[0].name == "cinematic"
    assert catalog.presets[0].effects == ("blur",)


def test_load_effects_with_composite_item_type_preserved(tmp_path: Path):
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text("""
version: "1.0"
effects:
  - name: vignette
    description: "Vignette effect"
    command: "vignette command"
    item_type: "composite"
""")

    loader = YamlEffectLoader()
    catalog = loader.load(path=effects_file)

    assert catalog.effects[0].item_type == ItemType.COMPOSITE


def test_load_empty_effects(tmp_path: Path):
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text('version: "1.0"\n')

    loader = YamlEffectLoader()
    catalog = loader.load(path=effects_file)

    assert len(catalog.effects) == 0
    assert len(catalog.composites) == 0
    assert len(catalog.presets) == 0


def test_get_default_path():
    loader = YamlEffectLoader()
    assert loader.get_default_path() == Path("effects.yaml")


def test_get_resolved_path_none_before_load():
    loader = YamlEffectLoader()
    assert loader.get_resolved_path() is None


def test_load_file_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    loader = YamlEffectLoader()
    nonexistent = tmp_path / "nonexistent.yaml"

    with pytest.raises(ConfigAssemblerError):
        loader.load(path=nonexistent)


def test_load_rejects_param_default_below_min(tmp_path: Path):
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text("""
version: "1.0"
parameter_types:
  percent:
    type: integer
    min: -100
    max: 100
effects:
  - name: brightness
    description: Brightness
    command: "magick {input} {output}"
    parameters:
      amount:
        type: percent
        description: Amount
        default: -150
""")
    loader = YamlEffectLoader()
    with pytest.raises(EffectsValidationError, match="below minimum"):
        loader.load(path=effects_file)


def test_load_rejects_param_default_above_max(tmp_path: Path):
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text("""
version: "1.0"
parameter_types:
  percentage:
    type: integer
    min: 0
    max: 100
effects:
  - name: opacity
    description: Opacity
    command: "magick {input} {output}"
    parameters:
      level:
        type: percentage
        description: Level
        default: 150
""")
    loader = YamlEffectLoader()
    with pytest.raises(EffectsValidationError, match="above maximum"):
        loader.load(path=effects_file)


def test_load_accepts_in_bounds_param_default(tmp_path: Path):
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text("""
version: "1.0"
parameter_types:
  percent:
    type: integer
    min: -100
    max: 100
effects:
  - name: brightness
    description: Brightness
    command: "magick {input} {output}"
    parameters:
      amount:
        type: percent
        description: Amount
        default: -20
""")
    loader = YamlEffectLoader()
    catalog = loader.load(path=effects_file)
    assert len(catalog.effects) == 1
    assert catalog.effects[0].name == "brightness"


def test_load_accepts_inline_min_max(tmp_path: Path):
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text("""
version: "1.0"
effects:
  - name: opacity
    description: Opacity
    command: "magick {input} {output}"
    parameters:
      level:
        type: integer
        description: Level
        default: 50
        min: 0
        max: 100
""")
    loader = YamlEffectLoader()
    catalog = loader.load(path=effects_file)
    assert len(catalog.effects) == 1
    assert catalog.effects[0].parameters[0].min == 0.0
    assert catalog.effects[0].parameters[0].max == 100.0
