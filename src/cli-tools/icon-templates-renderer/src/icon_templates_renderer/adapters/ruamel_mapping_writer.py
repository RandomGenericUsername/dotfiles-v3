from __future__ import annotations

import difflib
import re
from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from icon_templates_renderer.domain.exceptions import (
    IconNotFoundError,
    InvalidYamlError,
    UnknownPlaceholderError,
    VariantNotFoundError,
)

_INDENT_RE = re.compile(r"^( +)\S")


def _infer_indent(text: str) -> int:
    """Infer the mapping indent width from the file; fall back to 2."""
    widths = {
        match.group(1).__len__()
        for line in text.splitlines()
        if (match := _INDENT_RE.match(line)) is not None
    }
    widths.discard(0)
    return min(widths) if widths else 2


class RuamelMappingWriter:
    """Surgical comment-preserving YAML edits for color_mappings.

    Round-trip load/dump preserves comments, key order, quoting, and the
    indentation of existing nodes; inferred indent settings apply only to
    newly created ``color_mappings`` blocks.
    """

    def set_mapping(
        self,
        yaml_path: Path,
        group: str,
        variant: str | None,
        placeholder: str,
        token: str,
    ) -> str:
        data, yaml = self._load(yaml_path)
        if group not in data:
            raise IconNotFoundError(group, yaml_path)
        group_node = data[group]
        if group_node is None:
            group_node = CommentedMap()
            data[group] = group_node
        if not isinstance(group_node, dict):
            raise InvalidYamlError(f"Icon '{group}' must be a mapping in {yaml_path}")
        target: dict[str, Any] = group_node
        if variant is not None:
            target = self._find_variant(group_node, group, variant, yaml_path)
        mappings = target.get("color_mappings")
        if mappings is None:
            mappings = CommentedMap()
            target["color_mappings"] = mappings
        if not isinstance(mappings, dict):
            raise InvalidYamlError(f"'color_mappings' must be a mapping in {yaml_path}")
        mappings[placeholder] = token
        return self._dump(data, yaml)

    def set_default(self, yaml_path: Path, placeholder: str, token: str) -> str:
        data, yaml = self._load(yaml_path)
        defaults = data.get("defaults") if isinstance(data, dict) else None
        if not isinstance(defaults, dict):
            raise InvalidYamlError(
                f"Vocabulary file must contain a 'defaults' mapping: {yaml_path}"
            )
        if placeholder not in defaults:
            raise UnknownPlaceholderError(placeholder, yaml_path)
        defaults[placeholder] = token
        return self._dump(data, yaml)

    def add_variant(
        self,
        yaml_path: Path,
        group: str,
        variant: str,
        template: str,
        output: str,
    ) -> str:
        data, yaml = self._load(yaml_path)
        group_node = data.get(group)
        if group_node is None:
            group_node = CommentedMap()
            data[group] = group_node
        if not isinstance(group_node, dict):
            raise InvalidYamlError(f"Icon '{group}' must be a mapping in {yaml_path}")
        variants = group_node.get("variants")
        if variants is None:
            variants = []
            group_node["variants"] = variants
        if not isinstance(variants, list):
            raise InvalidYamlError(f"'variants' must be a list in {yaml_path}")
        for entry in variants:
            if isinstance(entry, dict) and entry.get("name") == variant:
                raise InvalidYamlError(
                    f"Variant '{variant}' already exists in {yaml_path}"
                )
        variants.append(
            CommentedMap({"name": variant, "template": template, "output": output})
        )
        return self._dump(data, yaml)

    def diff(self, yaml_path: Path, new_text: str) -> str:
        old_text = yaml_path.read_text(encoding="utf-8")
        if old_text == new_text:
            return ""
        return "".join(
            difflib.unified_diff(
                old_text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=str(yaml_path),
                tofile=str(yaml_path),
            )
        )

    def _load(self, yaml_path: Path) -> tuple[dict[str, Any], YAML]:
        try:
            text = yaml_path.read_text(encoding="utf-8")
        except OSError:
            raise InvalidYamlError(f"YAML file not found: {yaml_path}") from None
        yaml = YAML(typ="rt")
        yaml.preserve_quotes = True
        data = yaml.load(text)
        if data is None:
            raise InvalidYamlError(f"YAML file is empty: {yaml_path}")
        if not isinstance(data, dict):
            raise InvalidYamlError(f"YAML file must contain a mapping: {yaml_path}")
        mapping_indent = _infer_indent(text)
        yaml.indent(mapping=mapping_indent, sequence=mapping_indent * 2, offset=mapping_indent)
        # Never re-wrap long scalars: the emitter default folds lines near
        # 80 columns, which would reformat unrelated entries on every write.
        yaml.width = 1_000_000
        return data, yaml

    def _dump(self, data: dict[str, Any], yaml: YAML) -> str:
        buffer = StringIO()
        yaml.dump(data, buffer)
        return buffer.getvalue()

    @staticmethod
    def _find_variant(
        group_node: dict[str, Any], group: str, variant: str, yaml_path: Path
    ) -> dict[str, Any]:
        variants = group_node.get("variants")
        if not isinstance(variants, list):
            raise VariantNotFoundError(variant, group)
        for entry in variants:
            if isinstance(entry, dict) and entry.get("name") == variant:
                return entry
        raise VariantNotFoundError(variant, group)
