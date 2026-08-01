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
    path.write_text(
        "version: '1.0'\n"
        "effects:\n"
        "  - name: blur\n"
        "    description: Blur\n"
        "    command: magick {{input}} -blur {{radius}} {{output}}\n"
        "    parameters:\n"
        "      radius:\n"
        "        type: string\n"
        "        default: 0x8\n"
        "      sigma:\n"
        "        type: string\n"
        "        default: 3.0\n"
    )
    return path


@pytest.fixture
def input_file(tmp_path: Path) -> Path:
    path = tmp_path / "input.png"
    path.write_text("dummy")
    return path


class TestProcessEffectCommand:
    def test_effect_dry_run(
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
                "process",
                "--config",
                str(config_file),
                "--effects",
                str(effects_file),
                "effect",
                "blur",
                str(input_file),
                "--dry-run",
                "-o",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
        assert len(fake_processor.calls) == 1
        assert fake_processor.calls[0]["command"] == "process_effect"
        assert fake_processor.calls[0]["name"] == "blur"

    def test_effect_with_param(
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
                "process",
                "--config",
                str(config_file),
                "--effects",
                str(effects_file),
                "effect",
                "blur",
                str(input_file),
                "--param",
                "radius=0x8",
                "-o",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
        assert len(fake_processor.calls) == 1
        params = fake_processor.calls[0]["params"]
        assert params == {"radius": "0x8"} or (
            params is None and fake_processor.calls[0]["request"].params == {"radius": "0x8"}
        )

    def test_effect_json_output(
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
                "-o",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
        import json

        data = json.loads(result.stdout)
        assert data["success"] is True

    def test_effect_multiple_params(
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
                "process",
                "--config",
                str(config_file),
                "--effects",
                str(effects_file),
                "effect",
                "blur",
                str(input_file),
                "--param",
                "radius=0x8",
                "--param",
                "sigma=3.0",
                "-o",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
        assert len(fake_processor.calls) == 1
        req = fake_processor.calls[0]["request"]
        assert req.params == {"radius": "0x8", "sigma": "3.0"}


class TestProcessCompositeCommand:
    def test_composite_dry_run(
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
                "process",
                "--config",
                str(config_file),
                "--effects",
                str(effects_file),
                "composite",
                "blur-resize",
                str(input_file),
                "--dry-run",
                "-o",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
        assert len(fake_processor.calls) == 1
        assert fake_processor.calls[0]["command"] == "process_composite"


class TestProcessPresetCommand:
    def test_preset_dry_run(
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
                "process",
                "--config",
                str(config_file),
                "--effects",
                str(effects_file),
                "preset",
                "social",
                str(input_file),
                "--dry-run",
                "-o",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
        assert len(fake_processor.calls) == 1
        assert fake_processor.calls[0]["command"] == "process_preset"


class TestCliDependencies:
    def test_build_deps_returns_proper_cli_dependencies(self) -> None:
        from wallpaper_effects_generator.cli.main import build_deps
        from wallpaper_effects_generator.factory import (
            AssembledConfigResolver,
            CliDependencies,
            YamlEffectLoader,
        )

        deps = build_deps()
        assert isinstance(deps, CliDependencies)
        assert isinstance(deps.config_resolver, AssembledConfigResolver)
        assert isinstance(deps.effect_loader, YamlEffectLoader)
        assert deps.processor is None
        assert deps.output_adapter is None

    def test_cli_main_has_no_legacy_test_seam(self) -> None:
        from wallpaper_effects_generator.cli import main as cli_main

        assert hasattr(cli_main, "build_deps")
        assert not hasattr(cli_main, "set_test_deps")
        assert not hasattr(cli_main, "_test_deps")
