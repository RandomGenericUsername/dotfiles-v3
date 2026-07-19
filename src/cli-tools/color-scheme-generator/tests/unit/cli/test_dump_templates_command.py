from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from color_scheme_generator.factory import CliDependencies


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_output() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_deps(mock_output: MagicMock) -> CliDependencies:
    return CliDependencies(
        backend_registry={},
        output_adapter=mock_output,
    )


class TestDumpTemplatesCommand:
    def test_dump_templates_copies_bundled_templates(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        output_dir = tmp_path / "templates"
        output_dir.mkdir(parents=True)

        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        templates_root = tmp_path / "defaults"
        mock_bundled = templates_root / "templates"
        mock_bundled.mkdir(parents=True)
        (mock_bundled / "colors.json.j2").write_text("test template")
        (mock_bundled / "colors.sh.j2").write_text("test template")

        with patch(
            "color_scheme_generator.cli.dump_templates_cmd.resource_files",
            return_value=templates_root,
        ):
            result = runner.invoke(
                app,
                ["dump-templates", "--output", str(output_dir)],
            )

        assert result.exit_code == 0
        assert (output_dir / "colors.json.j2").exists()
        assert (output_dir / "colors.sh.j2").exists()

    def test_dump_templates_creates_parent_directories(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        output_dir = tmp_path / "deep" / "nested" / "templates"

        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        templates_root = tmp_path / "defaults"
        mock_bundled = templates_root / "templates"
        mock_bundled.mkdir(parents=True)
        (mock_bundled / "colors.json.j2").write_text("test")

        with patch(
            "color_scheme_generator.cli.dump_templates_cmd.resource_files",
            return_value=templates_root,
        ):
            result = runner.invoke(
                app,
                ["dump-templates", "--output", str(output_dir)],
            )

        assert result.exit_code == 0
        assert (output_dir / "colors.json.j2").exists()

    def test_dump_templates_overwrite_replaces_existing(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        output_dir = tmp_path / "templates"
        output_dir.mkdir(parents=True)
        existing = output_dir / "colors.json.j2"
        existing.write_text("old content")

        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        templates_root = tmp_path / "defaults"
        mock_bundled = templates_root / "templates"
        mock_bundled.mkdir(parents=True)
        (mock_bundled / "colors.json.j2").write_text("new content")

        with patch(
            "color_scheme_generator.cli.dump_templates_cmd.resource_files",
            return_value=templates_root,
        ):
            result = runner.invoke(
                app,
                [
                    "dump-templates",
                    "--output",
                    str(output_dir),
                    "--overwrite",
                ],
            )

        assert result.exit_code == 0
        assert existing.read_text() == "new content"

    def test_dump_templates_without_overwrite_skips_existing(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        output_dir = tmp_path / "templates"
        output_dir.mkdir(parents=True)
        existing = output_dir / "colors.json.j2"
        existing.write_text("old content")

        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        templates_root = tmp_path / "defaults"
        mock_bundled = templates_root / "templates"
        mock_bundled.mkdir(parents=True)
        (mock_bundled / "colors.json.j2").write_text("new content")

        with patch(
            "color_scheme_generator.cli.dump_templates_cmd.resource_files",
            return_value=templates_root,
        ):
            result = runner.invoke(
                app,
                ["dump-templates", "--output", str(output_dir)],
            )

        assert result.exit_code == 0
        assert existing.read_text() == "old content"

    def test_dump_templates_uses_custom_output_path(
        self,
        runner: CliRunner,
        mock_deps: CliDependencies,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        custom_dir = tmp_path / "custom-templates"

        monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
        from color_scheme_generator.cli.main import app

        templates_root = tmp_path / "defaults"
        mock_bundled = templates_root / "templates"
        mock_bundled.mkdir(parents=True)
        (mock_bundled / "colors.json.j2").write_text("test")

        with patch(
            "color_scheme_generator.cli.dump_templates_cmd.resource_files",
            return_value=templates_root,
        ):
            result = runner.invoke(
                app,
                [
                    "dump-templates",
                    "--output",
                    str(custom_dir),
                ],
            )

        assert result.exit_code == 0
        assert (custom_dir / "colors.json.j2").exists()

    def test_dump_templates_help_shows_expected_usage(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from color_scheme_generator.cli.main import app

        result = runner.invoke(app, ["dump-templates", "--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.stdout
