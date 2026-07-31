from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from wallpaper_effects_generator.cli.main import app


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "settings.toml"
    path.write_text(
        'version = "1.0"\n[execution]\n[output]\n[runtime]\nmode = "local"\n[container]\nengine = "docker"\n'
    )
    return path


@pytest.fixture
def effects_file(tmp_path: Path) -> Path:
    path = tmp_path / "effects.yaml"
    path.write_text("""version: '1.0'
effects:
  - name: blur
    description: Blur effect
    command: magick {{input}} -blur {{radius}} {{output}}
    parameters:
      radius:
        type: string
        default: "0x8"
  - name: resize
    description: Resize effect
    command: magick {{input}} -resize {{size}} {{output}}
    parameters:
      size:
        type: string
        default: "50%"
composites:
  - name: blur-resize
    description: Blur then resize
    steps:
      - effect_name: blur
        parameters:
          radius: "0x4"
presets:
  - name: social
    description: Social media preset
    effects:
      - resize
""")
    return path


@pytest.fixture
def input_file(tmp_path: Path) -> Path:
    path = tmp_path / "input.png"
    path.write_text("dummy")
    return path


class TestBatchEffectsCommand:
    def test_batch_effects_basic(
        self,
        runner: CliRunner,
        cli_deps_with_processor,
        fake_processor,
        config_file: Path,
        effects_file: Path,
        input_file: Path,
        tmp_path: Path,
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
                "-o",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
        assert len(fake_processor.calls) == 2
        assert fake_processor.calls[0]["command"] == "process_effect"


class TestBatchCompositesCommand:
    def test_batch_composites_basic(
        self,
        runner: CliRunner,
        cli_deps_with_processor,
        fake_processor,
        config_file: Path,
        effects_file: Path,
        input_file: Path,
        tmp_path: Path,
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
                "-o",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
        assert len(fake_processor.calls) == 1
        assert fake_processor.calls[0]["command"] == "process_composite"


class TestBatchPresetsCommand:
    def test_batch_presets_basic(
        self,
        runner: CliRunner,
        cli_deps_with_processor,
        fake_processor,
        config_file: Path,
        effects_file: Path,
        input_file: Path,
        tmp_path: Path,
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
                "-o",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
        assert len(fake_processor.calls) == 1
        assert fake_processor.calls[0]["command"] == "process_preset"


class TestBatchAllCommand:
    def test_batch_all_basic(
        self,
        runner: CliRunner,
        cli_deps_with_processor,
        fake_processor,
        config_file: Path,
        effects_file: Path,
        input_file: Path,
        tmp_path: Path,
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
                "-o",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
        assert len(fake_processor.calls) == 4
        import json

        data = json.loads(result.stdout)
        assert "total" in data
