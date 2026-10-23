## ADDED Requirements

### Requirement: packages manifest lists rofi as the launcher
`dotfiles/provisioning/packages.yaml` SHALL list `rofi` (not `wofi`) as the application launcher, and the manifest-reader test's expected package set SHALL match.

#### Scenario: manifest is corrected
- **WHEN** `packages.yaml` is inspected
- **THEN** it contains a `rofi` entry with the launcher comment
- **AND** it contains no `wofi` entry

#### Scenario: manifest-reader parity
- **WHEN** `test_yaml_manifest_reader.py` runs
- **THEN** its expected package set contains `rofi` and not `wofi`

### Requirement: group_vars maps rofi on both distro families
The `packages` map in `group_vars/arch.yml` and `group_vars/debian-family.yml` SHALL each include `rofi: rofi`, so the packages role actually installs it (the map, not the manifest, is the install authority).

#### Scenario: arch map resolves rofi
- **WHEN** the Arch group_vars are loaded
- **THEN** `packages.rofi == "rofi"`
- **AND** the packages role flat list includes `rofi`

#### Scenario: debian-family map resolves rofi
- **WHEN** the Debian-family group_vars are loaded
- **THEN** `packages.rofi == "rofi"`

### Requirement: compositor_configs places the launcher skeleton and its dirs
The compositor_configs role SHALL ensure `config/rofi/` and `config/rofi/launcher/` under the spine and SHALL place `dotfiles/config/rofi/launcher/config.rasi` as one per-file skeleton entry (repo-authoritative, `force: true`, no `creates:`).

#### Scenario: config dirs are ensured
- **WHEN** the compositor_configs role runs
- **THEN** `compositor_configs_config_dirs` includes `config/rofi` and `config/rofi/launcher`
- **AND** a `file` `state: directory` task re-ensures them

#### Scenario: the launcher skeleton is placed
- **WHEN** the role's skeleton loop runs
- **THEN** `compositor_configs_skeleton_files` includes the `rofi/launcher/config.rasi` entry with a `dotfiles/config/rofi/launcher/config.rasi` source
- **AND** the placement task renders with `force: true` and no `creates:`
- **AND** the skeleton count is exactly 27 (26 + rofi)

#### Scenario: no absolute paths
- **WHEN** role vars/tasks are scanned
- **THEN** the new entries derive from `{{ compositor_configs_repo_root }}` and `{{ compositor_configs_spine_config_dir }}` (no literal absolute paths)

### Requirement: config-links and verify include the rofi dir
`config_links_managed_dirs` and `verify_managed_link_dirs` SHALL both include `rofi` (parity-EXACT), and `rofi` SHALL NOT be added to the GTK migrate-then-symlink set.

#### Scenario: managed dir parity
- **WHEN** config_links and verify vars are compared
- **THEN** both lists contain `rofi`
- **AND** the parity test passes

#### Scenario: not a GTK migrate dir
- **WHEN** `config_links_gtk_dirs` is inspected
- **THEN** `rofi` is absent from it

#### Scenario: verify asserts the symlink
- **WHEN** the verify role runs
- **THEN** it asserts `~/.config/rofi` is a symlink into `<install>/config/rofi` (the managed-link stat/islnk/lnk_target checks)

### Requirement: provisioning converges idempotently
Re-running the provisioning roles SHALL be idempotent: the launcher skeleton, the spine dirs, and the `~/.config/rofi` link all converge to the repo state with no drift on a second run.

#### Scenario: second run reports no change
- **WHEN** the compositor-configs and config-links roles are re-applied after a successful first apply
- **THEN** the spine dirs, skeleton file, and `~/.config/rofi` symlink are unchanged
- **AND** the run reports no modifications for those resources

### Requirement: docs record the launcher and the artifact
The hexagonal-architecture doc's launcher row and the shared-data-contract artifact set/consumer table SHALL be updated to name `rofi` and the `colors.rasi` artifact + rofi pointer.

#### Scenario: docs updated
- **WHEN** the docs are inspected
- **THEN** the launcher row names `rofi`
- **AND** the shared-data-contract artifact set includes `colors.rasi`
- **AND** the consumer table includes the `config/rofi/colors.rasi → current/colors.rasi` row