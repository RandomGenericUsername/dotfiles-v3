from __future__ import annotations

from pathlib import Path

import pytest

from icon_templates_renderer.adapters.yaml_icon_config_loader import YamlIconConfigLoader
from icon_templates_renderer.domain.exceptions import (
    IconNotFoundError,
    InvalidYamlError,
)
from icon_templates_renderer.domain.models import PathOverrides


def _write_icons(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "icons.yaml"
    path.write_text(content)
    return path


class TestYamlIconConfigLoader:
    def test_valid_icons_yaml_parses(self, tmp_path: Path) -> None:
        path = _write_icons(
            tmp_path,
            "battery:\n"
            "  color_scheme: colors.yaml\n"
            "  template_dir: templates/\n"
            "  output_dir: out/\n"
            "  variants:\n"
            "    - name: battery-0\n"
            "      template: battery-0.svg\n"
            "      output: battery-0.svg\n"
            "    - name: battery-100\n"
            "      template: battery-100.svg\n"
            "      output: battery-100.svg\n",
        )
        config = YamlIconConfigLoader().load(path)
        assert len(config.groups) == 1
        group = config.groups[0]
        assert group.name == "battery"
        assert len(group.variants) == 2

    def test_missing_required_group_field_is_rejected(self, tmp_path: Path) -> None:
        path = _write_icons(
            tmp_path,
            "battery:\n  template_dir: templates/\n  output_dir: out/\n  variants: []\n",
        )
        with pytest.raises(InvalidYamlError) as excinfo:
            YamlIconConfigLoader().load(path)
        assert "Icon 'battery' is missing required field: 'color_scheme'" in str(excinfo.value)

    def test_missing_required_variant_field_is_rejected(self, tmp_path: Path) -> None:
        path = _write_icons(
            tmp_path,
            "battery:\n"
            "  color_scheme: colors.yaml\n"
            "  template_dir: templates/\n"
            "  output_dir: out/\n"
            "  variants:\n"
            "    - template: battery-0.svg\n"
            "      output: battery-0.svg\n",
        )
        with pytest.raises(InvalidYamlError) as excinfo:
            YamlIconConfigLoader().load(path)
        assert "A variant in icon 'battery' is missing required field: 'name'" in str(excinfo.value)

    def test_missing_yaml_file_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "does-not-exist.yaml"
        with pytest.raises(InvalidYamlError) as excinfo:
            YamlIconConfigLoader().load(path)
        assert f"YAML file not found: {path}" in str(excinfo.value)

    def test_malformed_yaml_raises(self, tmp_path: Path) -> None:
        path = _write_icons(tmp_path, "a: [unclosed\n")
        with pytest.raises(InvalidYamlError) as excinfo:
            YamlIconConfigLoader().load(path)
        assert "Failed to parse YAML:" in str(excinfo.value)

    def test_non_mapping_root_raises(self, tmp_path: Path) -> None:
        path = _write_icons(tmp_path, "- item1\n- item2\n")
        with pytest.raises(InvalidYamlError) as excinfo:
            YamlIconConfigLoader().load(path)
        assert "YAML root must be a mapping of icon group keys" in str(excinfo.value)

    def test_top_level_roots_are_used(self, tmp_path: Path) -> None:
        path = _write_icons(
            tmp_path,
            "templates_root: /root/tpls\n"
            "color_scheme: /global/colors.yaml\n"
            "outputs_root: /root/outs\n"
            "battery:\n"
            "  color_scheme: ignored.yaml\n"
            "  template_dir: battery/\n"
            "  output_dir: battery/\n"
            "  variants:\n"
            "    - name: battery-0\n"
            "      template: battery-0.svg\n"
            "      output: battery-0.svg\n",
        )
        group = YamlIconConfigLoader().load(path).groups[0]
        assert group.color_scheme == Path("/global/colors.yaml")
        assert group.template_dir == Path("/root/tpls/battery/")
        assert group.output_dir == Path("/root/outs/battery/")

    def test_cli_overrides_join_template_and_output(self, tmp_path: Path) -> None:
        path = _write_icons(
            tmp_path,
            "battery:\n"
            "  color_scheme: colors.yaml\n"
            "  template_dir: battery/\n"
            "  output_dir: battery/\n"
            "  variants:\n"
            "    - name: battery-0\n"
            "      template: battery-0.svg\n"
            "      output: battery-0.svg\n",
        )
        overrides = PathOverrides(
            template_dir=Path("/new/templates"),
            color_scheme=Path("/new/colors.yaml"),
            output_dir=Path("/new/out"),
        )
        group = YamlIconConfigLoader().load(path, overrides).groups[0]
        assert group.color_scheme == Path("/new/colors.yaml")
        assert group.template_dir == Path("/new/templates/battery/")
        assert group.output_dir == Path("/new/out/battery/")

    def test_load_one_returns_matching_group(self, tmp_path: Path) -> None:
        path = _write_icons(
            tmp_path,
            "battery:\n"
            "  color_scheme: colors.yaml\n"
            "  template_dir: templates/\n"
            "  output_dir: out/\n"
            "  variants: []\n"
            "network:\n"
            "  color_scheme: colors.yaml\n"
            "  template_dir: templates/\n"
            "  output_dir: out/\n"
            "  variants: []\n",
        )
        group = YamlIconConfigLoader().load_one(path, "network")
        assert group.name == "network"

    def test_load_one_unknown_raises(self, tmp_path: Path) -> None:
        path = _write_icons(
            tmp_path,
            "battery:\n"
            "  color_scheme: colors.yaml\n"
            "  template_dir: templates/\n"
            "  output_dir: out/\n"
            "  variants: []\n",
        )
        with pytest.raises(IconNotFoundError) as excinfo:
            YamlIconConfigLoader().load_one(path, "nonexistent")
        assert "Icon 'nonexistent' not found in" in str(excinfo.value)

    def test_color_scheme_null_placeholder_uses_override(self, tmp_path: Path) -> None:
        """A `color_scheme: ~` group resolves via the CLI override."""
        path = _write_icons(
            tmp_path,
            "battery:\n"
            "  color_scheme: ~\n"
            "  template_dir: templates/\n"
            "  output_dir: out/\n"
            "  variants:\n"
            "    - name: battery-0\n"
            "      template: battery-0.svg\n"
            "      output: battery-0.svg\n",
        )
        overrides = PathOverrides(color_scheme=Path("/new/colors.yaml"))
        group = YamlIconConfigLoader().load(path, overrides).groups[0]
        assert group.color_scheme == Path("/new/colors.yaml")

    def test_color_scheme_null_placeholder_uses_top_level(self, tmp_path: Path) -> None:
        path = _write_icons(
            tmp_path,
            "color_scheme: /global/colors.yaml\n"
            "battery:\n"
            "  color_scheme: ~\n"
            "  template_dir: templates/\n"
            "  output_dir: out/\n"
            "  variants: []\n",
        )
        group = YamlIconConfigLoader().load(path).groups[0]
        assert group.color_scheme == Path("/global/colors.yaml")

    def test_color_scheme_null_placeholder_without_source_raises(self, tmp_path: Path) -> None:
        path = _write_icons(
            tmp_path,
            "battery:\n"
            "  color_scheme: ~\n"
            "  template_dir: templates/\n"
            "  output_dir: out/\n"
            "  variants: []\n",
        )
        with pytest.raises(InvalidYamlError) as excinfo:
            YamlIconConfigLoader().load(path)
        assert "color_scheme" in str(excinfo.value)
