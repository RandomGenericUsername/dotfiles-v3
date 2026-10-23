## Why

The AGS bar is transparent (`dotfiles/config/ags/style.css` — `window#bar`
`background-color: transparent`, widgets render as bare floating icons). Icon
glyphs get their color from ITR (`icon-templates-renderer`) renders driven by
the runtime (`dotfiles-runtime wallpaper set` → `DerivationPipeline` →
`ItrAdapter` → `itr render`), using the generated palette
(`current/colors.yaml`: `background`/`foreground`/`cursor` + `color0..color15`).

Bar groups pin `COLOR_FOREGROUND → color15` (bright) in
`dotfiles/config/icon-template-color-scheme-mappings/icons.yaml` (`battery`,
`network`, `btop`, `thunderbird`, `tray`, `ui`, `power-menu`). On dark
wallpapers this reads well; on light wallpapers the icons wash out
(white-on-white — the reported bug). The existing `-gtk-icon-shadow` /
text-shadow depth is not enough.

ITR has no contrast awareness and its `icons.yaml` path is a positional CLI
arg with **no env override** (only `output.output_dir`, `templates.dir`,
`color_scheme.path` are env-overridable via `ICON_RENDERER__*`). So the fix
belongs in the runtime as a middleware step between palette derivation and
ITR rendering: evaluate WCAG contrast of the assigned icon color against the
bar backdrop and retarget bar-icon placeholders to the highest-contrast
palette token via an ephemeral overlay YAML passed to `itr render`.

## What Changes

- New pure runtime domain service `icon_contrast` (WCAG 2.1 relative
  luminance + contrast ratio, best-token selection from palette-resident
  candidates, bar-group allowlist, literal `#rrggbb` passthrough).
- `DerivationPipeline.ensure_icons` builds an **ephemeral overlay**
  `icons.yaml` (patched copy of the spine mappings, staging-only) retargeting
  only `COLOR_FOREGROUND` / `COLOR_JOIN` for bar groups below threshold, and
  passes the overlay path to `ItrAdapter.render`. Spine stays read-only
  (AD-11).
- Backdrop = sampled wallpaper top-strip luminance (bar height ~48px),
  fallback = palette `background` when sampling is unavailable.
- Icons cache key hashes the **effective** (overlay) mappings, not the spine
  file, so `cache/icons/<ih>/` stays content-addressed.
- New runtime dependency `Pillow` (image sampling) declared in
  `src/runtime/pyproject.toml`; installed by the existing provisioning
  `cli_tools` role via `uv tool install --force src/runtime` — no new role,
  no system package, no container image. Runtime-only-executes preserved:
  provisioning installs, runtime executes.
- Contrast decisions logged and persisted in icons `meta.json` (additive
  `contrast` field); surfaced via `doctor`/`inspect` wording only.

## Non-goals

- No ITR change (no `--auto-contrast` flag, no `icons.yaml` env override, no
  schema change); manual `itr render` behavior is unchanged.
- No repo `icons.yaml` / `defaults.yaml` edits; no `bar_mappings` changes.
- No AGS CSS scrim or shadow redesign (may be revisited separately).
- No new palette tokens invented — candidates are palette-resident only
  (never reference a missing key such as `surface` when CSG did not emit it).
- No change to palette/effects derivation, cache layout, or failure policy
  beyond the icons overlay (palette stays hard, icons stay graceful).
