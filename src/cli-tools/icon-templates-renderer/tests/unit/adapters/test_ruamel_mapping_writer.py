from __future__ import annotations

from pathlib import Path

import pytest

from icon_templates_renderer.adapters.ruamel_mapping_writer import RuamelMappingWriter
from icon_templates_renderer.domain.exceptions import (
    IconNotFoundError,
    InvalidYamlError,
    UnknownPlaceholderError,
    VariantNotFoundError,
)
from icon_templates_renderer.ports.mapping_writer import MappingWriterPort

HEADER = "# icons manifest — hand-maintained, comments matter\n"


def _manifest() -> str:
    return HEADER + (
        "battery:\n"
        "  # group-level mappings\n"
        "  color_mappings:\n"
        '    COLOR_ACCENT: "color12"\n'
        "    COLOR_FOREGROUND: foreground\n"
        "  variants:\n"
        "    - name: battery-0\n"
        "      template: battery-0.svg\n"
        "      output: battery-0.svg\n"
        "    - name: battery-50\n"
        "      template: battery-50.svg\n"
        "      output: battery-50.svg\n"
        "      color_mappings:\n"
        "        COLOR_ACCENT: color3\n"
    )


@pytest.fixture
def manifest_path(tmp_path: Path) -> Path:
    path = tmp_path / "icons.yaml"
    path.write_text(_manifest(), encoding="utf-8")
    return path


@pytest.fixture
def defaults_path(tmp_path: Path) -> Path:
    path = tmp_path / "defaults.yaml"
    path.write_text(
        "# vocabulary defaults\n"
        "defaults:\n"
        "  COLOR_FOREGROUND: foreground\n"
        '  COLOR_ACCENT: "accent-muted"\n',
        encoding="utf-8",
    )
    return path


class TestPortSatisfaction:
    def test_writer_satisfies_port(self) -> None:
        assert isinstance(RuamelMappingWriter(), MappingWriterPort)


class TestSetMapping:
    def test_group_set_preserves_comments_order_quotes(self, manifest_path: Path) -> None:
        writer = RuamelMappingWriter()
        new_text = writer.set_mapping(manifest_path, "battery", None, "COLOR_ACCENT", "color10")
        assert new_text.startswith(HEADER)
        assert "# group-level mappings" in new_text
        assert '"color10"' in new_text
        assert "COLOR_FOREGROUND: foreground" in new_text
        assert new_text.index("COLOR_ACCENT") < new_text.index("COLOR_FOREGROUND")
        assert "battery-50" in new_text
        assert "COLOR_ACCENT: color3" in new_text

    def test_variant_override_created_when_absent(self, manifest_path: Path) -> None:
        writer = RuamelMappingWriter()
        new_text = writer.set_mapping(
            manifest_path, "battery", "battery-0", "COLOR_ACCENT", "color10"
        )
        assert "color_mappings" in new_text
        import yaml

        data = yaml.safe_load(new_text)
        assert data["battery"]["color_mappings"]["COLOR_ACCENT"] == "color12"
        variant = next(v for v in data["battery"]["variants"] if v["name"] == "battery-0")
        assert variant["color_mappings"] == {"COLOR_ACCENT": "color10"}

    def test_group_mappings_created_when_absent(self, tmp_path: Path) -> None:
        path = tmp_path / "icons.yaml"
        path.write_text(
            "plain:\n  variants:\n    - name: v\n      template: v.svg\n      output: v.svg\n",
            encoding="utf-8",
        )
        new_text = RuamelMappingWriter().set_mapping(path, "plain", None, "K", "v")
        import yaml

        assert yaml.safe_load(new_text)["plain"]["color_mappings"] == {"K": "v"}

    def test_unknown_group_rejected(self, manifest_path: Path) -> None:
        with pytest.raises(IconNotFoundError):
            RuamelMappingWriter().set_mapping(manifest_path, "nope", None, "K", "v")
        assert manifest_path.read_text(encoding="utf-8") == _manifest()

    def test_unknown_variant_rejected(self, manifest_path: Path) -> None:
        with pytest.raises(VariantNotFoundError):
            RuamelMappingWriter().set_mapping(manifest_path, "battery", "nope", "K", "v")
        assert manifest_path.read_text(encoding="utf-8") == _manifest()

    def test_missing_file_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(InvalidYamlError):
            RuamelMappingWriter().set_mapping(tmp_path / "absent.yaml", "battery", None, "K", "v")


class TestSetDefault:
    def test_vocabulary_set_preserves_comment(self, defaults_path: Path) -> None:
        new_text = RuamelMappingWriter().set_default(defaults_path, "COLOR_FOREGROUND", "color15")
        assert new_text.startswith("# vocabulary defaults")
        assert "COLOR_FOREGROUND: color15" in new_text
        assert 'COLOR_ACCENT: "accent-muted"' in new_text

    def test_unknown_placeholder_rejected(self, defaults_path: Path) -> None:
        before = defaults_path.read_text(encoding="utf-8")
        with pytest.raises(UnknownPlaceholderError):
            RuamelMappingWriter().set_default(defaults_path, "NOPE", "color1")
        assert defaults_path.read_text(encoding="utf-8") == before


class TestDiff:
    def test_diff_shows_change(self, manifest_path: Path) -> None:
        writer = RuamelMappingWriter()
        new_text = writer.set_mapping(manifest_path, "battery", None, "COLOR_ACCENT", "color10")
        diff = writer.diff(manifest_path, new_text)
        assert '-    COLOR_ACCENT: "color12"' in diff
        assert '+    COLOR_ACCENT: "color10"' in diff
        assert str(manifest_path) in diff

    def test_diff_empty_when_identical(self, manifest_path: Path) -> None:
        writer = RuamelMappingWriter()
        assert writer.diff(manifest_path, manifest_path.read_text(encoding="utf-8")) == ""
