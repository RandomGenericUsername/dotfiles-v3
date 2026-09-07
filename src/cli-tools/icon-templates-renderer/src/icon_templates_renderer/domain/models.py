from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from icon_templates_renderer.domain.enums import MappingOrigin, Verbosity


def _frozen_mapping(mapping: dict[str, str]) -> MappingProxyType[str, str]:
    return MappingProxyType(dict(mapping))


@dataclass(frozen=True)
class ColorScheme:
    values: MappingProxyType[str, str] = field(default_factory=lambda: MappingProxyType({}))

    def get(self, name: str) -> str | None:
        return self.values.get(name)

    @classmethod
    def from_dict(cls, values: dict[str, str]) -> ColorScheme:
        return cls(values=_frozen_mapping(values))


@dataclass(frozen=True)
class Variant:
    name: str
    template: Path
    output: Path
    color_mappings: MappingProxyType[str, str] = field(default_factory=lambda: MappingProxyType({}))


@dataclass(frozen=True)
class IconGroup:
    name: str
    template_dir: Path | None = None
    output_dir: Path | None = None
    unsafe: bool = False
    variants: tuple[Variant, ...] = ()
    color_mappings: MappingProxyType[str, str] = field(default_factory=lambda: MappingProxyType({}))

    def resolve_mappings(
        self,
        variant: Variant,
        vocab_defaults: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Merge vocabulary defaults, group-level, and variant-level color_mappings.

        Priority (highest to lowest): variant > group > vocab_defaults.
        """
        base = vocab_defaults or {}
        return {**base, **self.color_mappings, **variant.color_mappings}


@dataclass(frozen=True)
class IconConfig:
    groups: tuple[IconGroup, ...] = ()


@dataclass(frozen=True)
class Vocabulary:
    defaults: MappingProxyType[str, str] = field(default_factory=lambda: MappingProxyType({}))

    @classmethod
    def from_dict(cls, defaults: dict[str, str]) -> Vocabulary:
        return cls(defaults=_frozen_mapping(defaults))

    def as_dict(self) -> dict[str, str]:
        return dict(self.defaults)


@dataclass(frozen=True)
class ResolvedRoots:
    """Resolved path roots shared across all groups of a single render.

    Populated by the CLI orchestrator from settings/env/flags + discovery.
    Individual fields may be ``None`` (e.g. for ``list`` which needs no roots).
    """

    template_root: Path | None = None
    color_scheme: Path | None = None
    output_root: Path | None = None


@dataclass(frozen=True)
class RenderRequest:
    yaml_path: Path
    icon: str | None = None
    unsafe: bool | None = None
    roots: ResolvedRoots = field(default_factory=ResolvedRoots)
    vocabulary_path: Path | None = None


@dataclass(frozen=True)
class RenderedVariant:
    variant_name: str
    group_name: str
    output_path: Path


@dataclass(frozen=True)
class RenderResult:
    success: bool
    rendered: tuple[RenderedVariant, ...] = ()


@dataclass(frozen=True)
class ListRequest:
    yaml_path: Path
    icon: str | None = None
    roots: ResolvedRoots = field(default_factory=ResolvedRoots)


@dataclass(frozen=True)
class ListResult:
    groups: tuple[tuple[str, tuple[str, ...]], ...] = ()
    single: bool = False


@dataclass(frozen=True)
class ValidateRequest:
    yaml_path: Path
    icon: str | None = None
    roots: ResolvedRoots = field(default_factory=ResolvedRoots)


@dataclass(frozen=True)
class ValidateResult:
    ok: bool = True
    checked_groups: int = 0
    checked_variants: int = 0


@dataclass(frozen=True)
class MappingEntry:
    placeholder: str
    token: str
    origin: MappingOrigin


@dataclass(frozen=True)
class VariantMappingView:
    variant: str
    template_path: Path
    svg_body: str
    entries: tuple[MappingEntry, ...] = ()


@dataclass(frozen=True)
class GroupMappingView:
    group: str
    variants: tuple[VariantMappingView, ...] = ()


@dataclass(frozen=True)
class MappingShowRequest:
    yaml_path: Path
    icon: str | None = None
    roots: ResolvedRoots = field(default_factory=ResolvedRoots)
    vocabulary_path: Path | None = None


@dataclass(frozen=True)
class MappingShowResult:
    groups: tuple[GroupMappingView, ...] = ()
    palette: ColorScheme = field(default_factory=ColorScheme)
    missing_tokens: tuple[str, ...] = ()
    shadows: tuple[tuple[str, tuple[str, ...]], ...] = ()


@dataclass(frozen=True)
class MappingSetRequest:
    yaml_path: Path
    group: str
    placeholder: str
    token: str
    variant: str | None = None
    roots: ResolvedRoots = field(default_factory=ResolvedRoots)
    unsafe: bool = False
    dry_run: bool = False
    show_diff: bool = False


@dataclass(frozen=True)
class MappingSetResult:
    group: str
    placeholder: str
    token: str
    variant: str | None = None
    dry_run: bool = False
    diff_text: str = ""


@dataclass(frozen=True)
class MappingSetDefaultRequest:
    defaults_path: Path
    placeholder: str
    token: str
    icons_path: Path | None = None
    roots: ResolvedRoots = field(default_factory=ResolvedRoots)
    unsafe: bool = False
    dry_run: bool = False
    show_diff: bool = False


@dataclass(frozen=True)
class MappingSetDefaultResult:
    placeholder: str
    token: str
    dry_run: bool = False
    diff_text: str = ""
    shadows: tuple[str, ...] = ()


@dataclass(frozen=True)
class OutputSettings:
    output_dir: Path | None = None
    verbosity: Verbosity = Verbosity.NORMAL


@dataclass(frozen=True)
class TemplatesSettings:
    dir: Path | None = None


@dataclass(frozen=True)
class ColorSchemeSettings:
    path: Path | None = None


@dataclass(frozen=True)
class AppSettings:
    output: OutputSettings = field(default_factory=OutputSettings)
    templates: TemplatesSettings = field(default_factory=TemplatesSettings)
    color_scheme: ColorSchemeSettings = field(default_factory=ColorSchemeSettings)
