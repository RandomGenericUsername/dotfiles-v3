from __future__ import annotations

from pathlib import Path

import pytest

from icon_templates_renderer.adapters.file_color_scheme_loader import FileColorSchemeLoader
from icon_templates_renderer.domain.exceptions import ColorSchemeNotFoundError


class TestFileColorSchemeLoader:
    def setup_method(self) -> None:
        self.loader = FileColorSchemeLoader()

    def test_yaml_list_becomes_color_n(self, tmp_path: Path) -> None:
        path = tmp_path / "colors.yaml"
        path.write_text(
            "special:\n"
            '  background: "#1a1a2e"\n'
            '  foreground: "#e0e0e0"\n'
            "colors:\n"
            '  - "#1a1a2e"\n'
            '  - "#e94560"\n'
        )
        scheme = self.loader.load(path)
        assert scheme.get("background") == "#1a1a2e"
        assert scheme.get("foreground") == "#e0e0e0"
        assert scheme.get("color0") == "#1a1a2e"
        assert scheme.get("color1") == "#e94560"

    def test_json_dict_preserves_keys(self, tmp_path: Path) -> None:
        path = tmp_path / "colors.json"
        path.write_text(
            "{\n"
            '  "special": {"background": "#aabbcc"},\n'
            '  "colors": {"color5": "#112233", "color0": "#aabbcc"}\n'
            "}\n"
        )
        scheme = self.loader.load(path)
        assert scheme.get("background") == "#aabbcc"
        assert scheme.get("color5") == "#112233"
        assert scheme.get("color0") == "#aabbcc"

    def test_json_csg_top_level_layout(self, tmp_path: Path) -> None:
        """CSG export layout: top-level background/foreground/cursor + colors list."""
        path = tmp_path / "colors.json"
        path.write_text(
            "{\n"
            '  "background": "#191533",\n'
            '  "foreground": "#c5c4cc",\n'
            '  "cursor": "#c5c4cc",\n'
            '  "colors": ["#191533", "#361190", "#c034d8", "#c5c4cc"],\n'
            '  "backend": "pywal"\n'
            "}\n"
        )
        scheme = self.loader.load(path)
        assert scheme.get("background") == "#191533"
        assert scheme.get("foreground") == "#c5c4cc"
        assert scheme.get("color0") == "#191533"
        assert scheme.get("color1") == "#361190"
        assert scheme.get("color2") == "#c034d8"
        assert scheme.get("color3") == "#c5c4cc"

    def test_yaml_csg_top_level_layout(self, tmp_path: Path) -> None:
        """CSG export YAML layout: top-level specials + colors list."""
        path = tmp_path / "colors.yaml"
        path.write_text(
            'background: "#191533"\n'
            'foreground: "#c5c4cc"\n'
            'cursor: "#c5c4cc"\n'
            "colors:\n"
            '  - "#191533"\n'
            '  - "#361190"\n'
        )
        scheme = self.loader.load(path)
        assert scheme.get("background") == "#191533"
        assert scheme.get("color0") == "#191533"
        assert scheme.get("color1") == "#361190"

    def test_semantic_keys_preserved(self, tmp_path: Path) -> None:
        """Semantic scheme carries surface/accent/accent-muted tokens."""
        path = tmp_path / "semantic.yaml"
        path.write_text(
            'foreground: "#c5c4cc"\n'
            'surface: "#191533"\n'
            'accent: "#c034d8"\n'
            'accent-muted: "#681e99"\n'
        )
        scheme = self.loader.load(path)
        assert scheme.get("surface") == "#191533"
        assert scheme.get("accent") == "#c034d8"
        assert scheme.get("accent-muted") == "#681e99"
        assert scheme.get("foreground") == "#c5c4cc"

    def test_unsupported_suffix_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "colors.txt"
        path.write_text("x")
        with pytest.raises(ColorSchemeNotFoundError) as excinfo:
            self.loader.load(path)
        assert "Unsupported color scheme format: .txt. Use .yaml or .json" in str(excinfo.value)

    def test_missing_file_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "nope.yaml"
        with pytest.raises(ColorSchemeNotFoundError) as excinfo:
            self.loader.load(path)
        assert f"Color scheme file not found: {path}" in str(excinfo.value)

    def test_supports(self) -> None:
        assert self.loader.supports(Path("colors.yaml"))
        assert self.loader.supports(Path("colors.yml"))
        assert self.loader.supports(Path("colors.json"))
        assert not self.loader.supports(Path("colors.txt"))
