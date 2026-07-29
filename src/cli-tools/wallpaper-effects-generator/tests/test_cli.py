from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

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
            "--output-format", "json",
            "show", "--effects", str(effects_file), "effects",
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


def test_install_command(tmp_path: Path):
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

    mock_result = subprocess.CompletedProcess(
        args=["docker", "pull", "ghcr.io/weg-managed-docker:latest"],
        returncode=0,
        stdout="",
        stderr="",
    )

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", return_value=mock_result),
    ):
        result = runner.invoke(
            app,
            ["install", "--config", str(config_file)],
        )

    assert result.exit_code == 0, f"exit_code={result.exit_code}, stderr={result.stderr}"
    import json
    objects = _parse_ndjson(result.stdout)
    data = objects[-1]
    assert "installed" in data["message"]


def test_install_command_runtime_unavailable(tmp_path: Path):
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

    with patch("shutil.which", return_value=None):
        result = runner.invoke(
            app,
            ["install", "--config", str(config_file)],
        )

    assert result.exit_code != 0


def test_uninstall_command(tmp_path: Path):
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

    mock_result = subprocess.CompletedProcess(
        args=["docker", "rmi", "ghcr.io/weg-managed-docker:latest"],
        returncode=0,
        stdout="Untagged: ghcr.io/weg-managed-docker:latest\n",
        stderr="",
    )

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", return_value=mock_result),
    ):
        result = runner.invoke(
            app,
            ["uninstall", "--config", str(config_file)],
        )

    assert result.exit_code == 0, f"exit_code={result.exit_code}, stderr={result.stderr}"
    import json
    data = json.loads(result.stdout)
    assert "removed" in data["message"]


def test_uninstall_command_no_image(tmp_path: Path):
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

    mock_result = subprocess.CompletedProcess(
        args=["docker", "rmi", "ghcr.io/weg-managed-docker:latest"],
        returncode=1,
        stdout="",
        stderr="No such image: ghcr.io/weg-managed-docker:latest",
    )

    with (
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run", return_value=mock_result),
    ):
        result = runner.invoke(
            app,
            ["uninstall", "--config", str(config_file)],
        )

    assert result.exit_code == 0, f"exit_code={result.exit_code}, stderr={result.stderr}"
    import json
    data = json.loads(result.stdout)
    assert "nothing to uninstall" in data["message"]
