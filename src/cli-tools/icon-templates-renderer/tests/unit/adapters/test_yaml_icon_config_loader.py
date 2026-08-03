from __future__ import annotations

from pathlib import Path

import pytest

from icon_templates_renderer.adapters.yaml_icon_config_loader import YamlIconConfigLoader
from icon_templates_renderer.domain.exceptions import (
    IconNotFoundError,
    InvalidYamlError,
)
from icon_templates_renderer.domain.models import ResolvedRoots


def _write_icons(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "icons.yaml"
    path.write_text(content)
    return path


def _roots(
    template: Path | None = Path("/root/tpls"),
    color_scheme: Path | None = Path("/global/colors.yaml"),
    output: Path | None = Path("/root/outs"),
) -> ResolvedRoots:
    return ResolvedRoots(
        template_root=template,
        color_scheme=color_scheme,
        output_root=output,
    )


class TestYamlIconConfigLoader:
    def test_valid_icons_yaml_parses(self, tmp_path: Path) -> None:
        path = _write_icons(
            tmp_path,
            "battery:\n"
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
        config = YamlIconConfigLoader().load(path, _roots())
        assert len(config.groups) == 1
        group = config.groups[0]
        assert group.name == "battery"
        assert len(group.variants) == 2

    def test_missing_required_group_field_is_rejected(self, tmp_path: Path) -> None:
        path = _write_icons(
            tmp_path,
            "battery:\n  template_dir: templates/\n",
        )
        with pytest.raises(InvalidYamlError) as excinfo:
            YamlIconConfigLoader().load(path, _roots())
        assert "Icon 'battery' is missing required field: 'variants'" in str(excinfo.value)

    def test_missing_required_variant_field_is_rejected(self, tmp_path: Path) -> None:
        path = _write_icons(
            tmp_path,
            "battery:\n"
            "  template_dir: templates/\n"
            "  output_dir: out/\n"
            "  variants:\n"
            "    - template: battery-0.svg\n"
            "      output: battery-0.svg\n",
        )
        with pytest.raises(InvalidYamlError) as excinfo:
            YamlIconConfigLoader().load(path, _roots())
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

    def test_global_roots_are_used(self, tmp_path: Path) -> None:
        path = _write_icons(
            tmp_path,
            "battery:\n"
            "  template_dir: battery/\n"
            "  output_dir: battery/\n"
            "  variants:\n"
            "    - name: battery-0\n"
            "      template: battery-0.svg\n"
            "      output: battery-0.svg\n",
        )
        group = YamlIconConfigLoader().load(path, _roots()).groups[0]
        assert group.template_dir == (Path("/root/tpls") / "battery/").resolve()
        assert group.output_dir == (Path("/root/outs") / "battery/").resolve()

    def test_default_relative_dirs_join_global_roots(self, tmp_path: Path) -> None:
        path = _write_icons(
            tmp_path,
            "battery:\n"
            "  variants:\n"
            "    - name: battery-0\n"
            "      template: battery-0.svg\n"
            "      output: battery-0.svg\n",
        )
        group = YamlIconConfigLoader().load(path, _roots()).groups[0]
        assert group.template_dir == Path("/root/tpls").resolve()
        assert group.output_dir == Path("/root/outs").resolve()

    def test_none_roots_produce_none_dirs(self, tmp_path: Path) -> None:
        path = _write_icons(
            tmp_path,
            "battery:\n"
            "  variants:\n"
            "    - name: battery-0\n"
            "      template: battery-0.svg\n"
            "      output: battery-0.svg\n",
        )
        group = YamlIconConfigLoader().load(path, None).groups[0]
        assert group.template_dir is None
        assert group.output_dir is None

    def test_absolute_subdir_passthrough(self, tmp_path: Path) -> None:
        path = _write_icons(
            tmp_path,
            "battery:\n"
            "  template_dir: /abs/tpls\n"
            "  output_dir: /abs/out\n"
            "  variants:\n"
            "    - name: battery-0\n"
            "      template: battery-0.svg\n"
            "      output: battery-0.svg\n",
        )
        group = YamlIconConfigLoader().load(path, _roots()).groups[0]
        assert group.template_dir == Path("/abs/tpls")
        assert group.output_dir == Path("/abs/out")

    def test_load_one_returns_matching_group(self, tmp_path: Path) -> None:
        path = _write_icons(
            tmp_path,
            "battery:\n  variants: []\nnetwork:\n  variants: []\n",
        )
        group = YamlIconConfigLoader().load_one(path, "network", _roots())
        assert group.name == "network"

    def test_load_one_unknown_raises(self, tmp_path: Path) -> None:
        path = _write_icons(
            tmp_path,
            "battery:\n  variants: []\n",
        )
        with pytest.raises(IconNotFoundError) as excinfo:
            YamlIconConfigLoader().load_one(path, "nonexistent", _roots())
        assert "Icon 'nonexistent' not found in" in str(excinfo.value)

    def test_variant_paths_join_under_global_root(self, tmp_path: Path) -> None:
        path = _write_icons(
            tmp_path,
            "battery:\n"
            "  template_dir: sub/\n"
            "  variants:\n"
            "    - name: battery-0\n"
            "      template: icons/battery-0.svg\n"
            "      output: battery-0.svg\n",
        )
        group = YamlIconConfigLoader().load(path, _roots()).groups[0]
        variant = group.variants[0]
        assert (
            variant.template == (Path("/root/tpls") / "sub" / "icons" / "battery-0.svg").resolve()
        )
        assert variant.output == (Path("/root/outs") / "battery-0.svg").resolve()
