## ADDED Requirements

### Requirement: `KittyReloader` reloads kitty so all open windows re-theme
A `KittyReloader` implementing `IDesktopReloader` SHALL, on each reload, signal
every running kitty process with `SIGUSR1` so kitty reloads its config (which
includes the runtime palette at `current/colors.kitty`). It SHALL NOT write OSC
to other terminals' ptys and SHALL NOT poll.

#### Scenario: open kitty windows adopt the new palette
- **GIVEN** one or more kitty processes are running
- **WHEN** a swap/reconcile runs the reloader list
- **THEN** each kitty process receives `SIGUSR1`
- **AND** the reloader returns `True`

#### Scenario: no kitty running is a vacuous success
- **GIVEN** no kitty process is running
- **WHEN** the reloader runs
- **THEN** it returns `True` (a terminal may legitimately not be open)

#### Scenario: a failed signal is surfaced
- **GIVEN** a kitty process exists
- **AND** signalling it raises `OSError` (e.g. permission)
- **WHEN** the reloader runs
- **THEN** it returns `False`
- **AND** `KittyReloader` appears in `ReconcileResult.reload_failures` (R5)

### Requirement: `TerminalColorApplier` is not run by the daemon
The daemon SHALL NOT include `TerminalColorApplier` in its reloader list, because
it has no controlling terminal; the `/dev/tty` OSC applier SHALL remain wired for
CLI `wallpaper set`/`reconcile` (which may run inside a terminal). `KittyReloader`
SHALL be present in both lists.

#### Scenario: daemon converge has no tty failure
- **GIVEN** a daemon-initiated converge
- **WHEN** the reloader list runs
- **THEN** `TerminalColorApplier` is not invoked
- **AND** no `/dev/tty` failure is logged

#### Scenario: CLI reconcile still applies OSC to the invoking terminal
- **GIVEN** a user runs `reconcile`/`wallpaper set` from a terminal
- **WHEN** the reloader list runs
- **THEN** `TerminalColorApplier` is invoked and its success/failure follows the existing R5 semantics
