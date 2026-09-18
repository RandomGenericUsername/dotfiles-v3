## Context

The guard lives in `DerivationPipeline.ensure_icons` (`runtime/application/
derive.py`): it reads the palette entry + cached wallpaper bytes, samples
the top strip (PIL, use-site import), picks max-contrast palette-resident
tokens for allowlisted bar groups below threshold 4.5, and renders from a
staging overlay (spine read-only; overlay carries the `defaults.yaml`
sibling — see `add-icon-contrast-guard` D2 amendment). Policy inputs today:
`RUNTIME__ICON_CONTRAST__THRESHOLD/GROUPS/BAND_PX` env only; no per-wallpaper
memory, no CLI surface. The GUI shells `dotfiles-runtime wallpaper set
<img>` (`wallpaper-selector/lib/apply.ts`) with no flag threading.
`reconcile --regenerate-stale` already regenerates stale layers +
reconverges — the closest existing primitive to "icons only".

## Goals / Non-Goals

**Goals**

- Per-wallpaper choice persists across reboots and re-applies; default ON.
- CLI stays scriptable (explicit per-run override + persistence in one flag).
- GUI live-toggle path touches ONLY the icons layer (no wallpaper flicker,
  no palette/effects recompute).

**Non-Goals**

- See proposal. Additionally: no threshold-per-wallpaper (global env only);
  no store sync across machines (state-local by decision).

## Decisions

### D1. Store: `$XDG_STATE_HOME/dotfiles/icon-contrast.json`, `{wallpaper_hash: bool}`

Rationale (decided): personal, machine-local, survives reboots alongside
`current.json`/`history.jsonl`; never provisioned, never in the repo. Schema
`{"version": 1, "prefs": {<64-hex>: true|false}}`; absent file or absent key
= default ON.

### D1a. Hexagonal split: pure domain policy + adapter file store

The layering gate (`tests/architecture/test_layering.py`) bans `pathlib`
and I/O in `runtime/domain/` (established by the `icon_contrast_sampler`
fix). Therefore: `runtime/domain/icon_contrast_policy.py` holds ONLY pure
functions — `parse(text) -> prefs`, `serialize(prefs) -> text`,
`lookup(prefs, hash) -> bool | None`, `resolve(*, flag, stored, default=True)
-> (enabled, source)` (the D2 precedence table); `runtime/adapters/
icon_contrast_prefs_store.py` owns file I/O (read + atomic temp+rename
write, corrupt file ⇒ empty prefs + warning, never raises into the
pipeline). The pipeline maps `None → True` (default ON).

### D1b. `icons preference` accessor: the GUI's only store interface

`dotfiles-runtime icons preference [HASH] [--set on|off]`: without `--set`,
prints the resolved preference for HASH (default: live wallpaper hash from
`current.json`) as plain/`--format json` (`{hash, enabled, source}`); with
`--set`, persists and prints the result. The GUI shells this accessor
exclusively and never writes the state file directly (change C, D2). Read
path fails loud only on absent/corrupt state (mirrors `icons regenerate`);
a missing store file is NOT an error (means "all defaults").

### D2. Tri-state flag `--contrast {auto,on,off}`, default `auto`

Why a flag AND a store (req 2 recommendation): the flag is the scriptable
one-shot override; the store is the GUI's memory. Semantics: `on`/`off`
force the guard for this run AND persist the choice for the wallpaper hash
(single mechanism, no divergence between "run once" and "remember");
`auto` reads store → default ON. `wallpaper set` and `icons regenerate`
share the resolution helper (one function, two callers).

### D2a. Governing hash: variant inputs resolve to the parent wallpaper's pref

A variant set (`wallpaper set <cache/effects/.../variant>`, detected by the
existing `_is_weg_artifact` path check) has its OWN content hash, but the
user's choice lives on the parent wallpaper (the L2 checkbox is attributed
to the drilled wallpaper, req 3.2). Resolution therefore uses the
**governing wallpaper hash**: direct wallpaper input ⇒ `hash(img)`; WEG
artifact input ⇒ the effects entry's `source_wallpaper_hash` (read from the
effects cache meta, read-only); `icons regenerate` on a live variant ⇒ the
same lookup from the live effects entry. If the parent hash is unresolvable,
fall back to default ON and log (never fail the run). Both the store lookup
AND the `on`/`off` persistence target the governing hash, so a toggle made
in L2 for H governs H's original and all of H's variants.

### D3. `icons regenerate`: icons-only use case, current palette, full converge

New application use case `RegenerateIconsUseCase` (or a narrow method if
review prefers): load `current.json` (fail loud on absent/corrupt, like
apply's guard) → resolve policy for the governing live hash (D2a) → ensure
icons entry via `DerivationPipeline.ensure_icons` (same overlay path, so
results are identical to a full set's icons) → repoint icons symlinks +
consumer links → history append with the EXISTING closed-enum trigger
`regenerate` plus `details: {layers: {icons: 1}}` (both schema-valid today
per `history.schema.json` — no enum change) → reload AGS (and only AGS —
palette CSS/terminal/hyprpaper untouched) → emit `applying` at start and
`done`/`error` at finish on `wallpaper.state` (the GUI's busy gate keys on
the `applying` edge; no `visible` — pixels never change). Palette/effects
layers are never touched; wallpaper pixels never re-set (no flicker).
Gated by the same state mutex (busy error if a set is in flight — the GUI's
busy gate normally prevents this). Distinct from `reconcile
--regenerate-stale` (which reconverges ALL stale layers + full reloads):
this command is single-layer by construction.

### D4. `inspect` explains the policy

Icons entry `meta.json: contrast` gains `policy: {source:
"flag"|"store"|"default", enabled: bool}` next to `decisions` (additive).
`doctor`/`inspect` surface "icons rendered with guard ON (per-wallpaper
preference)" — the traceability the user asked for.

### D5. Cache keys unchanged

Policy does not enter `ih` (same policy + same inputs ⇒ same overlay bytes
⇒ same entry; different policy ⇒ different overlay ⇒ natural miss). No
migration, no invalidation change. A wallpaper whose stored pref flips
simply derives a new entry on next set/regenerate; the old entry prunes
normally.
