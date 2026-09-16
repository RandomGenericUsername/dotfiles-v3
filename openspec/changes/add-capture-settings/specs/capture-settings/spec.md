## Purpose

A settings surface for the capture tool matching the approved mockup, backed by a GUI-owned config file the backend consumes for defaults — with explicit precedence and safe fallbacks throughout.

## ADDED Requirements

### Requirement: Settings view and navigation

The capture window SHALL offer a settings view with General / Screenshot / Recording groups matching `spikes/capture-tool-ui/settings.html` (path rows, toggles, compact segmented pills), reachable via a footer entry point and exited via back affordance or `Escape` (which returns to the mode view, not out of the window).

#### Scenario: Round trip
- **WHEN** the user opens settings, changes the screenshot folder, saves, and presses `Escape`
- **THEN** the mode view returns with prior selections intact and the new folder applies to the next save

### Requirement: Config file contract

Settings SHALL persist to `$XDG_CONFIG_HOME/capture-tool/config.json` per the design schema; missing file, missing keys, and corrupt JSON SHALL all degrade to defaults without crashing, and directories SHALL be created on save.

#### Scenario: First run
- **WHEN** no config file exists
- **THEN** the view shows the design defaults and saving creates the file plus both directories

#### Scenario: Corrupt config
- **WHEN** the config file is not valid JSON
- **THEN** the app runs on defaults, logs loudly, and overwrites cleanly on next save

### Requirement: Precedence

Explicit CLI args SHALL beat config values; last-used UI state SHALL beat settings defaults for initial selections; the notifications toggle SHALL gate all backend emission.

#### Scenario: Explicit output wins
- **WHEN** `--output /tmp/x.png` is passed with a configured screenshot dir
- **THEN** the file lands at `/tmp/x.png`

#### Scenario: Notifications off is silent
- **WHEN** the toggle is `false`
- **THEN** no `Notify` request is emitted for success or failure paths

### Requirement: Backend consumption

The backend SHALL derive default save paths from config dirs + pattern, support `--cursor` for screenshot and recording (recorder flags verified on-machine, outcomes recorded), and report the detected backend for the read-only row.

#### Scenario: Pattern paths
- **WHEN** pattern is `{kind}_%Y-%m-%d_%H-%M-%S` with the recording dir set
- **THEN** the default recording path matches `<dir>/recording_<date>_<time>.mp4`

#### Scenario: Backend readout
- **WHEN** the settings view renders
- **THEN** the backend row shows `Automatic (<detected-name>)` and offers no selection control

#### Verified backend cursor flags (on-machine)
- `grim -h` documents `-c` ("Include cursors in the screenshot") — `--cursor` maps to `grim -c`.
- `gpu-screen-recorder -h` documents `-cursor yes|no` — `--cursor` maps to `-cursor yes` (and `-cursor no` when off).
- `wf-recorder --help` documents NO cursor option — `--cursor` is accepted by the launcher but cannot be honored on that backend (no flag emitted).
