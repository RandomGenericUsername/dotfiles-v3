## ADDED Requirements

### Requirement: kitty is configured to read the runtime palette
Provisioning SHALL place a rendered kitty config at `<install>/config/kitty/kitty.conf`
and link `~/.config/kitty` to it. The config SHALL include the runtime palette at
the absolute path `<state_root>/dotfiles/current/colors.kitty` and SHALL include
an optional user file `local.conf`. `auto_reload_config` SHALL be set to a
negative number (`-1`), which disables automatic reload (kitty 0.48 types this
option as a float number of seconds; `no` is a parse error). The runtime signals
reloads explicitly via `SIGUSR1`.

#### Scenario: kitty reads the current palette
- **GIVEN** a provisioned machine
- **WHEN** kitty starts
- **THEN** `~/.config/kitty/kitty.conf` includes `<state>/dotfiles/current/colors.kitty`
- **AND** the window uses the palette colours from that artifact

#### Scenario: re-provisioning does not clobber user customisation
- **GIVEN** a user has edited `local.conf`
- **WHEN** provisioning runs again
- **THEN** `kitty.conf` is re-rendered
- **AND** `local.conf` is left unchanged

### Requirement: The render is machine-portable and fail-loud
The include path SHALL be derived at apply time from `ansible_facts.env`
(`XDG_STATE_HOME` default `~/.local/state`) and the validated
`{{ install_dir | trim }}`; the role SHALL NOT default `install_dir`, and a
missing `install_dir` SHALL fail before rendering.

#### Scenario: absolute path is rendered
- **WHEN** the role renders on a host with `HOME=/home/u` and no `XDG_STATE_HOME`
- **THEN** the include line is `include /home/u/.local/state/dotfiles/current/colors.kitty`

#### Scenario: install_dir is required
- **GIVEN** `install_dir` is undefined
- **WHEN** the role runs
- **THEN** it fails on the first assert before writing any file

### Requirement: Provisioning verifies the kitty config
`verify` SHALL assert that `~/.config/kitty` is linked, that `kitty.conf` exists,
and that it contains the runtime-palette include; the expected palette artifact
list SHALL include `colors.kitty`.

#### Scenario: verify catches a missing include
- **GIVEN** a machine where `kitty.conf` lacks the include line
- **WHEN** `verify` runs
- **THEN** it fails the kitty-config criterion
