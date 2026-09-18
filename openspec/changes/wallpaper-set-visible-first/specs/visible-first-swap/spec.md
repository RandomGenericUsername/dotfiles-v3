## ADDED Requirements

### Requirement: Wallpaper becomes visible before derivation completes

`wallpaper set` SHALL perform the visible swap (import → persist wallpaper
layer → repoint wallpaper symlinks → hyprpaper reload) BEFORE deriving
palette/effects/icons, then complete theming in the same process under the
same mutex.

#### Scenario: screen changes fast, theming follows

- **GIVEN** a wallpaper with cold caches (full derivation takes seconds)
- **WHEN** `wallpaper set <img>` runs
- **THEN** hyprpaper shows the new wallpaper before CSG/WEG/ITR complete
- **AND** a `visible` state is emitted between `applying` and `done`
- **AND** `done` arrives only after all consumers reloaded (or degraded per
  layer policy)

#### Scenario: intermediate state is schema-valid and crash-safe

- **GIVEN** the process is killed between `visible` and `done`
- **WHEN** the next `wallpaper set` / `reconcile` / `inspect` runs
- **THEN** `current.json` validates (wallpaper layer present, layers nullable)
- **AND** the desktop reconverges (missing layers derive, symlinks repoint)

### Requirement: `visible` event state is additive and documented

The `wallpaper.state` topic SHALL emit `state="visible"` with
`wallpaper_hash` after the swap. `done`/`error` semantics SHALL be unchanged
(`done` = pipeline finished, UI may unlock).

#### Scenario: old consumers ignore, new consumers react

- **GIVEN** a consumer built before this change
- **WHEN** it observes `visible`
- **THEN** it treats it as busy (no crash, no unlock)
- **GIVEN** the wallpaper selector
- **WHEN** it observes `visible`
- **THEN** Apply controls stay disabled and the status line may show
  "on screen — theming…"

### Requirement: Concurrent sets fail busy, never queue or preempt

A `wallpaper set` arriving while another set holds the state mutex SHALL
exit non-zero with a busy error without mutating state.

#### Scenario: double-click applies once

- **GIVEN** a set in flight (between `applying` and `done`)
- **WHEN** a second `wallpaper set` runs
- **THEN** it exits non-zero, emits no `visible`/`done`, and changes nothing

### Requirement: Post-visible layer failure keeps the wallpaper

If derivation fails after `visible`, the new wallpaper SHALL stay on screen
and the run SHALL report the degraded state (never revert pixels).

#### Scenario: palette backend down after swap

- **GIVEN** CSG fails after the swap succeeded
- **WHEN** the run completes
- **THEN** the exit is non-zero with a theming error, the event is `error`
  with the live `wallpaper_hash`, and `current.json` holds the new
  wallpaper with a null palette
