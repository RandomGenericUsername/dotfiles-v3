## ADDED Requirements

### Requirement: Provisioning ships a btop configuration that selects a generated theme
A `btop_config` provisioning role SHALL render `<install>/config/btop/btop.conf`
containing `color_theme` set to `csg-minimal.theme`, and SHALL set
`save_config_on_exit = false`. All other btop settings SHALL remain at btop's own
defaults.

The role SHALL create `<install>/config/btop/` and `<install>/config/btop/themes/`,
and `config_links` SHALL link `~/.config/btop` to `<install>/config/btop`, so btop
reads its configuration and themes at their native XDG locations.

#### Scenario: the rendered config selects the minimal theme
- **GIVEN** a provisioned machine
- **WHEN** `<install>/config/btop/btop.conf` is read
- **THEN** it contains `color_theme` with the value `csg-minimal.theme`

#### Scenario: btop will not overwrite the provisioned config
- **GIVEN** the rendered `btop.conf`
- **WHEN** `save_config_on_exit` is read
- **THEN** it is `false`
- **AND** btop exits without truncating and rewriting the file

#### Scenario: other settings are untouched
- **GIVEN** the rendered `btop.conf`
- **WHEN** it is compared to btop's own defaults
- **THEN** every setting other than `color_theme` and `save_config_on_exit`
  equals btop's default

#### Scenario: the native config location resolves into the spine
- **GIVEN** a provisioned machine
- **WHEN** `~/.config/btop/btop.conf` is resolved
- **THEN** it resolves to `<install>/config/btop/btop.conf`

### Requirement: All three generated themes are discoverable by btop
The runtime SHALL place `colors.btop-minimal.theme`, `colors.btop-balanced.theme`,
and `colors.btop-full.theme` into `<install>/config/btop/themes/` as consumer
pointers at `current/`, so all three are listed in btop's theme menu and selectable
by `color_theme`.

The destination parent directory SHALL be created by provisioning, because the
seeder skips a pointer whose parent is missing and never creates directories inside
the install spine.

#### Scenario: all three themes appear in the menu
- **GIVEN** a completed palette swap on a provisioned machine
- **WHEN** `<install>/config/btop/themes/` is listed
- **THEN** it contains `colors.btop-minimal.theme`, `colors.btop-balanced.theme`,
  and `colors.btop-full.theme`

#### Scenario: the theme files are reachable through the symlink chain
- **GIVEN** a listed theme file in `<install>/config/btop/themes/`
- **WHEN** it is resolved
- **THEN** it resolves to a file inside a palette cache entry
- **AND** the file is readable and ends with the `.theme` extension

#### Scenario: selecting a theme by stem works
- **GIVEN** `color_theme` set to `csg-balanced.theme`
- **WHEN** btop resolves the theme
- **THEN** it matches the discovered entry by filename and applies it
- **AND** it does not fall back to the built-in `Default` theme

#### Scenario: the themes directory always exists before the first swap
- **GIVEN** a freshly provisioned machine on which no palette swap has run
- **WHEN** `<install>/config/btop/themes/` is checked
- **THEN** the directory exists
- **AND** the first swap is not skipped for a missing parent

### Requirement: A wallpaper change reaches btop on its next launch
A palette swap SHALL update all three theme files in place, so that the next btop
launch reflects the current wallpaper. Provisioning SHALL NOT terminate or relaunch
a running btop.

#### Scenario: a swap updates the themes in place
- **GIVEN** a running btop displaying `csg-minimal.theme`
- **WHEN** the wallpaper changes
- **THEN** all three theme files reflect the new palette
- **AND** the running btop is left undisturbed

#### Scenario: the next launch picks up the new palette
- **GIVEN** a completed wallpaper change
- **WHEN** btop is launched
- **THEN** it applies the current `color_theme` from the updated theme file

### Requirement: Provisioning preserves any pre-existing btop config directory
`config_links` SHALL apply its existing migrate-then-backup guard to `btop`: a
pre-existing `~/.config/btop` that is not already the managed spine symlink SHALL
be moved aside to a timestamped backup before the symlink is created, and never
deleted.

#### Scenario: a real directory is preserved, not deleted
- **GIVEN** `~/.config/btop` exists as a real directory before provisioning
- **WHEN** `config_links` runs
- **THEN** it is moved aside to a timestamped path under the backup root
- **AND** `~/.config/btop` becomes the managed spine symlink
- **AND** the original content remains readable at the backup path

#### Scenario: re-running is idempotent
- **GIVEN** `~/.config/btop` already points at the spine
- **WHEN** `config_links` runs again
- **THEN** nothing is moved and no backup is created

### Requirement: Provisioning verifies the btop integration
`verify` SHALL assert that the rendered `btop.conf` exists, that it selects
`csg-minimal.theme`, that `save_config_on_exit` is `false`, that
`<install>/config/btop/themes/` exists, and that all three theme files are present.
The `btop` package SHALL be present in the manifest, and `btop` SHALL appear in
both `config_links_managed_dirs` and `verify_managed_link_dirs`.

#### Scenario: verify catches a missing config
- **GIVEN** `<install>/config/btop/btop.conf` is absent
- **WHEN** `verify` runs
- **THEN** verification fails with a message naming the missing file

#### Scenario: verify catches a wrong theme selection
- **GIVEN** a `btop.conf` whose `color_theme` is not `csg-minimal.theme`
- **WHEN** `verify` runs
- **THEN** verification fails

#### Scenario: the managed-dir lists stay in parity
- **GIVEN** `btop` added to `config_links_managed_dirs`
- **WHEN** the parity test compares it with `verify_managed_link_dirs`
- **THEN** both lists contain `btop` and the comparison passes
