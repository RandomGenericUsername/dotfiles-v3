from __future__ import annotations

import re
from pathlib import Path

from icon_templates_renderer.domain.enums import MappingOrigin
from icon_templates_renderer.domain.exceptions import (
    ColorSchemeKeyNotFoundError,
    MissingMappingError,
)
from icon_templates_renderer.domain.models import ColorScheme, MappingEntry

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


class PathResolutionService:
    """Pure path-joiner.

    Joins a relative ``sub`` path under ``root`` then resolves the result;
    absolute ``sub`` paths pass through. Returns ``None`` when ``root`` is
    ``None`` (no resolution possible — caller decides whether that is fatal).
    """

    def resolve(self, root: Path | None, sub: str) -> Path | None:
        if root is None:
            return None
        path = Path(sub)
        if path.is_absolute():
            return path
        return (root / path).resolve()


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

    def merge_with_origin(
        self,
        vocab_defaults: dict[str, str] | None,
        group_mappings: dict[str, str],
        variant_mappings: dict[str, str],
    ) -> tuple[MappingEntry, ...]:
        """Merge like :meth:`merge` but attribute each entry to its source layer.

        Priority (highest to lowest): variant > group > vocabulary. Entries are
        returned sorted by placeholder for stable output.
        """
        vocab = vocab_defaults or {}
        entries = []
        for placeholder in vocab.keys() | group_mappings.keys() | variant_mappings.keys():
            if placeholder in variant_mappings:
                entries.append(
                    MappingEntry(placeholder, variant_mappings[placeholder], MappingOrigin.VARIANT)
                )
            elif placeholder in group_mappings:
                entries.append(
                    MappingEntry(placeholder, group_mappings[placeholder], MappingOrigin.GROUP)
                )
            else:
                entries.append(
                    MappingEntry(placeholder, vocab[placeholder], MappingOrigin.VOCABULARY)
                )
        entries.sort(key=lambda entry: entry.placeholder)
        return tuple(entries)


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
