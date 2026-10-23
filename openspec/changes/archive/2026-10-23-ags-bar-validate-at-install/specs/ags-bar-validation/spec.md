# ags-bar-validation (delta)

## ADDED Requirements

### Requirement: The manifest is pure data

The bar SHALL declare its capabilities, params, and icon groups in a pure `bar-manifest` module or artifact that carries no GJS dependency, so both the bar and the validator consume the same declarations.

Source: spine **AD-14**.

#### Scenario: manifest imports without a desktop runtime

- **WHEN** the manifest is imported by a non-GJS runtime
- **THEN** it requires no `ags`, GTK, Gio, or Astal

### Requirement: One rule set, two enforcements

`validateLayout` and `validateIcons` SHALL be the shared functions. Provisioning SHALL run both and fail the install on any error; the bar SHALL run the same functions at startup and degrade. `unknown-param`, `duplicate-widget` (unless the capability declares `multi: true`), and `missing-icon-key` (only for groups declaring `states`) SHALL be errors.

Source: spine **AD-15**.

#### Scenario: install fails on a bad layout

- **GIVEN** a layout naming an unknown widget or a typo'd param
- **WHEN** provisioning runs the validator
- **THEN** the install fails with the `BarIssue` naming the widget/param

#### Scenario: the bar degrades instead of crashing

- **GIVEN** the same bad layout at runtime
- **WHEN** the bar starts
- **THEN** it skips the unknown widget, applies defaults, and blanks a missing glyph
- **AND** it does not crash

### Requirement: Artifacts are versioned per artifact

Each runtime artifact (`icons.json`, optional `bar.json`, `colors.gtk.css`) SHALL carry its own `schemaVersion`. An unknown version SHALL warn and degrade, never crash. A `BarLayout` SHALL NOT carry a separate version field.

Source: spine **AD-9**, **AD-16**.

#### Scenario: unknown version degrades

- **WHEN** an artifact carries an unrecognised `schemaVersion`
- **THEN** the bar warns and runs with a degraded artifact
