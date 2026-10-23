## Context

Chain today (`src/runtime`):

```
ApplyWallpaperUseCase.run (application/apply_wallpaper.py)
 → DerivationPipeline.ensure_icons(peh) (application/derive.py:446-494)
 → ItrAdapter.render(peh, templates_dir, mappings_path, work)
    (adapters/itr_adapter.py:153+) — env ICON_RENDERER__OUTPUT__OUTPUT_DIR +
    ICON_RENDERER__COLOR_SCHEME__PATH, mappings as positional arg
 → itr render <mappings> (icon-templates-renderer/cli/render.py)
    — merge order variant > group > vocab (domain/services.py:
    MappingResolutionService), placeholder regex \{\{(\w+)\}\}
    (PlaceholderSubstitutionService), literal `#` passthrough.
```

Config resolution (`assembled_config_resolver.py:67-72` + `cli/_helpers.py`):
overridable roots are exactly `output.output_dir`, `templates.dir`,
`color_scheme.path`. `icons.yaml` is **not** env-overridable — confirmed,
so the middleware must materialize a file.

Palette shape: CSG `colors.yaml.j2` emits top-level
`background`/`foreground`/`cursor` + `colors:` list of 16
(`color-scheme-generator/defaults/templates/colors.yaml.j2`). ITR
`FileColorSchemeLoader._extract_values` maps those to
`{background, foreground, cursor, color0..color15}` plus any semantic
passthrough keys. `defaults.yaml` references `surface`/`accent`/`accent-muted`
which may be absent from a given palette — the guard must intersect
candidates with the loaded palette and never emit a dangling token.

Cache: `icons_entry_hash(peh || t_h || m_h)` (`runtime/adapters/hashing.py`).
`ensure_icons` hashes spine inputs via `_hash_path_input` (file → `hash_file`,
dir → `canonical_hash_dir`). An overlay changes `m_h` semantics to
*effective* mappings.

## Goals / Non-Goals

**Goals**

- Bar icons always meet a contrast threshold (default 4.5:1) against the bar
  backdrop, using only colors from the current wallpaper's palette.
- Deterministic per `(wallpaper, palette, spine mappings)`: same inputs →
  same overlay → same `ih`.
- Spine read-only; staging-only overlay; cache-correct; graceful degradation
  (guard failure ⇒ original mappings + warning, icons layer stays graceful
  per `apply_wallpaper.py`).
- Dependency handled inside the existing provision-then-execute split (see D4).

**Non-Goals**

- See proposal Non-goals. Additionally: no per-variant accent recoloring
  (`camera-accent`, `warning-caution` stay fixed), no threshold
  auto-tuning UI.

## Decisions

### D1. Middleware lives in runtime `DerivationPipeline.ensure_icons`, not in ITR

ITR stays a pure renderer (manual `itr render` reproducible, no behavior
change, no CLI/schema churn). The runtime owns derivation policy, cache keys,
and graceful degradation — the natural seam. ITR's merge/substitution
services are reused by contract, not modified.

### D2. Ephemeral overlay YAML in staging, spine untouched

`ensure_icons` copies the resolved spine mappings (file case: `icons.yaml`;
dir case: replicate dir, patch only `icons.yaml`) into the staging area,
retargets group-level `COLOR_FOREGROUND` (and `COLOR_JOIN` where present)
for allowlisted bar groups below threshold, and passes the overlay path to
`ItrAdapter.render`. Comment-preserving write is preferred (mirror ITR's
`RuamelMappingWriter`); otherwise a round-trip-safe YAML dump is acceptable
since the overlay is never committed.

**Amendment 2026-09-18 (live bug):** the file-case overlay MUST also stage a
copy of the spine's sibling `defaults.yaml` next to the patched `icons.yaml`.
ITR resolves its vocabulary as `yaml.parent / "defaults.yaml"` with an empty
vocabulary when absent — groups with empty `color_mappings` (`wlogout`,
`email-client`, `wallpaper-selector`) then fail the whole render with
`Placeholder ... has no entry in color_mappings`, yielding `icons: null` and
warning-triangle bar icons. The staged copy stays OUT of the cache key:
`ItrAdapter` recomputes the entry hash from exactly the path it receives
(`output_dir.name` validation), so pipeline and adapter must hash
identically — `m_h = hash_file(overlay icons.yaml)`, mirroring the pre-guard
spine key (which likewise never covered the vocabulary file).

### D3. Backdrop = sampled wallpaper top-strip, fallback = palette `background`

The bar floats on the wallpaper's top ~48px, not on a palette swatch, so the
honest signal is the wallpaper pixels. Primary: average relative luminance
of the top band. Fallback (unreadable image, unsupported format, sampling
error): palette `background`. The chosen backdrop source is logged and stored
in `meta.json` so `inspect` can explain the decision. Sampling runs inside
`ensure_icons` before staging (read-only input read, no spine mutation).

### D4. Dependency: `Pillow` in `src/runtime/pyproject.toml`, provisioned by the existing `cli_tools` role — no new provisioning work

Wallpaper decoding (PNG/JPEG) needs a real image library; stdlib cannot do
it (the repo's stdlib-only PNG helper is test-fixture-scoped). Add
`Pillow>=10` to `src/runtime` `dependencies`. Provisioning already runs
`uv tool install --force <repo>/src/runtime` on every bootstrap
(`src/provisioning/ansible/roles/cli_tools/tasks/main.yml:100-105`) with
`UV_TOOL_BIN_DIR` pinned, plus a `dotfiles-runtime` resolve check — so the
new dep is installed and verified with **zero role changes**. No system
package (NFR-3 distro isolation untouched), no container image (`itr` and
`dotfiles-runtime` are host-local; `cli_tools_image_builds` stays `[csg]`),
no `packages.yaml` / `assets.yaml` / `filesystem.yaml` change. This keeps
the invariant **provisioning installs, runtime executes**: the guard code
never installs anything; it only imports PIL at use-site with a clean
`MissingDerivationInputError`-style fallback to the palette proxy if the
import ever fails.

### D5. Scope guard: bar-group allowlist + placeholder allowlist

Groups: `battery`, `network`, `btop`, `thunderbird`, `tray`, `ui`,
`power-menu`, `email-client`, `wallpaper-selector` (config-overridable, not
hardcoded elsewhere). Placeholders: `COLOR_FOREGROUND`, `COLOR_JOIN` only.
Literals (`#…`), variant-level overrides, and non-bar groups are never
rewritten. Threshold + allowlists are overridable via
`RUNTIME__ICON_CONTRAST__*` env / settings plumbing (follow existing
`config-assembler-engine` conventions); defaults: threshold `4.5`.

### D6. Cache key = effective mappings hash

`m_h` becomes `hash(overlay)` (file → `hash_file`, dir →
`canonical_hash_dir`), keeping `ih = sha256(peh || t_h || m_h)` valid.
Overlay construction is deterministic (sorted keys, fixed serialization), so
identical inputs hit the same entry. `meta.json` gains an additive
`contrast: {backdrop_source, threshold, decisions[{group, placeholder,
from, to, ratio_before, ratio_after}]}` field — additive only, no schema
migration.

### D7. WCAG 2.1 math, palette-resident candidates

Relative luminance via sRGB linearization; ratio `(L1+0.05)/(L2+0.05)`.
Candidate set = palette keys ∩
`{foreground, background, cursor, color0..color15}` (ordered by ratio desc,
ties → keep original). If the best candidate still misses the threshold,
pick it anyway (best effort) and log. Never synthesize hex.
