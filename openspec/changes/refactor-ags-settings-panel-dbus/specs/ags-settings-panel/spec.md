## MODIFIED Requirements

### Requirement: Wi-Fi connect feedback

The settings panel SHALL acknowledge a Wi-Fi connect press immediately, before
any network lookup completes, by showing an in-row spinner and a
"Connecting…" label for the target network. Progress SHALL be derived from
NetworkManager's device connection state, not from a fixed delay or watchdog.

#### Scenario: Spinner appears on the first frame
- **WHEN** the user presses Connect on a network
- **THEN** the row for that network shows a spinner and "Connecting…" without
  waiting for a profile lookup or any subprocess

#### Scenario: Progress reflects NetworkManager state
- **WHEN** NetworkManager reports the device in a preparing/configuring/
  ip-configuring state
- **THEN** the panel shows an active connecting state for the target

#### Scenario: Failure is surfaced
- **WHEN** NetworkManager reports the attempt failed
- **THEN** the panel clears the busy state and shows a human-readable reason

### Requirement: Wi-Fi network switching

The settings panel SHALL allow switching from the currently connected network
to another network without waiting for an unrelated attempt to finish. Pressing
Connect on a different network while another attempt is pending SHALL
re-target the attempt (cancel the previous target, deactivate the current
connection when needed, activate the new target) rather than being ignored.
Connect controls SHALL NOT be disabled en masse while an attempt is in flight.

#### Scenario: Switching between two known networks
- **WHEN** the user is connected to network A and presses Connect on network B
- **THEN** the panel deactivates A and activates B, completing promptly without
  a fixed multi-second lockout

#### Scenario: Re-target during a pending connect
- **WHEN** an attempt for network A is pending and the user presses Connect on
  network B
- **THEN** the attempt for A is cancelled and B becomes the active target, with
  its spinner shown

#### Scenario: No silent click drops
- **WHEN** the user presses any Connect control
- **THEN** the press always produces a visible state change or an error message

### Requirement: Wi-Fi password handling

The settings panel SHALL prompt for the password of a secured network that has
no saved profile, and SHALL also enter the password prompt when
NetworkManager reports that secrets are required for the attempt.

#### Scenario: Secured unsaved network prompts
- **WHEN** the user selects a secured network with no saved profile
- **THEN** the password prompt is shown for that network

#### Scenario: NetworkManager requires secrets
- **WHEN** an activation attempt returns a secrets-required result
- **THEN** the panel transitions to the password prompt for the target network

#### Scenario: Join feedback
- **WHEN** the user submits a password
- **THEN** the Join action shows a busy state and the outcome is reflected in
  the network list or an inline error

### Requirement: Wi-Fi list freshness

The Wi-Fi list SHALL be sourced from NetworkManager's access-point data and
refreshed when the Wi-Fi view is open. A network that is no longer present SHALL
disappear from the list without requiring an application restart.

#### Scenario: List sourced from NetworkManager
- **WHEN** the Wi-Fi view opens
- **THEN** the network list reflects NetworkManager's current access points and
  the connected network is identified from NetworkManager's active access point

#### Scenario: Vanished network drops
- **WHEN** an access point disappears from NetworkManager's data
- **THEN** the panel removes it from the list within a refresh cycle

### Requirement: Wi-Fi control uses provisioned services only

The Wi-Fi control path SHALL NOT shell out to external executables, and SHALL
NOT perform synchronous D-Bus calls on the user-interface thread. All
NetworkManager interaction SHALL be asynchronous D-Bus.

#### Scenario: No subprocess control path
- **WHEN** the AGS panel sources are inspected
- **THEN** the Wi-Fi control path contains no `nmcli`, `iw`, or other
  subprocess invocation

#### Scenario: No blocking bus calls
- **WHEN** the service layer is inspected
- **THEN** it performs no synchronous bus calls on the UI thread

### Requirement: Bluetooth control path

The Bluetooth control path SHALL use BlueZ D-Bus for power, discovery,
pairing, connection, and device listing, and SHALL surface a per-device busy
state for actions.

#### Scenario: No subprocess control path
- **WHEN** the AGS panel sources are inspected
- **THEN** the Bluetooth control path contains no `bluetoothctl` or `rfkill`
  subprocess invocation

#### Scenario: Action feedback
- **WHEN** the user pairs, connects, or disconnects a device
- **THEN** the device row shows a busy state until the action completes or
  fails visibly
