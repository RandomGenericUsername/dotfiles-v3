from __future__ import annotations

from pathlib import Path

from icon_templates_renderer.constants import VOCABULARY_FILENAME
from icon_templates_renderer.domain.exceptions import (
    ColorSchemeNotFoundError,
    ConfigResolutionError,
    TemplateNotFoundError,
)
from icon_templates_renderer.domain.models import (
    IconConfig,
    IconGroup,
    ListRequest,
    ListResult,
    RenderedVariant,
    RenderRequest,
    RenderResult,
    ResolvedRoots,
    ValidateRequest,
    ValidateResult,
)
from icon_templates_renderer.ports.color_scheme_loader import ColorSchemeLoaderPort
from icon_templates_renderer.ports.icon_config_loader import IconConfigLoaderPort
from icon_templates_renderer.ports.svg_renderer import SvgRendererPort
from icon_templates_renderer.ports.vocabulary_loader import VocabularyLoaderPort


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
    ) -> None:
        self._config_loader = config_loader
        self._color_loader = color_loader
        self._vocab_loader = vocab_loader
        self._svg_renderer = svg_renderer

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
