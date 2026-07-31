from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from wallpaper_effects_generator.cli.main import app

runner = CliRunner()


def _parse_ndjson(output: str) -> list[dict]:
    import json

    objects: list[dict] = []
    depth = 0
    start = 0
    for i, ch in enumerate(output):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                objects.append(json.loads(output[start : i + 1]))
    return objects


def test_info_command(tmp_path: Path):
    config_file = tmp_path / "settings.toml"
    config_file.write_text("""
version = "1.0"
[execution]
[output]
[runtime]
mode = "container"
[container]
""")

    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text("""
version: "1.0"
effects:
  - name: blur
    description: "Gaussian blur"
    command: "convert {input} -blur {radius}x{sigma} {output}"
    parameters:
      radius:
        type: integer
        description: "Blur radius"
      sigma:
        type: float
        description: "Blur sigma"
""")

    result = runner.invoke(
        app,
        ["info", "--config", str(config_file), "--effects", str(effects_file)],
    )

    assert result.exit_code == 0, f"exit_code={result.exit_code}, stderr={result.stderr_bytes}"
    import json

    data = json.loads(result.stdout)
    assert data["version"] == "1.0"
    assert data["catalog"]["effects_count"] == 1
    assert data["settings"]["runtime"]["mode"] == "container"


def test_dump_config_command():
    result = runner.invoke(
        app,
        ["dump-config"],
    )

    assert result.exit_code == 0, f"exit_code={result.exit_code}, stderr={result.stderr_bytes}"
    assert 'version = "1.0"' in result.stdout
    assert "[execution]" in result.stdout
    assert "parallel = true" in result.stdout
    assert 'mode = "local"' in result.stdout
    assert 'engine = "docker"' in result.stdout


def test_dump_effects_command():
    result = runner.invoke(
        app,
        ["dump-effects"],
    )

    assert result.exit_code == 0, f"exit_code={result.exit_code}, stderr={result.stderr_bytes}"
    assert "blur" in result.stdout
    assert "brightness" in result.stdout
    assert "contrast" in result.stdout
    assert "saturation" in result.stdout
    assert "sepia" in result.stdout
    assert "vignette" in result.stdout
    assert "color_overlay" in result.stdout
    assert "negate" in result.stdout
    assert "blackwhite" in result.stdout


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Wallpaper Effects Generator" in result.stdout
    assert "info" in result.stdout
    assert "dump-config" in result.stdout
    assert "dump-effects" in result.stdout


def test_cli_callback_flags(tmp_path: Path):
    config_file = tmp_path / "settings.toml"
    config_file.write_text('version = "1.0"\n')

    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text('version: "1.0"\n')

    result = runner.invoke(
        app,
        [
            "--output-format",
            "json",
            "info",
            "--config",
            str(config_file),
            "--effects",
            str(effects_file),
        ],
    )

    assert result.exit_code == 0

    # verify --runtime at root is now rejected
    result = runner.invoke(
        app,
        [
            "--config",
            str(config_file),
            "--runtime",
            "container",
            "info",
        ],
    )
    assert result.exit_code != 0


def test_show_effects_command(tmp_path: Path):
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text("""
version: "1.0"
effects:
  - name: blur
    description: "Gaussian blur"
    command: "convert {input} -blur {radius}x{sigma} {output}"
    parameters:
      radius:
        type: integer
        description: "Blur radius"
      sigma:
        type: float
        description: "Blur sigma"
""")

    result = runner.invoke(
        app,
        ["show", "--effects", str(effects_file), "effects"],
    )

    assert result.exit_code == 0, f"exit_code={result.exit_code}, stderr={result.stderr_bytes}"
    import json

    data = json.loads(result.stdout)
    assert data["count"] == 1
    assert data["items"][0]["name"] == "blur"


def test_show_composites_command(tmp_path: Path):
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text("""
version: "1.0"
composites:
  - name: blur-resize
    description: "Blur then resize"
""")

    result = runner.invoke(
        app,
        ["show", "--effects", str(effects_file), "composites"],
    )

    assert result.exit_code == 0, f"exit_code={result.exit_code}, stderr={result.stderr_bytes}"
    import json

    data = json.loads(result.stdout)
    assert data["count"] == 1
    assert data["items"][0]["name"] == "blur-resize"


def test_show_presets_command(tmp_path: Path):
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text("""
version: "1.0"
presets:
  - name: social
    description: "Social media preset"
""")

    result = runner.invoke(
        app,
        ["show", "--effects", str(effects_file), "presets"],
    )

    assert result.exit_code == 0, f"exit_code={result.exit_code}, stderr={result.stderr_bytes}"
    import json

    data = json.loads(result.stdout)
    assert data["count"] == 1
    assert data["items"][0]["name"] == "social"


def test_show_all_command(tmp_path: Path):
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text("""
version: "1.0"
effects:
  - name: blur
    description: "Gaussian blur"
    command: "convert {input} -blur {radius}x{sigma} {output}"
composites:
  - name: blur-resize
    description: "Blur then resize"
presets:
  - name: social
    description: "Social media preset"
""")

    result = runner.invoke(
        app,
        ["show", "--effects", str(effects_file), "all"],
    )

    assert result.exit_code == 0, f"exit_code={result.exit_code}, stderr={result.stderr_bytes}"
    import json

    data = json.loads(result.stdout)
    assert "effects" in data
    assert "composites" in data
    assert "presets" in data
    assert len(data["effects"]) == 1
    assert data["effects"][0]["name"] == "blur"


def test_show_command_json_output(tmp_path: Path):
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text("""
version: "1.0"
effects:
  - name: blur
    description: "Gaussian blur"
    command: "convert {input} -blur {radius}x{sigma} {output}"
""")

    result = runner.invoke(
        app,
        [
            "--output-format",
            "json",
            "show",
            "--effects",
            str(effects_file),
            "effects",
        ],
    )

    assert result.exit_code == 0, f"exit_code={result.exit_code}, stderr={result.stderr_bytes}"
    import json

    data = json.loads(result.stdout)
    assert data["count"] == 1


def test_version_command():
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "wallpaper-effects-generator" in result.stdout


def test_operational_no_processing_dependency(tmp_path: Path):
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text('version: "1.0"\n')
    config_file = tmp_path / "settings.toml"
    config_file.write_text('version = "1.0"\n')

    result = runner.invoke(
        app,
        ["info", "--config", str(config_file), "--effects", str(effects_file)],
    )
    assert result.exit_code == 0


def test_install_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_file = tmp_path / "settings.toml"
    config_file.write_text("""
version = "1.0"
[runtime]
mode = "container"
[container]
engine = "docker"
image_tag = "latest"
image_registry = "ghcr.io"
""")

    from tests.conftest import FakeEngine

    fake_engine = FakeEngine()
    monkeypatch.setattr(
        "wallpaper_effects_generator.cli.install.create_container_engine",
        lambda settings: fake_engine,
    )
    result = runner.invoke(
        app,
        ["install", "--config", str(config_file)],
    )

    assert result.exit_code == 0, f"exit_code={result.exit_code}, stderr={result.stderr}"
    objects = _parse_ndjson(result.stdout)
    data = objects[-1]
    assert "installed" in data["message"]


def test_install_command_runtime_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_file = tmp_path / "settings.toml"
    config_file.write_text("""
version = "1.0"
[runtime]
mode = "container"
[container]
engine = "docker"
image_tag = "latest"
image_registry = "ghcr.io"
""")

    from tests.conftest import FakeEngine

    fake_engine = FakeEngine(available=False)
    monkeypatch.setattr(
        "wallpaper_effects_generator.cli.install.create_container_engine",
        lambda settings: fake_engine,
    )
    result = runner.invoke(
        app,
        ["install", "--config", str(config_file)],
    )

    assert result.exit_code != 0


def test_uninstall_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_file = tmp_path / "settings.toml"
    config_file.write_text("""
version = "1.0"
[runtime]
mode = "container"
[container]
engine = "docker"
image_tag = "latest"
image_registry = "ghcr.io"
""")

    from tests.conftest import FakeEngine

    fake_engine = FakeEngine(image_exists=True)
    monkeypatch.setattr(
        "wallpaper_effects_generator.cli.uninstall.create_container_engine",
        lambda settings: fake_engine,
    )
    result = runner.invoke(
        app,
        ["uninstall", "--config", str(config_file)],
    )

    assert result.exit_code == 0, f"exit_code={result.exit_code}, stderr={result.stderr}"
    import json

    data = json.loads(result.stdout)
    assert "removed" in data["message"]


def test_uninstall_command_no_image(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_file = tmp_path / "settings.toml"
    config_file.write_text("""
version = "1.0"
[runtime]
mode = "container"
[container]
engine = "docker"
image_tag = "latest"
image_registry = "ghcr.io"
""")

    from tests.conftest import FakeEngine

    fake_engine = FakeEngine(image_exists=False)
    monkeypatch.setattr(
        "wallpaper_effects_generator.cli.uninstall.create_container_engine",
        lambda settings: fake_engine,
    )
    result = runner.invoke(
        app,
        ["uninstall", "--config", str(config_file)],
    )

    assert result.exit_code == 0, f"exit_code={result.exit_code}, stderr={result.stderr}"
    import json

    data = json.loads(result.stdout)
    assert "nothing to uninstall" in data["message"]


# 4.5 dump-config --output and dump-effects --output file-write tests
def test_dump_config_output_file(tmp_path: Path):
    output_path = tmp_path / "cfg.toml"
    result = runner.invoke(app, ["dump-config", "--output", str(output_path)])
    assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
    assert output_path.exists()
    content = output_path.read_text()
    assert 'version = "1.0"' in content


def test_dump_effects_output_file(tmp_path: Path):
    output_path = tmp_path / "fx.yaml"
    result = runner.invoke(app, ["dump-effects", "--output", str(output_path)])
    assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
    assert output_path.exists()
    content = output_path.read_text()
    assert "blur" in content


# 4.6 Global flag tests
def test_output_format_rich(tmp_path: Path):
    config_file = tmp_path / "settings.toml"
    config_file.write_text('version = "1.0"\n[execution]\n[output]\n[runtime]\n[container]\n')
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text('version: "1.0"\neffects: []\n')
    result = runner.invoke(
        app,
        [
            "--output-format",
            "rich",
            "info",
            "--config",
            str(config_file),
            "--effects",
            str(effects_file),
        ],
    )
    assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
    assert "Configuration Info" in result.stdout


def test_output_format_plain(tmp_path: Path):
    config_file = tmp_path / "settings.toml"
    config_file.write_text('version = "1.0"\n[execution]\n[output]\n[runtime]\n[container]\n')
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text('version: "1.0"\neffects: []\n')
    result = runner.invoke(
        app,
        [
            "--output-format",
            "plain",
            "info",
            "--config",
            str(config_file),
            "--effects",
            str(effects_file),
        ],
    )
    assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
    assert "\x1b[" not in result.stdout


def test_quiet_flag(tmp_path: Path):
    config_file = tmp_path / "settings.toml"
    config_file.write_text('version = "1.0"\n[execution]\n[output]\n[runtime]\n[container]\n')
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text('version: "1.0"\neffects: []\n')
    result = runner.invoke(
        app,
        [
            "--quiet",
            "info",
            "--config",
            str(config_file),
            "--effects",
            str(effects_file),
        ],
    )
    assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"


def test_verbose_flag(tmp_path: Path):
    config_file = tmp_path / "settings.toml"
    config_file.write_text(
        'version = "1.0"\n[execution]\n[output]\n[runtime]\n[container]\nengine = "docker"\n'
    )
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text('version: "1.0"\neffects: []\n')
    result = runner.invoke(
        app,
        [
            "-v",
            "info",
            "--config",
            str(config_file),
            "--effects",
            str(effects_file),
        ],
    )
    assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"


# 4.7 Error-path tests
def test_missing_input_file_error(tmp_path: Path):
    config_file = tmp_path / "settings.toml"
    config_file.write_text(
        'version = "1.0"\n[execution]\n[output]\n[runtime]\nmode = "local"\n[container]\n'
    )
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text('version: "1.0"\neffects: []\n')
    result = runner.invoke(
        app,
        [
            "--output-format",
            "json",
            "process",
            "--config",
            str(config_file),
            "--effects",
            str(effects_file),
            "effect",
            "blur",
            str(tmp_path / "nonexistent.png"),
            "--dry-run",
        ],
    )
    assert result.exit_code != 0


def test_missing_config_file_error(tmp_path: Path):
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text('version: "1.0"\neffects: []\n')
    result = runner.invoke(
        app,
        [
            "info",
            "--config",
            str(tmp_path / "nonexistent.toml"),
            "--effects",
            str(effects_file),
        ],
    )
    assert result.exit_code != 0


def test_invalid_container_engine(tmp_path: Path):
    config_file = tmp_path / "settings.toml"
    config_file.write_text(
        'version = "1.0"\n[execution]\n[output]\n[runtime]\nmode = "container"\n[container]\nengine = "docker"\n'
    )
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text('version: "1.0"\neffects: []\n')
    result = runner.invoke(
        app,
        [
            "process",
            "--config",
            str(config_file),
            "--effects",
            str(effects_file),
            "--container-engine",
            "invalid",
            "effect",
            "blur",
            str(tmp_path / "input.png"),
        ],
    )
    assert result.exit_code != 0


# 4.8 Show exception-path test
def test_show_invalid_effects_file(tmp_path: Path):
    effects_file = tmp_path / "invalid.yaml"
    effects_file.write_text("not: valid: yaml: [[[")
    result = runner.invoke(app, ["show", "--effects", str(effects_file), "effects"])
    assert result.exit_code != 0


# 4.9 Replace test.sh characterization with batch all --dry-run test
def test_batch_all_dry_run_characterization(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_file = tmp_path / "settings.toml"
    config_file.write_text(
        'version = "1.0"\n[execution]\n[output]\n[runtime]\nmode = "local"\n[container]\nengine = "docker"\n'
    )
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text("""version: '1.0'
effects:
  - name: blur
    description: Blur
    command: magick {{input}} -blur {{radius}} {{output}}
    parameters:
      radius:
        type: string
        default: "0x8"
  - name: resize
    description: Resize
    command: magick {{input}} -resize {{size}} {{output}}
    parameters:
      size:
        type: string
        default: "50%"
  - name: contrast
    description: Contrast
    command: magick {{input}} -contrast {{output}}
composites:
  - name: blur-resize
    description: Blur then resize
    steps:
      - effect_name: blur
        parameters:
          radius: "0x4"
presets:
  - name: social
    description: Social
    effects:
      - resize
""")
    input_file = tmp_path / "input.png"
    input_file.write_text("dummy")
    from tests.conftest import FakeProcessor
    from wallpaper_effects_generator.factory import CliDependencies

    fp = FakeProcessor()
    deps = CliDependencies(processor=fp)
    monkeypatch.setattr("wallpaper_effects_generator.cli.main.build_deps", lambda: deps)
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
            str(tmp_path / "output"),
        ],
    )
    assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
    import json

    data = json.loads(result.stdout)
    assert data["total"] > 0
    assert data["succeeded"] == data["total"]


# 8.1 xfail: process.py _parse_params silently drops malformed --param (should reject)
@pytest.mark.xfail(
    reason="process.py _parse_params silently drops no-equals params instead of rejecting them"
)
def test_process_malformed_param_silent_drop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_file = tmp_path / "settings.toml"
    config_file.write_text(
        'version = "1.0"\n[execution]\n[output]\n[runtime]\nmode = "local"\n[container]\n'
    )
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text(
        'version: "1.0"\neffects:\n  - name: blur\n    description: Blur\n    command: "magick"\n'
    )
    input_file = tmp_path / "input.png"
    input_file.write_text("dummy")
    from tests.conftest import FakeProcessor
    from wallpaper_effects_generator.factory import CliDependencies

    fp = FakeProcessor()
    deps = CliDependencies(processor=fp)
    monkeypatch.setattr("wallpaper_effects_generator.cli.main.build_deps", lambda: deps)
    result = runner.invoke(
        app,
        [
            "--output-format",
            "json",
            "process",
            "--config",
            str(config_file),
            "--effects",
            str(effects_file),
            "effect",
            "blur",
            str(input_file),
            "--param",
            "badparam",
        ],
    )
    # Desired: malformed param should be rejected
    assert result.exit_code != 0


# 8.2 batch.py _parse_params raises on malformed (different from process.py)
def test_batch_malformed_param_raises(tmp_path: Path):
    config_file = tmp_path / "settings.toml"
    config_file.write_text(
        'version = "1.0"\n[execution]\n[output]\n[runtime]\nmode = "local"\n[container]\n'
    )
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text(
        'version: "1.0"\neffects:\n  - name: blur\n    description: Blur\n    command: "magick"\n'
    )
    input_file = tmp_path / "input.png"
    input_file.write_text("dummy")
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
            "badparam",
        ],
    )
    # Current behavior: raises BadParameter for no-equals in batch.py
    assert result.exit_code != 0


# 8.3 explicit_output=True without -o is treated as False
def test_explicit_output_without_output_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_file = tmp_path / "settings.toml"
    config_file.write_text(
        'version = "1.0"\n[execution]\n[output]\n[runtime]\nmode = "local"\n[container]\n'
    )
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text(
        'version: "1.0"\neffects:\n  - name: blur\n    description: Blur\n    command: "magick"\n'
    )
    input_file = tmp_path / "input.png"
    input_file.write_text("dummy")
    from tests.conftest import FakeProcessor
    from wallpaper_effects_generator.factory import CliDependencies

    fp = FakeProcessor()
    deps = CliDependencies(processor=fp)
    monkeypatch.setattr("wallpaper_effects_generator.cli.main.build_deps", lambda: deps)
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
            "--explicit-output",
        ],
    )
    assert result.exit_code == 0, (
        f"exit_code: {result.exit_code}\n"
        f"stderr: {result.stderr}"
    )


# 8.4 info command respects cli_overrides
def test_info_respects_runtime_override(tmp_path: Path):
    config_file = tmp_path / "settings.toml"
    config_file.write_text(
        'version = "1.0"\n[execution]\n[output]\n[runtime]\nmode = "local"\n[container]\nengine = "docker"\n'
    )
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text('version: "1.0"\neffects: []\n')
    result = runner.invoke(
        app,
        [
            "info",
            "--config",
            str(config_file),
            "--effects",
            str(effects_file),
        ],
    )
    assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
    import json

    data = json.loads(result.stdout)
    # Without --runtime container, runtime.mode should be "local" (from config)
    assert data["settings"]["runtime"]["mode"] == "local"
