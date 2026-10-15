# Spec Delta

## Purpose

`btop-theme-deployment` ships authored btop themes from the repo into the install spine and selects the active theme, so authored themes reach btop and the active selection survives re-provisioning.

## ADDED Requirements

### Requirement: Ship authored themes into the spine

Provisioning SHALL place authored `.theme` files from the repo into the install-spine themes directory that btop scans, without disturbing the generated theme's runtime pointer.

#### Scenario: authored theme reaches btop
- **WHEN** provisioning runs after an authored theme is added to the repo
- **THEN** the theme file is present in the spine themes directory and btop discovers it by filename

#### Scenario: generated pointer is not disturbed
- **WHEN** provisioning ships authored themes
- **THEN** the generated `colors.btop.theme` consumer pointer remains a runtime-owned pointer into `current/`

### Requirement: Active theme is a repo-owned setting that survives re-provisioning

The active `color_theme` SHALL be selected from a repo-owned setting rendered into `btop.conf`, and re-provisioning SHALL preserve the selection; `save_config_on_exit` SHALL remain `false`.

#### Scenario: selection persists across provisioning
- **WHEN** provisioning re-renders `btop.conf`
- **THEN** `color_theme` reflects the repo setting and `save_config_on_exit` is `false`

#### Scenario: btop does not rewrite the managed config
- **WHEN** btop exits
- **THEN** the provisioning-owned `btop.conf` is unchanged
