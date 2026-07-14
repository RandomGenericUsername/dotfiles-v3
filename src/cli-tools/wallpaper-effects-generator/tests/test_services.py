from pathlib import Path

import pytest

from wallpaper_effects_generator.domain.enums import ItemType
from wallpaper_effects_generator.domain.exceptions import ConfigResolutionError
from wallpaper_effects_generator.domain.models import (
    ChainStep,
    CompositeDefinition,
    EffectDefinition,
    EffectsCatalog,
    ParameterDefinition,
    PresetDefinition,
    ProcessingRequest,
)
from wallpaper_effects_generator.domain.services import (
    CatalogValidationService,
    CommandSubstitutionService,
    OutputPathService,
    ParameterResolutionService,
)


class TestCommandSubstitutionService:
    def test_substitute_input_output(self) -> None:
        svc = CommandSubstitutionService()
        request = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        result = svc.substitute("convert {{input}} {{output}}", {}, request)
        assert result == "convert /in/img.png /out/img.png"

    def test_substitute_with_params(self) -> None:
        svc = CommandSubstitutionService()
        request = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        result = svc.substitute(
            "convert -resize {{size}} {{input}} {{output}}",
            {"size": "800x600"},
            request,
        )
        assert "800x600" in result

    def test_substitute_injection_guarded(self) -> None:
        svc = CommandSubstitutionService()
        request = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        result = svc.substitute(
            "convert {{size}} {{input}}",
            {"size": "; rm -rf /"},
            request,
        )
        assert "';" in result


class TestParameterResolutionService:
    def test_resolve_default(self) -> None:
        svc = ParameterResolutionService()
        p = ParameterDefinition(key="size", description="Size", default="100")
        assert svc.resolve(p) == "100"

    def test_resolve_override(self) -> None:
        svc = ParameterResolutionService()
        p = ParameterDefinition(key="size", description="Size", default="100")
        assert svc.resolve(p, {"size": "200"}) == "200"

    def test_resolve_required_raises_when_missing(self) -> None:
        svc = ParameterResolutionService()
        p = ParameterDefinition(key="required_param", description="Required", required=True)
        with pytest.raises(ConfigResolutionError):
            svc.resolve(p)

    def test_resolve_all(self) -> None:
        svc = ParameterResolutionService()
        params = (
            ParameterDefinition(key="a", description="A", default="1"),
            ParameterDefinition(key="b", description="B", default="2"),
        )
        resolved = svc.resolve_all(params, {"b": "3"})
        assert resolved == {"a": "1", "b": "3"}


class TestOutputPathService:
    def test_nested_path(self) -> None:
        svc = OutputPathService()
        result = svc.resolve(
            input_path=Path("img.png"),
            output_dir=Path("/out"),
            item_type=ItemType.EFFECT,
        )
        assert result == Path("/out/effect/img.png")

    def test_flat_path(self) -> None:
        svc = OutputPathService()
        result = svc.resolve(
            input_path=Path("img.png"),
            output_dir=Path("/out"),
            item_type=ItemType.EFFECT,
            flat=True,
        )
        assert result == Path("/out/effect-img.png")

    def test_explicit_output_path(self) -> None:
        svc = OutputPathService()
        result = svc.resolve(
            input_path=Path("img.png"),
            output_dir=Path("/out"),
            item_type=ItemType.EFFECT,
            explicit_output=True,
        )
        assert result == Path("/out/effect-img.png")

    def test_composite_subdir(self) -> None:
        svc = OutputPathService()
        result = svc.resolve(
            input_path=Path("img.png"),
            output_dir=Path("/out"),
            item_type=ItemType.COMPOSITE,
        )
        assert result == Path("/out/composite/img.png")

    def test_preset_subdir(self) -> None:
        svc = OutputPathService()
        result = svc.resolve(
            input_path=Path("img.png"),
            output_dir=Path("/out"),
            item_type=ItemType.PRESET,
        )
        assert result == Path("/out/preset/img.png")

    def test_batch_output_dir_nested(self) -> None:
        svc = OutputPathService()
        result = svc.batch_output_dir(
            input_path=Path("/in"),
            output_dir=Path("/out"),
            flat=False,
            explicit_output=False,
        )
        assert result == Path("/out/in")

    def test_batch_output_dir_flat(self) -> None:
        svc = OutputPathService()
        result = svc.batch_output_dir(
            input_path=Path("/in"),
            output_dir=Path("/out"),
            flat=True,
            explicit_output=False,
        )
        assert result == Path("/out/in")

    def test_batch_output_dir_explicit(self) -> None:
        svc = OutputPathService()
        result = svc.batch_output_dir(
            input_path=Path("/in"),
            output_dir=Path("/out"),
            flat=False,
            explicit_output=True,
        )
        assert result == Path("/out")

    def test_resolve_explicit_output(self) -> None:
        svc = OutputPathService()
        result = svc.resolve(
            input_path=Path("img.png"),
            output_dir=Path("/out"),
            item_type=ItemType.EFFECT,
            explicit_output=True,
            output_name="blur",
        )
        assert result == Path("/out/effect-blur.png")

    def test_resolve_flat_no_explicit(self) -> None:
        svc = OutputPathService()
        result = svc.resolve(
            input_path=Path("img.png"),
            output_dir=Path("/out/input_stem"),
            item_type=ItemType.EFFECT,
            flat=True,
        )
        assert result == Path("/out/input_stem/effect-img.png")

    def test_resolve_nested_default(self) -> None:
        svc = OutputPathService()
        result = svc.resolve(
            input_path=Path("img.png"),
            output_dir=Path("/out/input_stem"),
            item_type=ItemType.EFFECT,
        )
        assert result == Path("/out/input_stem/effect/img.png")

    def test_resolve_with_output_name(self) -> None:
        svc = OutputPathService()
        result = svc.resolve(
            input_path=Path("photo.png"),
            output_dir=Path("/out/input_stem"),
            item_type=ItemType.COMPOSITE,
            output_name="my-composite",
        )
        assert result == Path("/out/input_stem/composite/my-composite.png")

    def test_resolve_composite_subdir(self) -> None:
        svc = OutputPathService()
        result = svc.resolve(
            input_path=Path("img.png"),
            output_dir=Path("/out"),
            item_type=ItemType.COMPOSITE,
        )
        assert result == Path("/out/composite/img.png")

    def test_resolve_preset_subdir(self) -> None:
        svc = OutputPathService()
        result = svc.resolve(
            input_path=Path("img.png"),
            output_dir=Path("/out"),
            item_type=ItemType.PRESET,
        )
        assert result == Path("/out/preset/img.png")


class TestCatalogValidationService:
    def test_valid_catalog(self) -> None:
        svc = CatalogValidationService()
        catalog = EffectsCatalog(
            effects=(EffectDefinition(name="blur", description="Blur", command="blur"),),
        )
        assert svc.validate(catalog) == []

    def test_composite_refers_to_unknown_effect(self) -> None:
        svc = CatalogValidationService()
        catalog = EffectsCatalog(
            composites=(
                CompositeDefinition(
                    name="my-composite",
                    description="Test",
                    steps=(ChainStep(effect_name="unknown"),),
                ),
            ),
        )
        errors = svc.validate(catalog)
        assert len(errors) == 1
        assert "unknown" in errors[0]

    def test_preset_refers_to_unknown_effect(self) -> None:
        svc = CatalogValidationService()
        catalog = EffectsCatalog(
            presets=(
                PresetDefinition(
                    name="my-preset",
                    description="Test",
                    effects=("unknown",),
                ),
            ),
        )
        errors = svc.validate(catalog)
        assert len(errors) == 1
        assert "unknown" in errors[0]

    def test_duplicate_effect_name_detected(self) -> None:
        svc = CatalogValidationService()
        catalog = EffectsCatalog(
            effects=(
                EffectDefinition(name="blur", description="Blur", command="blur"),
                EffectDefinition(name="blur", description="Duplicate", command="blur2"),
            ),
        )
        errors = svc.validate(catalog)
        assert any("Duplicate" in e for e in errors)

    def test_valid_composite_and_preset(self) -> None:
        svc = CatalogValidationService()
        catalog = EffectsCatalog(
            effects=(EffectDefinition(name="blur", description="Blur", command="blur"),),
            composites=(
                CompositeDefinition(
                    name="my-composite",
                    description="Test",
                    steps=(ChainStep(effect_name="blur"),),
                ),
            ),
            presets=(
                PresetDefinition(
                    name="my-preset",
                    description="Test",
                    effects=("blur",),
                ),
            ),
        )
        assert svc.validate(catalog) == []
