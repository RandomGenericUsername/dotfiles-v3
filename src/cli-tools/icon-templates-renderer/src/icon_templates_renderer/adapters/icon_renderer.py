from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from icon_templates_renderer.adapters.ruamel_mapping_writer import RuamelMappingWriter
from icon_templates_renderer.constants import VOCABULARY_FILENAME
from icon_templates_renderer.domain.exceptions import (
    ColorSchemeNotFoundError,
    ConfigResolutionError,
    TemplateNotFoundError,
    UnknownTokenError,
)
from icon_templates_renderer.domain.models import (
    GroupMappingView,
    IconConfig,
    IconGroup,
    ListRequest,
    ListResult,
    MappingSetDefaultRequest,
    MappingSetDefaultResult,
    MappingSetRequest,
    MappingSetResult,
    MappingShowRequest,
    MappingShowResult,
    RenderedVariant,
    RenderRequest,
    RenderResult,
    ResolvedRoots,
    ValidateRequest,
    ValidateResult,
    VariantMappingView,
)
from icon_templates_renderer.domain.services import MappingResolutionService
from icon_templates_renderer.ports.color_scheme_loader import ColorSchemeLoaderPort
from icon_templates_renderer.ports.icon_config_loader import IconConfigLoaderPort
from icon_templates_renderer.ports.mapping_writer import MappingWriterPort
from icon_templates_renderer.ports.svg_renderer import SvgRendererPort
from icon_templates_renderer.ports.vocabulary_loader import VocabularyLoaderPort

_HEX_LITERAL_RE = re.compile(r"#[0-9a-fA-F]{6}\Z")


def _validate_token(token: str, scheme_keys: set[str], unsafe: bool) -> None:
    """Reject tokens that are neither #rrggbb literals nor scheme keys."""
    if unsafe:
        return
    if _HEX_LITERAL_RE.match(token) is not None:
        return
    if token not in scheme_keys:
        raise UnknownTokenError(token)


class IconRenderer:
    """Orchestrates config loading, color-scheme loading, and SVG rendering.

    Implements the v2 ``IconRenderer`` (api/icon_renderer.py) sequencing while
    depending on injected ports.
    """

    def __init__(
        self,
        config_loader: IconConfigLoaderPort,
        color_loader: ColorSchemeLoaderPort,
        vocab_loader: VocabularyLoaderPort,
        svg_renderer: SvgRendererPort,
        mapping_service: MappingResolutionService | None = None,
        mapping_writer: MappingWriterPort | None = None,
    ) -> None:
        self._config_loader = config_loader
        self._color_loader = color_loader
        self._vocab_loader = vocab_loader
        self._svg_renderer = svg_renderer
        self._mapping_service = mapping_service or MappingResolutionService()
        self._mapping_writer = mapping_writer or RuamelMappingWriter()

    def render(self, request: RenderRequest) -> RenderResult:
        """Render icons. Returns result with output paths written."""
        roots = self._require_roots(request.roots, "render")
        groups = self._load_groups(request.yaml_path, request.icon, roots)
        vocab = self._load_vocab(request.yaml_path, request.vocabulary_path)
        rendered: list[RenderedVariant] = []

        for group in groups:
            effective_unsafe = request.unsafe if request.unsafe is not None else group.unsafe
            scheme = self._color_loader.load(roots.color_scheme)
            group.output_dir.mkdir(parents=True, exist_ok=True)

            for variant in group.variants:
                color_mappings = group.resolve_mappings(variant, vocab.as_dict())
                out = self._svg_renderer.render_variant(
                    variant, scheme, effective_unsafe, color_mappings
                )
                rendered.append(
                    RenderedVariant(
                        variant_name=variant.name,
                        group_name=group.name,
                        output_path=out,
                    )
                )

        return RenderResult(success=True, rendered=tuple(rendered))

    def list(self, request: ListRequest) -> ListResult:
        """List icon groups and variant names. Roots may be None (names only)."""
        if request.icon is not None:
            group = self._config_loader.load_one(request.yaml_path, request.icon, request.roots)
            return ListResult(
                groups=((group.name, tuple(v.name for v in group.variants)),),
                single=True,
            )

        config = self._config_loader.load(request.yaml_path, request.roots)
        groups = tuple((g.name, tuple(v.name for v in g.variants)) for g in config.groups)
        return ListResult(groups=groups, single=False)

    def validate(self, request: ValidateRequest) -> ValidateResult:
        """Validate YAML and all referenced files. Raises on first error."""
        roots = self._require_roots(request.roots, "validate")
        groups = self._load_groups(request.yaml_path, request.icon, roots)
        checked_variants = 0
        for group in groups:
            if not roots.color_scheme.exists():
                raise ColorSchemeNotFoundError(f"Color scheme not found: {roots.color_scheme}")
            for variant in group.variants:
                checked_variants += 1
                if not variant.template.exists():
                    raise TemplateNotFoundError(variant.template)
        return ValidateResult(
            ok=True,
            checked_groups=len(groups),
            checked_variants=checked_variants,
        )

    def mapping_show(self, request: MappingShowRequest) -> MappingShowResult:
        """Inspect merged mappings with per-entry origin. Read-only, never renders.

        Missing palette tokens are collected, never raised.
        """
        roots = self._require_show_roots(request.roots)
        groups = self._load_groups(request.yaml_path, request.icon, roots)
        vocab = self._load_vocab(request.yaml_path, request.vocabulary_path)
        scheme = self._color_loader.load(roots.color_scheme)

        group_views: list[GroupMappingView] = []
        missing: set[str] = set()
        for group in groups:
            variant_views: list[VariantMappingView] = []
            for variant in group.variants:
                if not variant.template.exists():
                    raise TemplateNotFoundError(variant.template)
                entries = self._mapping_service.merge_with_origin(
                    vocab.as_dict(),
                    dict(group.color_mappings),
                    dict(variant.color_mappings),
                )
                for entry in entries:
                    if not entry.token.startswith("#") and scheme.get(entry.token) is None:
                        missing.add(entry.token)
                variant_views.append(
                    VariantMappingView(
                        variant=variant.name,
                        template_path=variant.template,
                        svg_body=variant.template.read_text(encoding="utf-8"),
                        entries=entries,
                    )
                )
            group_views.append(GroupMappingView(group=group.name, variants=tuple(variant_views)))

        shadow_sets = self._shadow_sets(groups)
        shadows = tuple(
            (placeholder, tuple(sorted(shadow_sets[placeholder])))
            for placeholder in sorted(shadow_sets)
        )
        return MappingShowResult(
            groups=tuple(group_views),
            palette=scheme,
            missing_tokens=tuple(sorted(missing)),
            shadows=shadows,
        )

    def mapping_set(self, request: MappingSetRequest) -> MappingSetResult:
        """Apply one group- or variant-scoped mapping edit. Atomic unless dry-run."""
        roots = self._require_scheme_root(request.roots)
        scheme = self._color_loader.load(roots.color_scheme)
        _validate_token(request.token, set(scheme.values), request.unsafe)
        new_text = self._mapping_writer.set_mapping(
            request.yaml_path,
            request.group,
            request.variant,
            request.placeholder,
            request.token,
        )
        diff_text = (
            self._mapping_writer.diff(request.yaml_path, new_text) if request.show_diff else ""
        )
        if not request.dry_run:
            self._atomic_write(request.yaml_path, new_text)
        return MappingSetResult(
            group=request.group,
            placeholder=request.placeholder,
            token=request.token,
            variant=request.variant,
            dry_run=request.dry_run,
            diff_text=diff_text,
        )

    def mapping_set_default(self, request: MappingSetDefaultRequest) -> MappingSetDefaultResult:
        """Retarget one vocabulary default; report groups shadowing the placeholder."""
        roots = self._require_scheme_root(request.roots)
        scheme = self._color_loader.load(roots.color_scheme)
        _validate_token(request.token, set(scheme.values), request.unsafe)
        new_text = self._mapping_writer.set_default(
            request.defaults_path, request.placeholder, request.token
        )
        shadows = self._shadows_for_placeholder(request)
        diff_text = (
            self._mapping_writer.diff(request.defaults_path, new_text) if request.show_diff else ""
        )
        if not request.dry_run:
            self._atomic_write(request.defaults_path, new_text)
        return MappingSetDefaultResult(
            placeholder=request.placeholder,
            token=request.token,
            dry_run=request.dry_run,
            diff_text=diff_text,
            shadows=shadows,
        )

    def _shadows_for_placeholder(self, request: MappingSetDefaultRequest) -> tuple[str, ...]:
        icons_path = request.icons_path
        if icons_path is None:
            icons_path = request.defaults_path.parent / "icons.yaml"
            if not icons_path.exists():
                return ()
        config = self._config_loader.load(icons_path, request.roots)
        shadow_sets = self._shadow_sets(list(config.groups))
        if request.placeholder not in shadow_sets:
            return ()
        return tuple(sorted(shadow_sets[request.placeholder]))

    @staticmethod
    def _shadow_sets(groups: list[IconGroup]) -> dict[str, set[str]]:
        """Map each placeholder to the groups overriding it (group or variant level)."""
        shadow_sets: dict[str, set[str]] = {}
        for group in groups:
            for placeholder in set(group.color_mappings):
                shadow_sets.setdefault(placeholder, set()).add(group.name)
            for variant in group.variants:
                for placeholder in set(variant.color_mappings):
                    shadow_sets.setdefault(placeholder, set()).add(group.name)
        return shadow_sets

    @staticmethod
    def _atomic_write(path: Path, text: str) -> None:
        """Write text atomically via temp file + rename."""
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f"{path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(tmp_name, path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def _load_groups(
        self, yaml_path: Path, icon: str | None, roots: ResolvedRoots
    ) -> list[IconGroup]:
        if icon is not None:
            return [self._config_loader.load_one(yaml_path, icon, roots)]
        config: IconConfig = self._config_loader.load(yaml_path, roots)
        return list(config.groups)

    def _load_vocab(self, yaml_path: Path, vocabulary_path: Path | None):
        path = (
            vocabulary_path
            if vocabulary_path is not None
            else yaml_path.parent / VOCABULARY_FILENAME
        )
        return self._vocab_loader.load(path)

    @staticmethod
    def _require_roots(roots: ResolvedRoots, operation: str) -> ResolvedRoots:
        if roots.template_root is None:
            raise ConfigResolutionError(
                "templates_dir",
                ("--template-dir", "ICON_RENDERER__TEMPLATES__DIR", "[templates] dir", "discovery"),
            )
        if roots.color_scheme is None:
            raise ConfigResolutionError(
                "color_scheme",
                (
                    "--color-scheme",
                    "ICON_RENDERER__COLOR_SCHEME__PATH",
                    "[color_scheme] path",
                    "discovery",
                ),
            )
        if roots.output_root is None:
            raise ConfigResolutionError(
                "output_dir",
                ("--output-dir", "ICON_RENDERER__OUTPUT__OUTPUT_DIR", "[output] output_dir"),
            )
        return roots

    @staticmethod
    def _require_show_roots(roots: ResolvedRoots) -> ResolvedRoots:
        """Require the read-only roots for mapping inspection (no output dir)."""
        if roots.template_root is None:
            raise ConfigResolutionError(
                "templates_dir",
                ("--template-dir", "ICON_RENDERER__TEMPLATES__DIR", "[templates] dir", "discovery"),
            )
        if roots.color_scheme is None:
            raise ConfigResolutionError(
                "color_scheme",
                (
                    "--color-scheme",
                    "ICON_RENDERER__COLOR_SCHEME__PATH",
                    "[color_scheme] path",
                    "discovery",
                ),
            )
        return roots

    @staticmethod
    def _require_scheme_root(roots: ResolvedRoots) -> ResolvedRoots:
        """Require the color scheme root for token validation."""
        if roots.color_scheme is None:
            raise ConfigResolutionError(
                "color_scheme",
                (
                    "--color-scheme",
                    "ICON_RENDERER__COLOR_SCHEME__PATH",
                    "[color_scheme] path",
                    "discovery",
                ),
            )
        return roots
