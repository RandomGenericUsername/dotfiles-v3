from __future__ import annotations

from pathlib import Path

from icon_templates_renderer.adapters.color_scheme_resolver import ColorSchemeResolver
from icon_templates_renderer.adapters.template_dir_resolver import TemplateDirResolver


class TestTemplateDirResolver:
    def test_returns_none_when_nothing_found(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        assert TemplateDirResolver().resolve() is None

    def test_finds_traversed_templates_dir(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / "templates").mkdir()
        nested = tmp_path / "sub" / "nested"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        result = TemplateDirResolver().resolve()
        assert result is not None
        assert result.name == "templates"
        assert result == (tmp_path / "templates").resolve()

    def test_finds_xdg_templates_dir(self, tmp_path: Path, monkeypatch) -> None:
        xdg = tmp_path / ".config"
        (xdg / "itr" / "templates").mkdir(parents=True)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        monkeypatch.chdir(tmp_path)
        result = TemplateDirResolver().resolve()
        assert result is not None
        assert result == (xdg / "itr" / "templates").resolve()


class TestColorSchemeResolver:
    def test_returns_none_when_nothing_found(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        assert ColorSchemeResolver().resolve() is None

    def test_finds_traversed_colors_yaml(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / "colors.yaml").write_text("colors: []\n")
        nested = tmp_path / "sub" / "nested"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        result = ColorSchemeResolver().resolve()
        assert result is not None
        assert result == (tmp_path / "colors.yaml").resolve()

    def test_finds_xdg_colors_yaml(self, tmp_path: Path, monkeypatch) -> None:
        xdg = tmp_path / ".config"
        (xdg / "itr").mkdir(parents=True)
        (xdg / "itr" / "colors.yaml").write_text("colors: []\n")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        monkeypatch.chdir(tmp_path)
        result = ColorSchemeResolver().resolve()
        assert result is not None
        assert result == (xdg / "itr" / "colors.yaml").resolve()
