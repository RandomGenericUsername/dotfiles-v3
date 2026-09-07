from __future__ import annotations

import re
from pathlib import Path

from icon_templates_renderer.domain.enums import MappingOrigin, TemplateMode
from icon_templates_renderer.domain.exceptions import (
    ColorSchemeKeyNotFoundError,
    InvalidPlaceholderNameError,
    MissingMappingError,
)
from icon_templates_renderer.domain.models import ColorScheme, MappingEntry, TemplateShape

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")

SHAPE_RE = re.compile(
    r"<(path|rect|circle|ellipse|line|polyline|polygon)\b"
    r"((?:\"[^\"]*\"|'[^']*'|[^>\"'])*?)(/>|>([\s\S]*?)</\1>)"
)
_ROOT_RE = re.compile(r"<svg\b[^>]*>")
PLACEHOLDER_VALUE_RE = re.compile(r"\{\{(\w+)\}\}")
PLACEHOLDER_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def attr_value(element: str, name: str) -> str | None:
    m = re.search(rf"\b{name}\s*=\s*\"([^\"]*)\"", element)
    return m.group(1) if m else None


def validate_placeholder_name(name: str) -> None:
    """Raise ``InvalidPlaceholderNameError`` when ``name`` breaks ``[A-Z][A-Z0-9_]*``."""
    if PLACEHOLDER_NAME_RE.match(name) is None:
        raise InvalidPlaceholderNameError(name)


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


class TemplateAnalysisService:
    """Pure SVG shape extraction mirroring the GUI extractor (lib/svg.ts).

    Paint attributes inherit from the root ``<svg>`` element: a shape without
    its own ``fill``/``stroke`` consults the root before the "missing fill
    paints black" default applies. Shapes are numbered in document order from
    1, identically to the GUI hit-tester.
    """

    def analyze(self, body: str) -> tuple[TemplateShape, ...]:
        """Return the shapes of ``body`` in document order."""
        return tuple(shape for shape, _ in self._extract(body))

    def extract_with_elements(self, body: str) -> list[tuple[TemplateShape, str]]:
        """Return ``(shape, element)`` pairs in document order (for writers)."""
        return self._extract(body)

    @staticmethod
    def classify(shapes: tuple[TemplateShape, ...]) -> TemplateMode:
        """Templated when any shape carries a placeholder, else bare."""
        return (
            TemplateMode.TEMPLATED
            if any(shape.placeholder for shape in shapes)
            else TemplateMode.BARE
        )

    def _extract(self, body: str) -> list[tuple[TemplateShape, str]]:
        root_match = _ROOT_RE.search(body)
        root_tag = root_match.group(0) if root_match else ""
        root_fill = attr_value(root_tag, "fill")
        root_stroke = attr_value(root_tag, "stroke")

        shapes: list[tuple[TemplateShape, str]] = []
        shape_id = 0
        for match in SHAPE_RE.finditer(body):
            shape_id += 1
            element = match.group(0)
            fill = attr_value(element, "fill")
            if fill is None:
                fill = root_fill
            stroke = attr_value(element, "stroke")
            if stroke is None:
                stroke = root_stroke
            use_stroke = fill == "none"
            if use_stroke:
                paint_attr = "stroke"
                value = stroke
            else:
                paint_attr = "fill"
                value = fill
            placeholder: str | None = None
            literal: str | None = None
            if value is not None:
                pm = PLACEHOLDER_VALUE_RE.search(value)
                if pm is not None:
                    placeholder = pm.group(1)
                else:
                    literal = value
            shapes.append(
                (
                    TemplateShape(
                        shape_id=shape_id,
                        tag=match.group(1),
                        paint_attr=paint_attr,
                        placeholder=placeholder,
                        literal=literal,
                    ),
                    element,
                )
            )
        return shapes
