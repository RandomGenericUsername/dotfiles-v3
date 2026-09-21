## MODIFIED Requirements

### Requirement: Wi-Fi scan provisioning

The provision SHALL NOT install `iw` or grant it network capabilities. Wi-Fi
list freshness SHALL be delivered at runtime by NetworkManager's own D-Bus
access-point data and scan requests; no external scan utility is provisioned or
granted capabilities for the settings panel.

#### Scenario: iw not provisioned
- **WHEN** the packages playbook converges
- **THEN** `iw` is not installed by the manifest and carries no granted
  capabilities as a result of provisioning

#### Scenario: No capability grant tasks remain
- **WHEN** the packages role is inspected
- **THEN** it contains no `setcap`/`getcap` task for `iw`

#### Scenario: Verify gate reflects the removal
- **WHEN** `verify` runs
- **THEN** it asserts only NetworkManager/BlueZ-provisioned capabilities and
  contains no `iw` package or capability assertion

## REMOVED Requirements

### Requirement: Provisioned iw scan capability

**Reason**: introduced solely for a workaround Wi-Fi scan path; the panel now
uses NetworkManager D-Bus and the external scan utility is unnecessary.

**Migration**: no user action. `iw` may remain installed on machines that
already have it; it is simply no longer part of the provision or verify gate.
