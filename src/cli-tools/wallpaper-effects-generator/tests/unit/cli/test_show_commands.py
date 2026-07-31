from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from wallpaper_effects_generator.cli.main import app


@pytest.fixture
def effects_file(tmp_path: Path) -> Path:
    path = tmp_path / "effects.yaml"
    path.write_text("""version: '1.0'
effects:
  - name: blur
    description: Gaussian blur
    command: magick {{input}} -blur {{radius}} {{output}}
    parameters:
      radius:
        type: string
        default: "0x8"
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
      - blur
""")
    return path


class TestShowCommand:
    def test_show_effects(self, runner: CliRunner, effects_file: Path) -> None:
        result = runner.invoke(app, ["show", "--effects", str(effects_file), "effects"])
        assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
        import json

        data = json.loads(result.stdout)
        assert data["count"] == 1
        assert data["items"][0]["name"] == "blur"

    def test_show_composites(self, runner: CliRunner, effects_file: Path) -> None:
        result = runner.invoke(app, ["show", "--effects", str(effects_file), "composites"])
        assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
        import json

        data = json.loads(result.stdout)
        assert data["count"] == 1
        assert data["items"][0]["name"] == "blur-resize"

    def test_show_presets(self, runner: CliRunner, effects_file: Path) -> None:
        result = runner.invoke(app, ["show", "--effects", str(effects_file), "presets"])
        assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
        import json

        data = json.loads(result.stdout)
        assert data["count"] == 1
        assert data["items"][0]["name"] == "social"

    def test_show_all(self, runner: CliRunner, effects_file: Path) -> None:
        result = runner.invoke(app, ["show", "--effects", str(effects_file), "all"])
        assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
        import json

        data = json.loads(result.stdout)
        assert "effects" in data
        assert "composites" in data
        assert "presets" in data

    def test_show_rejects_config_flag(self, runner: CliRunner, effects_file: Path) -> None:
        result = runner.invoke(
            app, ["show", "--effects", str(effects_file), "effects", "--config", "/x"]
        )
        assert result.exit_code != 0
        assert "no such option" in (result.stdout + result.stderr).lower()
