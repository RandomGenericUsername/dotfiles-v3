## ADDED Requirements

### Requirement: Bar icons meet a contrast threshold via a runtime overlay

The runtime SHALL evaluate, during `ensure_icons`, the WCAG 2.1 contrast
ratio of each allowlisted bar group's effective foreground color against the
bar backdrop, and when below threshold SHALL render icons from a staging-only
overlay `icons.yaml` with the placeholder retargeted to the highest-contrast
palette-resident token. The spine mappings file SHALL NOT be modified.

#### Scenario: light wallpaper flips bright icons to a dark token

- **GIVEN** a light wallpaper whose top-strip luminance makes `color15`
  contrast < 4.5:1 against the backdrop
- **WHEN** `wallpaper set <light.png>` derives icons
- **THEN** the overlay retargets `battery.COLOR_FOREGROUND` (and equivalents)
  to the max-ratio palette token
- **AND** rendered SVGs contain the picked hex and no `{{` remains

#### Scenario: dark wallpaper keeps existing mapping (no churn)

- **GIVEN** a dark wallpaper where `color15` already meets the threshold
- **WHEN** icons derive
- **THEN** the overlay is byte-identical in effect to the spine (no retarget)
- **AND** the icons cache entry matches the pre-guard entry for the same inputs

#### Scenario: guard failure degrades gracefully

- **GIVEN** wallpaper sampling throws (corrupt image) AND palette fallback works
- **WHEN** icons derive
- **THEN** derivation uses the palette-`background` backdrop and completes
- **AND** a warning is logged; `current.json` icons entry is still written
- **GIVEN** the whole guard throws unexpectedly
- **WHEN** icons derive
- **THEN** derivation falls back to the original spine mappings with a warning
  (icons layer never hard-fails `wallpaper set`)

### Requirement: Overlay scope is strictly bounded

Only group-level `COLOR_FOREGROUND` / `COLOR_JOIN` of allowlisted bar groups
(`battery`, `network`, `btop`, `thunderbird`, `tray`, `ui`, `power-menu`,
`email-client`, `wallpaper-selector`) SHALL be rewritten. Variant-level
`color_mappings`, literal `#rrggbb` values, `bar_mappings`, and all non-bar
groups SHALL be byte-preserved.

#### Scenario: accent variants untouched

- **GIVEN** `capture-tool` variants `camera-accent` (`COLOR_FOREGROUND: color6`)
  and `warning-caution` (`COLOR_FOREGROUND: color3`)
- **WHEN** the guard runs on any wallpaper
- **THEN** those variant mappings are unchanged in the overlay and output

### Requirement: Backdrop sampling prefers wallpaper pixels, falls back to palette

The backdrop luminance SHALL come from the wallpaper top band (~bar height)
when decodable, else from palette `background`. The chosen source SHALL be
recorded per derivation.

#### Scenario: sampled wins, fallback recorded

- **GIVEN** a decodable wallpaper
- **WHEN** icons derive
- **THEN** `meta.json` `contrast.backdrop_source == "sampled"`
- **GIVEN** an undecodable wallpaper input
- **WHEN** icons derive
- **THEN** `contrast.backdrop_source == "palette"` and derivation completes

### Requirement: Icons cache stays content-addressed on effective inputs

`icons_entry_hash` SHALL be computed over the **effective** (overlay)
mappings hash. Overlay serialization SHALL be deterministic (same inputs →
same bytes → same `ih`). Cache-hit behavior (entry-dir existence ⇒ no tool
invocation) SHALL be unchanged.

#### Scenario: same inputs hit cache, changed palette misses

- **GIVEN** two `wallpaper set` runs with identical wallpaper + templates +
  spine mappings
- **WHEN** the second runs
- **THEN** it reports `cache_hit_icons == True` with zero `itr` invocations
- **GIVEN** a palette change that flips a contrast decision
- **WHEN** icons derive
- **THEN** a new `ih` entry is populated (no stale icons served)

### Requirement: Dependency is provisioned, runtime only executes

`Pillow` SHALL be declared in `src/runtime/pyproject.toml` `dependencies`
and installed exclusively via the existing provisioning `cli_tools` role
(`uv tool install --force src/runtime`); no new Ansible role, system
package, or container image SHALL be introduced. The guard SHALL import PIL
at use-site and fall back to the palette backdrop (then to spine mappings)
if the import fails, never attempting installation at runtime.

#### Scenario: fresh machine gets the dependency from bootstrap

- **GIVEN** a fresh checkout with the `Pillow` dep declared
- **WHEN** `./bootstrap.sh` (→ `cli_tools` role) completes
- **THEN** `dotfiles-runtime` resolves on PATH and `python -c "import PIL"`
  in its tool env succeeds

#### Scenario: runtime never installs at runtime

- **GIVEN** a host where PIL import fails inside the runtime tool env
- **WHEN** `wallpaper set` runs
- **THEN** icons still derive (palette-backdrop path) with a warning, and no
  `pip install` / `uv` subprocess is spawned by the runtime
