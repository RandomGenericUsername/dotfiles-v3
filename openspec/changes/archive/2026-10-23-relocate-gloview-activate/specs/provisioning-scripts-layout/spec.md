## ADDED Requirements

### Requirement: Provisioning scripts location
The repository SHALL keep provisioning-owned helper scripts under `dotfiles/provisioning/scripts/`, with `gloview-activate` as the first entry.

#### Scenario: Helper resolves at new path
- **WHEN** inspecting the repo tree
- **THEN** `dotfiles/provisioning/scripts/gloview-activate` exists, is executable, and `scripts/gloview-activate` does not exist

### Requirement: Installed helper contract unchanged
The `cli_tools` role SHALL install `dotfiles/provisioning/scripts/gloview-activate` to `{{ cli_tools_bin_dir }}/gloview-activate` with mode `0755`.

#### Scenario: Provisioning copies from new source
- **WHEN** the `cli_tools` role runs (or dry-runs)
- **THEN** the user bin contains an executable `gloview-activate` identical in behavior to before the move
