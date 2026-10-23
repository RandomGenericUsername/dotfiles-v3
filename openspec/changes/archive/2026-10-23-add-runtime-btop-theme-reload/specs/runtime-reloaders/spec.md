## ADDED Requirements

### Requirement: A running btop adopts a new palette without restarting
The runtime SHALL send `SIGUSR2` to every running btop process after a
successful palette swap, and btop SHALL adopt the newly-repointed theme file
without being restarted, terminated, or relaunched.

`SIGUSR2` SHALL be used and `SIGUSR1`/`SIGWINCH` SHALL NOT: btop registers
`SIGUSR1` as an input-poll no-op and `SIGWINCH` as resize-only, so either would
make the adapter silently do nothing.

#### Scenario: an open btop re-themes on a palette swap
- **GIVEN** a btop process running with `color_theme` pointing at the consumer pointer
- **WHEN** a wallpaper change repoints that pointer to a new palette entry
- **THEN** the runtime sends `SIGUSR2` to that process
- **AND** btop paints the new theme's background colour without being restarted

#### Scenario: no btop running is a success
- **GIVEN** no btop process is running
- **WHEN** a palette swap occurs
- **THEN** the reload reports success
- **AND** no signal is sent

#### Scenario: an unreachable btop is a surfaced failure
- **GIVEN** a btop process exists but signalling it raises
- **WHEN** the reload runs
- **THEN** it reports failure
- **AND** the failure appears in the reconcile result's reload failures

#### Scenario: the reload runs after the pointer is repointed
- **GIVEN** the built reloader list
- **WHEN** its order is inspected
- **THEN** `BtopReloader` is last, after `KittyReloader`, so the consumer pointer
  is already repointed when btop re-reads it

### Requirement: The reload assertion can prove a negative
The verification of the live reload SHALL include a negative control in which the
theme file is replaced and **no** signal is sent, asserting the new colour is
ABSENT from the rendered frame. Without that control, the positive assertion
could be satisfied by a redraw or any other incidental change.

The verification SHALL additionally assert that a second `Loading theme file`
line is logged, proving `Theme::updateThemes()` and `Theme::setTheme()` ran
rather than only a repaint.

#### Scenario: no signal means no reload
- **GIVEN** a running btop whose theme file is replaced
- **WHEN** no signal is sent
- **THEN** the new background colour is absent from the frame
- **AND** the negative control assertion holds

#### Scenario: the reload is attributable to the reload path
- **GIVEN** a reload that made the new colour appear
- **WHEN** btop's log is inspected
- **THEN** it contains at least two `Loading theme file` lines

### Requirement: The adapter uses no shell and no pty
The reloader SHALL enumerate processes without invoking a shell and SHALL NOT
read or write any pseudo-terminal. Process enumeration SHALL degrade to "no
processes" on any spawn, timeout, or parse failure rather than surfacing a
failure.

#### Scenario: a missing pgrep is not a failure
- **GIVEN** `pgrep` is unavailable
- **WHEN** the default pid source runs
- **THEN** it returns no pids and the reload is vacuously successful