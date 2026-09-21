## MODIFIED Requirements

### Requirement: AGS source deployment

The compositor config provision SHALL deploy every AGS source file, including
the panel-agnostic `services/` modules and the `components/` UI modules, and
SHALL NOT leave the superseded `settings-panel/services` directory in place.

#### Scenario: New layout deployed
- **WHEN** the compositor configs role converges
- **THEN** `config/ags/services/*`, `config/ags/components/**`, and the settings
  panel sources are present in the install spine

#### Scenario: Legacy directory removed
- **WHEN** the compositor configs role converges on a machine that still has the
  old `config/ags/settings-panel/services` directory
- **THEN** that directory is removed

#### Scenario: Verify gates the new files
- **WHEN** `verify` runs
- **THEN** it asserts the `services/` and `components/` files exist and no longer
  asserts the removed `settings-panel/services` paths
