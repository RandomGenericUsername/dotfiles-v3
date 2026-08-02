from __future__ import annotations

import re
from pathlib import Path

from icon_templates_renderer.domain.exceptions import (
    ColorSchemeKeyNotFoundError,
    InvalidYamlError,
    MissingMappingError,
)
from icon_templates_renderer.domain.models import ColorScheme, PathOverrides

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


class PathResolutionService:
    """Pure path-resolution logic (v2 yaml_loader._resolve_*).

    Precedence per kind: CLI override > YAML top-level root > YAML-relative.
    ``template_dir`` and ``output_dir`` overrides join the YAML-declared string;
    a ``color_scheme`` override replaces the whole path.
    """

    def resolve_template_dir(
        self,
        base_dir: Path,
        template_dir_str: str,
        overrides: PathOverrides,
        templates_root: Path | None,
    ) -> Path:
        if overrides.template_dir is not None:
            return (overrides.template_dir / template_dir_str).resolve()
        if templates_root is not None:
            return (templates_root / template_dir_str).resolve()
        return self.resolve(base_dir, template_dir_str)

    def resolve_output_dir(
        self,
        base_dir: Path,
        output_dir_str: str,
        overrides: PathOverrides,
        outputs_root: Path | None,
    ) -> Path:
        if overrides.output_dir is not None:
            return (overrides.output_dir / output_dir_str).resolve()
        if outputs_root is not None:
            return (outputs_root / output_dir_str).resolve()
        return self.resolve(base_dir, output_dir_str)

    def resolve_color_scheme(
        self,
        base_dir: Path,
        color_scheme_str: str | None,
        overrides: PathOverrides,
        color_scheme_global: Path | None,
    ) -> Path:
        if overrides.color_scheme is not None:
            return overrides.color_scheme
        if color_scheme_global is not None:
            return color_scheme_global
        if color_scheme_str is None:
            raise InvalidYamlError(
                "No color scheme configured: group declares `color_scheme: ~` "
                "and no --color-scheme or top-level color_scheme was provided"
            )
        return self.resolve(base_dir, color_scheme_str)

    def resolve(self, base: Path, path_str: str) -> Path:
        path = Path(path_str)
        if path.is_absolute():
            return path
        return (base / path).resolve()


class MappingResolutionService:
    """Pure mapping-merge logic (v2 IconGroup.resolve_mappings)."""

    def merge(
        self,
        vocab_defaults: dict[str, str] | None,
        group_mappings: dict[str, str],
        variant_mappings: dict[str, str],
    ) -> dict[str, str]:
        base = vocab_defaults or {}
        return {**base, **group_mappings, **variant_mappings}


class PlaceholderSubstitutionService:
    """Pure SVG placeholder substitution (v2 svg_renderer.render_string)."""

    def substitute(
        self,
        svg: str,
        scheme: ColorScheme,
        unsafe: bool,
        color_mappings: dict[str, str],
    ) -> str:
        def replace(match: re.Match[str]) -> str:
            key = match.group(1)

            if key not in color_mappings:
                if unsafe:
                    return match.group(0)
                raise MissingMappingError(key)

            value = color_mappings[key]

            if value.startswith("#"):
                return value

            resolved = scheme.get(value)
            if resolved is None:
                if unsafe:
                    return match.group(0)
                raise ColorSchemeKeyNotFoundError(key, value)
            return resolved

        return _PLACEHOLDER_RE.sub(replace, svg)
