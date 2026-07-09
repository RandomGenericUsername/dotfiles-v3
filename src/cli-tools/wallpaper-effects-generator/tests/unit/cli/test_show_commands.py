from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from wallpaper_effects_generator.cli.main import app
from wallpaper_effects_generator.domain.enums import CatalogQuery
from wallpaper_effects_generator.domain.models import EffectsCatalog

runner = CliRunner()


def _make_mock_catalog() -> EffectsCatalog:
    return EffectsCatalog()


class TestShowCommand:
    def test_show_effects(self) -> None:
        mock_adapter = MagicMock()
        with (
            patch(
                "wallpaper_effects_generator.cli.show._get_output_adapter",
                return_value=mock_adapter,
            ),
            patch(
                "wallpaper_effects_generator.adapters.catalog_cache.CatalogCache.get",
                return_value=_make_mock_catalog(),
            ),
        ):
            result = runner.invoke(app, ["show", "effects"])
            assert result.exit_code == 0
            mock_adapter.catalog_list.assert_called_once()
            args = mock_adapter.catalog_list.call_args[0]
            assert args[1] == CatalogQuery.EFFECT

    def test_show_composites(self) -> None:
        mock_adapter = MagicMock()
        with (
            patch(
                "wallpaper_effects_generator.cli.show._get_output_adapter",
                return_value=mock_adapter,
            ),
            patch(
                "wallpaper_effects_generator.adapters.catalog_cache.CatalogCache.get",
                return_value=_make_mock_catalog(),
            ),
        ):
            result = runner.invoke(app, ["show", "composites"])
            assert result.exit_code == 0
            mock_adapter.catalog_list.assert_called_once()
            args = mock_adapter.catalog_list.call_args[0]
            assert args[1] == CatalogQuery.COMPOSITE

    def test_show_presets(self) -> None:
        mock_adapter = MagicMock()
        with (
            patch(
                "wallpaper_effects_generator.cli.show._get_output_adapter",
                return_value=mock_adapter,
            ),
            patch(
                "wallpaper_effects_generator.adapters.catalog_cache.CatalogCache.get",
                return_value=_make_mock_catalog(),
            ),
        ):
            result = runner.invoke(app, ["show", "presets"])
            assert result.exit_code == 0
            mock_adapter.catalog_list.assert_called_once()
            args = mock_adapter.catalog_list.call_args[0]
            assert args[1] == CatalogQuery.PRESET

    def test_show_all(self) -> None:
        mock_adapter = MagicMock()
        with (
            patch(
                "wallpaper_effects_generator.cli.show._get_output_adapter",
                return_value=mock_adapter,
            ),
            patch(
                "wallpaper_effects_generator.adapters.catalog_cache.CatalogCache.get",
                return_value=_make_mock_catalog(),
            ),
        ):
            result = runner.invoke(app, ["show", "all"])
            assert result.exit_code == 0
            mock_adapter.catalog_list.assert_called_once()
            args = mock_adapter.catalog_list.call_args[0]
            assert args[1] == CatalogQuery.ALL
