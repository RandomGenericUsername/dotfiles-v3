from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from color_scheme_generator.adapters.template_dir_resolver import TemplateDirResolver
from color_scheme_generator.ports.template_dir_resolver import TemplateDirResolverPort


class TestTemplateDirResolver:
    def test_resolve_uses_env_var_first(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "custom-templates"
        templates_dir.mkdir(parents=True)

        with patch.dict(os.environ, {"COLORSCHEME_TEMPLATES_TEMPLATES_DIR": str(templates_dir)}):
            resolver = TemplateDirResolver()
            result = resolver.resolve()

        assert result == templates_dir.resolve()

    def test_resolve_falls_back_to_xdg(self, tmp_path: Path) -> None:
        xdg_config = tmp_path / "xdg-config"
        templates_dir = xdg_config / "color-scheme-generator" / "templates"
        templates_dir.mkdir(parents=True)

        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(xdg_config)}):
            resolver = TemplateDirResolver()
            result = resolver.resolve()

        assert result == templates_dir.resolve()

    def test_resolve_falls_back_to_package_defaults(self) -> None:
        resolver = TemplateDirResolver()
        result = resolver.resolve()

        expected = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "src"
            / "color_scheme_generator"
            / "defaults"
            / "templates"
        )
        assert result == expected.resolve()

    def test_structural_subtyping(self) -> None:
        resolver = TemplateDirResolver()
        assert isinstance(resolver, TemplateDirResolverPort)
