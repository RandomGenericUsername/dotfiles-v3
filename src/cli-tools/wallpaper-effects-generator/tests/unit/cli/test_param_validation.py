from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from wallpaper_effects_generator.cli.main import app

CONFIG_TOML = "\n".join(
    [
        'version = "1.0"',
        "[execution]",
        "[output]",
        "[runtime]",
        'mode = "local"',
        "[container]",
        'engine = "docker"',
    ]
)

EFFECTS_YAML = """version: '1.0'
effects:
  - name: blur
    description: Blur effect
    command: magick {{input}} -blur {{blur}} {{output}}
    parameters:
      blur:
        type: string
        default: "0x8"
  - name: blackwhite
    description: Convert to grayscale
    command: magick {{input}} -grayscale Average {{output}}
  - name: brightness
    description: Adjust brightness
    command: magick {{input}} -brightness-contrast {{brightness}}% {{output}}
    parameters:
      brightness:
        type: integer
        default: -20
  - name: contrast
    description: Adjust contrast
    command: magick {{input}} -brightness-contrast 0x{{contrast}}% {{output}}
    parameters:
      contrast:
        type: integer
        default: 20
composites:
  - name: blur-brightness80
    description: Blur then dim
    steps:
      - effect_name: blur
        parameters:
          blur: "0x8"
      - effect_name: brightness
        parameters:
          brightness: "-20"
  - name: blackwhite-blur
    description: Grayscale then blur
    steps:
      - effect_name: blackwhite
      - effect_name: blur
        parameters:
          blur: "0x8"
presets:
  - name: dark_blur
    description: Dark blurred background
    effects:
      - blur
      - brightness
  - name: high_contrast
    description: High contrast
    effects:
      - contrast
"""


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "settings.toml"
    path.write_text(CONFIG_TOML)
    return path


@pytest.fixture
def effects_file(tmp_path: Path) -> Path:
    path = tmp_path / "effects.yaml"
    path.write_text(EFFECTS_YAML)
    return path


@pytest.fixture
def input_file(tmp_path: Path) -> Path:
    path = tmp_path / "input.png"
    path.write_text("dummy")
    return path


class TestProcessEffectValidation:
    def test_effect_rejects_unknown_key(
        self,
        runner: CliRunner,
        config_file: Path,
        effects_file: Path,
        input_file: Path,
    ) -> None:
        result = runner.invoke(
            app,
            [
                "process",
                "--config",
                str(config_file),
                "--effects",
                str(effects_file),
                "effect",
                "blur",
                str(input_file),
                "--param",
                "bliur=0x15",
            ],
        )
        assert result.exit_code != 0
        assert "bliur" in result.output
        assert "effect 'blur'" in result.output
        assert "blur" in result.output

    def test_effect_rejects_param_for_zero_param_effect(
        self,
        runner: CliRunner,
        config_file: Path,
        effects_file: Path,
        input_file: Path,
    ) -> None:
        result = runner.invoke(
            app,
            [
                "process",
                "--config",
                str(config_file),
                "--effects",
                str(effects_file),
                "effect",
                "blackwhite",
                str(input_file),
                "--param",
                "brightness=50",
            ],
        )
        assert result.exit_code != 0
        assert "brightness" in result.output
        assert "blackwhite" in result.output
        assert "none declared" in result.output

    def test_effect_accepts_known_key(
        self,
        runner: CliRunner,
        config_file: Path,
        effects_file: Path,
        input_file: Path,
    ) -> None:
        result = runner.invoke(
            app,
            [
                "process",
                "--config",
                str(config_file),
                "--effects",
                str(effects_file),
                "effect",
                "blur",
                str(input_file),
                "--param",
                "blur=5x3",
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"


class TestProcessCompositeValidation:
    def test_composite_rejects_unknown_key(
        self,
        runner: CliRunner,
        config_file: Path,
        effects_file: Path,
        input_file: Path,
    ) -> None:
        result = runner.invoke(
            app,
            [
                "process",
                "--config",
                str(config_file),
                "--effects",
                str(effects_file),
                "composite",
                "blackwhite-blur",
                str(input_file),
                "--param",
                "shadow=3",
            ],
        )
        assert result.exit_code != 0
        assert "shadow" in result.output
        assert "blackwhite-blur" in result.output
        assert "for composite" in result.output

    def test_composite_accepts_key_declared_by_any_step(
        self,
        runner: CliRunner,
        config_file: Path,
        effects_file: Path,
        input_file: Path,
    ) -> None:
        result = runner.invoke(
            app,
            [
                "process",
                "--config",
                str(config_file),
                "--effects",
                str(effects_file),
                "composite",
                "blur-brightness80",
                str(input_file),
                "--param",
                "blur=5x3",
                "--param",
                "brightness=10",
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"


class TestProcessPresetValidation:
    def test_preset_accepts_key_declared_by_any_effect(
        self,
        runner: CliRunner,
        config_file: Path,
        effects_file: Path,
        input_file: Path,
    ) -> None:
        result = runner.invoke(
            app,
            [
                "process",
                "--config",
                str(config_file),
                "--effects",
                str(effects_file),
                "preset",
                "dark_blur",
                str(input_file),
                "--param",
                "brightness=-30",
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"


class TestBatchPerKindScoping:
    def test_batch_effects_accepts_key_declared_by_any_effect(
        self,
        runner: CliRunner,
        config_file: Path,
        effects_file: Path,
        input_file: Path,
    ) -> None:
        result = runner.invoke(
            app,
            [
                "batch",
                "--config",
                str(config_file),
                "--effects",
                str(effects_file),
                "effects",
                str(input_file),
                "--param",
                "blur=5x3",
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"

    def test_batch_composites_rejects_key_unknown_to_composites(
        self,
        runner: CliRunner,
        config_file: Path,
        effects_file: Path,
        input_file: Path,
    ) -> None:
        result = runner.invoke(
            app,
            [
                "batch",
                "--config",
                str(config_file),
                "--effects",
                str(effects_file),
                "composites",
                str(input_file),
                "--param",
                "contrast=40",
            ],
        )
        assert result.exit_code != 0
        assert "for batch composites" in result.output
        assert "contrast" in result.output
        assert "blur" in result.output
        assert "brightness" in result.output

    def test_batch_composites_accepts_key_valid_for_composite_steps(
        self,
        runner: CliRunner,
        config_file: Path,
        effects_file: Path,
        input_file: Path,
    ) -> None:
        result = runner.invoke(
            app,
            [
                "batch",
                "--config",
                str(config_file),
                "--effects",
                str(effects_file),
                "composites",
                str(input_file),
                "--param",
                "blur=5x3",
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"

    def test_batch_presets_rejects_key_unknown_to_presets(
        self,
        runner: CliRunner,
        config_file: Path,
        effects_file: Path,
        input_file: Path,
    ) -> None:
        result = runner.invoke(
            app,
            [
                "batch",
                "--config",
                str(config_file),
                "--effects",
                str(effects_file),
                "presets",
                str(input_file),
                "--param",
                "color=#ffffff",
            ],
        )
        assert result.exit_code != 0
        assert "for batch presets" in result.output
        assert "color" in result.output

    def test_batch_all_rejects_key_declared_nowhere(
        self,
        runner: CliRunner,
        config_file: Path,
        effects_file: Path,
        input_file: Path,
    ) -> None:
        result = runner.invoke(
            app,
            [
                "batch",
                "--config",
                str(config_file),
                "--effects",
                str(effects_file),
                "all",
                str(input_file),
                "--param",
                "typo=1",
            ],
        )
        assert result.exit_code != 0
        assert "typo" in result.output
        assert "for batch all" in result.output

    def test_batch_all_accepts_mixed_keys_declared_somewhere(
        self,
        runner: CliRunner,
        config_file: Path,
        effects_file: Path,
        input_file: Path,
    ) -> None:
        result = runner.invoke(
            app,
            [
                "batch",
                "--config",
                str(config_file),
                "--effects",
                str(effects_file),
                "all",
                str(input_file),
                "--param",
                "blur=5x3",
                "--param",
                "brightness=10",
                "--param",
                "contrast=40",
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"

    def test_batch_all_rejects_partially_unknown_key_set(
        self,
        runner: CliRunner,
        config_file: Path,
        effects_file: Path,
        input_file: Path,
    ) -> None:
        result = runner.invoke(
            app,
            [
                "batch",
                "--config",
                str(config_file),
                "--effects",
                str(effects_file),
                "all",
                str(input_file),
                "--param",
                "blur=5x3",
                "--param",
                "typo=1",
            ],
        )
        assert result.exit_code != 0
        assert "typo" in result.output


class TestBatchStrictBeforeExecution:
    def test_strict_rejects_unknown_param_before_execution(
        self,
        runner: CliRunner,
        cli_deps_with_processor,
        fake_processor,
        config_file: Path,
        effects_file: Path,
        input_file: Path,
    ) -> None:
        result = runner.invoke(
            app,
            [
                "batch",
                "--config",
                str(config_file),
                "--effects",
                str(effects_file),
                "effects",
                str(input_file),
                "--strict",
                "--param",
                "typo=1",
            ],
        )
        assert result.exit_code != 0
        assert fake_processor.calls == []


class TestHappyPathRegression:
    def test_known_override_reaches_processor(
        self,
        runner: CliRunner,
        cli_deps_with_processor,
        fake_processor,
        config_file: Path,
        effects_file: Path,
        input_file: Path,
    ) -> None:
        result = runner.invoke(
            app,
            [
                "process",
                "--config",
                str(config_file),
                "--effects",
                str(effects_file),
                "effect",
                "blur",
                str(input_file),
                "--param",
                "blur=5x3",
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
        assert fake_processor.calls
        assert fake_processor.calls[0]["params"]["blur"] == "5x3"
