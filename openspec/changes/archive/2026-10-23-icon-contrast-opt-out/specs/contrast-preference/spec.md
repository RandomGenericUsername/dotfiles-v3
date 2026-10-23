## ADDED Requirements

### Requirement: Per-wallpaper preference store with default ON

The runtime SHALL persist explicit per-wallpaper contrast choices in
`$XDG_STATE_HOME/dotfiles/icon-contrast.json` (`{version: 1, prefs:
{<64-hex>: bool}}`, atomic writes). An absent file or absent key SHALL
resolve to enabled (default ON).

#### Scenario: first run of a wallpaper uses the guard

- **GIVEN** no store entry for wallpaper hash H
- **WHEN** icons derive for H
- **THEN** the guard evaluates (same behavior as today)

#### Scenario: stored opt-out is honored

- **GIVEN** `prefs[H] == false`
- **WHEN** icons derive for H in `auto` mode
- **THEN** the spine mappings render unchanged and `meta.json: contrast`
  records `policy.enabled == false`

### Requirement: Tri-state `--contrast` flag forces and persists

`wallpaper set` and `icons regenerate` SHALL accept
`--contrast {auto,on,off}` (default `auto`). `on`/`off` SHALL force the
guard for the run AND persist the choice for the wallpaper hash; `auto`
SHALL follow store → default ON.

#### Scenario: flag persists for next time

- **GIVEN** `wallpaper set <img> --contrast off`
- **WHEN** the run completes
- **THEN** `prefs[hash(img)] == false`
- **AND** a later bare `wallpaper set <img>` renders without the guard

#### Scenario: variant set honors the parent wallpaper's preference

- **GIVEN** `prefs[H] == false` for wallpaper H with variant V
- **WHEN** `wallpaper set <V>` runs in `auto` mode
- **THEN** the governing hash resolves to H (via the effects entry's
  `source_wallpaper_hash`) and icons render without the guard
- **AND** an explicit `--contrast on` persists `prefs[H] == true`
  (governing hash, never the variant's own hash)

### Requirement: `icons regenerate` re-renders only the icons layer

The runtime SHALL provide `icons regenerate [--contrast ...]` which loads
the live `current.json`, re-derives ONLY icons from the current palette
under the resolved policy, repoints icons links, appends history with
`trigger="regenerate"` and `details.layers={icons: 1}`, and reloads AGS —
without touching wallpaper/palette/effects or re-setting pixels. It SHALL
emit `applying` at start and `done`/`error` at finish on `wallpaper.state`
(never `visible`).

#### Scenario: live toggle flips icons without flicker

- **GIVEN** wallpaper H live with palette P and spine-rendered icons
- **WHEN** `icons regenerate --contrast on` runs
- **THEN** `current/icons/` holds guard-rendered SVGs from P, AGS shows
  them, and hyprpaper/palette CSS are untouched (no pixel change)
- **AND** `applying` then `done` were emitted (no `visible`)
- **AND** the history line carries `trigger="regenerate"`

### Requirement: `icons preference` accessor is the sole store interface

The runtime SHALL provide `icons preference [HASH] [--set on|off]`: show
prints the resolved `{hash, enabled, source}` (default HASH = live
wallpaper hash); `--set` persists and prints the result. A missing store
file SHALL NOT error (all defaults).

#### Scenario: GUI reads and writes through the accessor

- **GIVEN** no store entry for live wallpaper H
- **WHEN** `icons preference` runs
- **THEN** it prints `enabled=true, source=default` with exit 0
- **WHEN** `icons preference H --set off` runs
- **THEN** a later `icons preference H` prints `enabled=false,
  source=store`

#### Scenario: absent state fails loud

- **GIVEN** no `current.json` (or corrupt)
- **WHEN** `icons regenerate` runs
- **THEN** it exits non-zero without mutating cache, symlinks, or history

### Requirement: Policy is traceable in entry metadata

Icons entry `meta.json: contrast` SHALL include `policy: {source:
"flag"|"store"|"default", enabled: bool}` (additive; old entries without it
remain valid).

#### Scenario: inspect explains the rendering

- **GIVEN** current icons rendered with a stored opt-out
- **WHEN** `inspect`/`doctor` reports the icons layer
- **THEN** it states the guard was OFF via per-wallpaper preference
