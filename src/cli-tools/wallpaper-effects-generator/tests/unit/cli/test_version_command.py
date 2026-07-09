from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from wallpaper_effects_generator.cli.main import app

runner = CliRunner()


class TestVersionCommand:
    def test_version_with_package(self) -> None:
        mock_provider = MagicMock()
        mock_provider.get_version.return_value = "1.2.3"

        with patch(
            "wallpaper_effects_generator.cli.main.create_version_provider",
            return_value=mock_provider,
        ):
            result = runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert "wallpaper-effects-generator 1.2.3" in result.stdout

    def test_version_without_package_fallback(self) -> None:
        mock_provider = MagicMock()
        mock_provider.get_version.return_value = "0.1.0"

        with patch(
            "wallpaper_effects_generator.cli.main.create_version_provider",
            return_value=mock_provider,
        ):
            result = runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert "wallpaper-effects-generator 0.1.0" in result.stdout
