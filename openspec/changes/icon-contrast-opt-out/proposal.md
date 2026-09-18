## Why

The icon-contrast guard (`add-icon-contrast-guard`) currently runs
unconditionally on every derivation. Some wallpapers look better with the
authored mappings, and the user wants per-wallpaper control from the GUI —
so the guard must become optional with a persistent per-wallpaper choice,
while staying scriptable from the CLI.

## What Changes

- New machine-local preference store in XDG state
  (`$XDG_STATE_HOME/dotfiles/icon-contrast.json`): wallpaper content-hash →
  explicit `true`/`false`. Absent entry = **default ON** (decided: the
  just-shipped fix stays active everywhere unless opted out).
- `wallpaper set` gains a tri-state `--contrast {auto,on,off}` (default
  `auto`): `on`/`off` force the guard for this run (and persist the choice
  for the wallpaper hash); `auto` follows the store, falling back to
  default-ON. Stored as `contrast` alongside the icons entry decisions so
  `inspect` can explain which policy rendered the current icons.
- New `dotfiles-runtime icons regenerate [--contrast {auto,on,off}]`
  command: re-renders ONLY the icons layer from the **current** palette and
  reconverges (repoint + AGS reload), without touching wallpaper/palette/
  effects. This is the GUI's "toggle flipped on the live wallpaper" path —
  no full `wallpaper set` needed. History uses the existing
  `trigger="regenerate"`.
- New `dotfiles-runtime icons preference [HASH] [--set on|off]` accessor:
  the GUI's exclusive store interface (read resolved policy, persist a
  choice) — the GUI never writes the state file directly.
- Resolution precedence (highest first): explicit CLI flag > per-wallpaper
  store > default ON > graceful fallback (guard exception ⇒ spine mappings
  + warning, unchanged).

## Non-goals

- No GUI in this change (see `wallpaper-selector-contrast-toggle`, which
  consumes the store + `icons regenerate` as its backend).
- No change to the WCAG math, candidate set, allowlist, or overlay
  mechanics; no spine/config-tree writes (store is state-local, never
  provisioned).
- No migration: existing cache entries are untouched; the next derivation
  of a wallpaper re-evaluates under the resolved policy (keys unchanged —
  the guard output for a given policy is deterministic, so hits still hit).
