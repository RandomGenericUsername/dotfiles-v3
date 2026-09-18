## ADDED Requirements

### Requirement: Checkbox and L1 swatch reflect and edit the wallpaper's preference

The selector SHALL show an "Auto high-contrast icons" checkbox attributed to
the focused wallpaper (L2 crumb header, primary) AND a CSS-drawn ◐ swatch on
each L1 card's hover toolbar that is BOTH indicator and control. Both SHALL
equal the resolved preference (store → default ON) at render time and
refresh on `done`/`error` rescans.

#### Scenario: checkbox matches stored preference

- **GIVEN** `prefs[H] == false` for the drilled wallpaper H
- **WHEN** L2 renders
- **THEN** the checkbox is unchecked with sublabel naming H's file

#### Scenario: L1 swatch toggles high-contrast in place

- **GIVEN** a card for wallpaper H whose resolved pref is ON
- **WHEN** the user clicks the card's ◐ swatch
- **THEN** the swatch flips to OFF immediately, `prefs[H] == false` is
  persisted, and — if H is live — `icons regenerate --contrast off` runs
  (icons-only, no pixel change)
- **AND** the L2 checkbox for H mirrors the new state

### Requirement: Live toggle regenerates icons only

Flipping the checkbox or the L1 swatch for the LIVE wallpaper/variant SHALL
persist the pref then run `icons regenerate` with the matching policy (no
wallpaper re-set, no pixel change). Flipping for a non-live wallpaper SHALL
persist only.

#### Scenario: hover-live toggle repaints the bar

- **GIVEN** wallpaper H live with spine-rendered icons
- **WHEN** the user clicks the swatch for H
- **THEN** pref H=true is stored and `icons regenerate --contrast on`
  completes, after which the bar shows guard-rendered icons

### Requirement: Applies honor the checkbox

L1 quick-Apply and L2 Apply pills SHALL persist the focused wallpaper's
checkbox state before invoking `wallpaper set` (which runs in `auto`),
so the set resolves identically with or without explicit flag threading.

#### Scenario: set-with-variant follows the box

- **GIVEN** L2 for wallpaper H with the box unchecked, applying variant V
- **WHEN** Apply runs
- **THEN** `prefs[H] == false` is stored before the set and the resulting
  icons render without the guard

### Requirement: Busy disables apply, never browse

While the last observed `wallpaper.state` is `applying` or `visible`, all
Apply controls SHALL be insensitive; grid, search, drill-down, and the
checkbox SHALL stay interactive. A checkbox flip on the live target during
busy SHALL save the pref and defer the regenerate until `done`/`error`,
with a status line noting the deferral.

#### Scenario: double-apply impossible, browse unaffected

- **GIVEN** a set in flight (`visible` observed)
- **WHEN** the user clicks an Apply pill and types in search
- **THEN** the pill does nothing (insensitive) and search filters normally

#### Scenario: locally initiated set collapses at `visible`

- **GIVEN** the user pressed Apply in the selector (local set in flight)
- **WHEN** the `visible` event arrives (pixels swapped, theming still running)
- **THEN** the selector window collapses immediately rather than waiting for
  `done`; the process keeps running and `done`/`error` still rescan + unlock
- **AND** a set NOT initiated by this instance never dismisses the window
