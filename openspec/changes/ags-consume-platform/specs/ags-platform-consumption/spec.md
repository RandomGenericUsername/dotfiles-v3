# ags-platform-consumption (delta)

## ADDED Requirements

### Requirement: The framework is installed as one versioned unit

The provisioning pipeline SHALL install the AGS platform as a single versioned unit under `<install>/ags-platform/<version>/` and SHALL NOT enumerate its files individually. The unit's version SHALL be recorded so it can be rolled back by repointing the shortcut.

Source: spine **AD-17**.

#### Scenario: one unit, one version

- **WHEN** provisioning installs the framework
- **THEN** the files land under `<install>/ags-platform/<version>/`
- **AND** the pinned version is recorded

### Requirement: Every app resolves the framework by a bare specifier

The bar and every app SHALL resolve the platform through a shared-ancestor `node_modules` shortcut on their resolution path, so `config/ags` and every `config/ags-*` find it without a per-app copy.

Source: spine **AD-17**.

#### Scenario: apps resolve the shared ancestor

- **GIVEN** the framework is installed and the shortcut created
- **WHEN** `ags run` starts the bar or any app
- **THEN** the platform bare specifier resolves
- **AND** no app config dir carries its own framework copy

### Requirement: Retired per-file copies are removed

Switching to the one-unit install SHALL remove the previously placed per-file framework copies, so a fresh provision does not leave stale modules.

Source: spine **AD-17**.

#### Scenario: no stale copies remain

- **WHEN** the install completes
- **THEN** the previously enumerated framework files are gone
- **AND** `verify` passes on a fresh host
