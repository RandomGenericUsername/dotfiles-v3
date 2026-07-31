from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from color_scheme_generator.adapters.template_catalog_loader import DirectoryTemplateCatalogLoader
from color_scheme_generator.domain.enums import ColorFormat


def test_load_with_explicit_dir(tmp_path: Path) -> None:
    (tmp_path / "colors.json.j2").write_text("x")
    (tmp_path / "colors.sh.j2").write_text("x")

    resolver = MagicMock()
    loader = DirectoryTemplateCatalogLoader(resolver)
    catalog = loader.load(explicit_dir=tmp_path)

    assert len(catalog.templates) == 2
    assert catalog.templates[0].format == ColorFormat.JSON
    assert catalog.templates[1].format == ColorFormat.SH
    assert catalog.source_dir == tmp_path
    assert loader.get_resolved_path() == tmp_path


def test_load_without_explicit_dir_uses_resolver(tmp_path: Path) -> None:
    (tmp_path / "colors.json.j2").write_text("x")

    resolver = MagicMock()
    resolver.resolve.return_value = tmp_path

    loader = DirectoryTemplateCatalogLoader(resolver)
    catalog = loader.load()

    assert len(catalog.templates) == 1
    assert catalog.templates[0].format == ColorFormat.JSON
    resolver.resolve.assert_called_once()
    assert loader.get_resolved_path() == tmp_path


def test_load_from_cache_returns_cached(tmp_path: Path) -> None:
    (tmp_path / "colors.json.j2").write_text("x")

    resolver = MagicMock()
    resolver.resolve.return_value = tmp_path

    loader = DirectoryTemplateCatalogLoader(resolver)
    catalog1 = loader.load(explicit_dir=tmp_path)
    catalog2 = loader.load(explicit_dir=tmp_path)

    assert catalog1 is catalog2
    # resolve called only once even though we created .sh.j2 after first load
    (tmp_path / "colors.sh.j2").write_text("x")
    catalog3 = loader.load(explicit_dir=tmp_path)
    # different key = re-scan (catalog1 was cached at explicit=tmp_path; same key)
    assert catalog3 is catalog1, "same key should return cached"
    assert len(catalog3.templates) == 1, "cached, not re-scanned"

    # fresh key re-scans
    (tmp_path / "colors.css.j2").write_text("x")
    # with no explicit_dir the key is "__resolved__"
    catalog4 = loader.load()
    assert catalog4 is not catalog1
    assert len(catalog4.templates) == 3


def test_get_resolved_path_before_load_is_none() -> None:
    resolver = MagicMock()
    loader = DirectoryTemplateCatalogLoader(resolver)
    assert loader.get_resolved_path() is None
