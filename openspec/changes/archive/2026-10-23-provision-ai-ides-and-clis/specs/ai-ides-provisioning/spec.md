## ADDED Requirements

### Requirement: packages manifest declares the AI IDEs and CLIs
`dotfiles/provisioning/packages.yaml` SHALL list the logical entries
`antigravity-ide`, `windsurf`, `vscode`, `copilot-cli`, and `codex-cli`, and the
manifest-reader test's expected package set SHALL match.

#### Scenario: manifest lists the five tools
- **WHEN** `packages.yaml` is inspected
- **THEN** it contains entries named `antigravity-ide`, `windsurf`, `vscode`, `copilot-cli`, `codex-cli`
- **AND** the manifest-reader expected set contains all five

### Requirement: Arch group_vars resolve each logical tool to its AUR package
The `packages` map in `group_vars/arch.yml` SHALL map `antigravity-ide →
antigravity-ide`, `windsurf → devin-desktop`, `vscode →
visual-studio-code-bin`, `copilot-cli → github-copilot-cli`, and `codex-cli →
openai-codex-bin`.

#### Scenario: arch map resolves the tools
- **WHEN** the Arch group_vars are loaded
- **THEN** `packages.windsurf == "devin-desktop"` and `packages.vscode == "visual-studio-code-bin"`
- **AND** `packages["copilot-cli"] == "github-copilot-cli"` and `packages["codex-cli"] == "openai-codex-bin"`
- **AND** `packages["antigravity-ide"] == "antigravity-ide"`

#### Scenario: the tools are Arch-only
- **WHEN** the Debian-family group_vars are loaded
- **THEN** none of the five logical keys is present

### Requirement: the AUR channel routes the five packages
`roles/packages/vars/arch.yml` `aur_packages` SHALL include `antigravity-ide`,
`devin-desktop`, `visual-studio-code-bin`, `github-copilot-cli`, and
`openai-codex-bin`, so the packages role subtracts them from the pacman list and
installs them via yay.

#### Scenario: AUR channel includes the tools
- **WHEN** `aur_packages` is inspected
- **THEN** it contains all five package names
- **AND** `test_every_manifest_entry_is_reachable_from_a_provisioning_path` passes

### Requirement: the IDEs are rofi-launchable with Wayland flags
The compositor_configs role SHALL place repo-authoritative user overrides for
`antigravity-ide.desktop`, `code.desktop`, and `devin-desktop.desktop` into
`$XDG_DATA_HOME/applications/`, each carrying
`--ozone-platform-hint=auto` and the combined
`UseOzonePlatform,WaylandWindowDecorations` feature flag, so rofi's drun mode
launches them Wayland-native and shadows the packaged entries.

#### Scenario: overrides are registered and placed
- **WHEN** `compositor_configs_desktop_entries` is inspected
- **THEN** it contains one entry per IDE with a `dotfiles/applications/…` source and a `$XDG_DATA_HOME/applications/…` dest
- **AND** the placement task copies with `force: true`

#### Scenario: each override carries the Wayland flags
- **WHEN** each IDE `.desktop` override is read
- **THEN** its `Exec=` contains `--ozone-platform-hint=auto`
- **AND** its `Exec=` contains `UseOzonePlatform,WaylandWindowDecorations`

### Requirement: the two CLIs are rofi-launchable via kitty
The compositor_configs role SHALL place `copilot.desktop` and `codex.desktop`
overrides whose `Exec` runs `kitty` with the CLI and whose `Terminal` is
`false`, so both CLIs appear in rofi's drun mode.

#### Scenario: CLI launchers are registered and placed
- **WHEN** `compositor_configs_desktop_entries` is inspected
- **THEN** it contains `copilot.desktop` and `codex.desktop` entries
- **AND** each file's `Exec=` starts with `kitty`
- **AND** each file sets `Terminal=false`

### Requirement: one Codex resolves on PATH
The cli_tools role SHALL remove the standalone Codex shadow at
`{{ cli_tools_bin_dir }}/codex` **only** when it is a symlink into
`.codex/packages/standalone`, and SHALL remove the `~/.codex/packages` payload,
so the AUR `/usr/bin/codex` is the single resolved binary. User Codex config and
auth under `~/.codex` SHALL be preserved.

#### Scenario: standalone shadow is removed, user files preserved
- **WHEN** `~/.local/bin/codex` is a symlink into `~/.codex/packages/standalone/…`
- **THEN** the role removes the symlink and the `~/.codex/packages` dir
- **AND** it does not remove `~/.codex/config.toml` or auth
- **AND** the removals are skipped under `--check`

#### Scenario: a non-standalone codex is left alone
- **WHEN** `~/.local/bin/codex` is a regular file or links elsewhere
- **THEN** the role leaves it untouched

### Requirement: verify gates the five binaries
`verify_system_binaries` SHALL include `antigravity-ide`, `code`,
`devin-desktop`, `copilot`, and `codex`, so a missing install fails the
provision (criterion-2 PATH gate).

#### Scenario: binaries are gated
- **WHEN** the verify role runs
- **THEN** `command -v` is checked for all five
- **AND** the exact-list structural test includes them
