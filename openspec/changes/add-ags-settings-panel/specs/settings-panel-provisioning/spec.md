## Purpose

All setup for the settings panel — packages, GObject-Introspection bindings,
the BlueZ service, backlight permission, AGS source deployment, and icon
rendering — performed by the provisioning process, with verify asserting each
outcome. The runtime only executes against what provisioning delivered.

## ADDED Requirements

### Requirement: Astal bindings installed by provisioning

Provisioning SHALL install the Astal Bluetooth and WirePlumber bindings (along
with the already-present Astal network/battery/hyprland set and `brightnessctl`,
`wireplumber`, `networkmanager`, `hyprmod`), resolved through the per-manager
package maps, and SHALL NOT rely on the runtime to obtain them.

#### Scenario: Bindings resolved from the package maps
- **WHEN** the packages role converges
- **THEN** the Astal Bluetooth and Wp packages are installed via the same channel
  (pacman/AUR) as the rest of the Astal set

#### Scenario: Namespaces importable
- **WHEN** `verify` runs
- **THEN** it fails if the `AstalBluetooth` or `AstalWp` GIR namespace does not
  resolve on the machine

### Requirement: BlueZ service provisioned

Provisioning SHALL install `bluez`/`bluez-utils` and enable + start
`bluetooth.service`, so Bluetooth devices are available to the panel without any
runtime action.

#### Scenario: Service enabled
- **WHEN** provisioning converges
- **THEN** `systemctl is-enabled bluetooth` reports enabled and the service is
  running

#### Scenario: Verify pins the service
- **WHEN** the `verify` role runs
- **THEN** it fails if `bluetooth.service` is not enabled

### Requirement: Backlight control permission

Provisioning SHALL ensure the user can change display brightness with the
provisioned `brightnessctl` (udev rule from the package, and adding the user to
the `video` group if the ACL does not otherwise apply), so the Display slider is
never a silent no-op.

#### Scenario: User can set brightness
- **WHEN** provisioning converges
- **THEN** `brightnessctl set <pct>%` succeeds as the user without elevation

### Requirement: AGS sources deployed by provisioning

Provisioning SHALL deploy every new AGS source file for the panel (window,
state, primitives, controls, views, and the bar settings widget) into the config
spine via the explicit per-file entries, creating the new `settings-panel/`
config directories, and SHALL regenerate `icons.json` from `icons.yaml`.

#### Scenario: Files present in the spine
- **WHEN** the `compositor_configs` role converges
- **THEN** every panel source file exists under the config-in-spine `ags/` tree

#### Scenario: Manifest regenerated
- **WHEN** `icons.yaml` contains the new groups
- **THEN** the generated `ags/icons.json` includes `settings`, `settings-panel`,
  `volume`, and the `ui` brightness variant

#### Scenario: Verify pins the files
- **WHEN** the `verify` role runs
- **THEN** it fails if any required panel file, the regenerated manifest, or the
  new icon samples are missing

### Requirement: No new always-on instance

The panel SHALL live in the existing always-on bar AGS instance; provisioning
SHALL NOT add an autostart entry or an always-on instance for it.

#### Scenario: Instance list unchanged
- **WHEN** the always-on AGS instance set is inspected
- **THEN** it is still just the status bar instance

#### Scenario: Runtime does no setup
- **WHEN** the AGS process starts
- **THEN** it loads the panel from deployed sources and performs no installation,
  download, service enablement, or permission change
