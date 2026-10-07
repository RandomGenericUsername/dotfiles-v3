## ADDED Requirements

### Requirement: Every host-state probe in the verify role SHALL declare `when: not ansible_check_mode`, for BOTH `command` and `shell`

Every task in `roles/verify/tasks/main.yml` whose module is
`ansible.builtin.command` **or `ansible.builtin.shell`** SHALL carry
`when: not ansible_check_mode`, matching the placement used by the sibling
probes (`Gate csg settings parse`, `Check masked systemd user units`).

The module scope is the substance, not an implementation detail. `shell` is
documented `check_mode: support: PARTIAL` exactly like `command`, so it carries
the same obligation to declare the gate rather than inherit it. An invariant
scoped to `command` cannot observe a `shell` defect at all — which is how four
probes stayed ungated through an earlier gate sweep.

#### Scenario: The AstalNotifd probe is check-gated
- **WHEN** `roles/verify/tasks/main.yml` is parsed and the task named `Check AstalNotifd binding package is installed` is inspected
- **THEN** its module is `ansible.builtin.shell` with `pacman -Q {{ item }}`, `register: verify_notifd_binding_checks`, `changed_when: false`, `failed_when: false`
- **AND** its `when` is exactly `not ansible_check_mode`

#### Scenario: The AstalWp probe is check-gated
- **WHEN** the task named `Check AstalWp binding package is installed` is inspected
- **THEN** its module is `ansible.builtin.shell` with `register: verify_astal_wp_binding_checks`
- **AND** its `when` is exactly `not ansible_check_mode`

#### Scenario: Both `command -v` PATH probes are check-gated
- **WHEN** the tasks named `Check system binaries on PATH` and `Check CLI tools on PATH` are inspected
- **THEN** each is `ansible.builtin.shell` running `command -v {{ item }}`
- **AND** each has `when == "not ansible_check_mode"`

#### Scenario: No probe of either module is left ungated
- **WHEN** every task whose module key is in `("ansible.builtin.command", "ansible.builtin.shell")` is enumerated
- **THEN** each one has `when == "not ansible_check_mode"`
- **AND** this is pinned by `test_every_probe_task_is_check_gated`, whose failure message names the `rc`/`results` consequence

#### Scenario: The invariant fires on an ungated `shell` probe
- **WHEN** `when: not ansible_check_mode` is removed from the task named `Check AstalWp binding package is installed`
- **THEN** `test_every_probe_task_is_check_gated` fails, reporting that probe by name and module
- **AND** `test_settings_parse_gate_tasks_exist_and_are_check_gated` fails on the same task
- **AND** the pre-fix command-only form of that test passed on the same file, which is the blind spot being closed

#### Scenario: The invariant rejects a near-miss gate
- **WHEN** a probe's `when` is `ansible_check_mode`, `not ansible_check_mode and <expr>`, or `<register>.rc != 0`
- **THEN** the invariant reports it as ungated
- **AND** only the exact string `not ansible_check_mode` is accepted

### Requirement: The probe-gate invariant SHALL NOT flag modules that legitimately run under `--check`

The invariant SHALL be scoped to `command` and `shell` host-state probes.
`ansible.builtin.stat` tasks and the CONFIG seam asserts SHALL NOT be reported,
because `stat` executes honestly under `--check` without mutating anything and
the seam asserts are required to fail under `--check`.

#### Scenario: A `stat` task is not flagged
- **WHEN** the invariant is evaluated against a task whose module is `ansible.builtin.stat` with no `when`
- **THEN** it is not reported as an ungated probe

#### Scenario: An ungated seam assert is not flagged
- **WHEN** the invariant is evaluated against a task named `Assert install_dir seam is provided` with no `when`
- **THEN** it is not reported as an ungated probe

#### Scenario: The role's probe population still spans both modules
- **WHEN** the role's probe tasks are enumerated
- **THEN** the set of module keys among them equals `{"ansible.builtin.command", "ansible.builtin.shell"}`
- **AND** a role that stopped using one module fails the test, so the other half of the invariant cannot silently become dead

### Requirement: A check-mode run SHALL NOT consume a register from a conditionally-skipped probe

Where a task consumes a register produced by a `when: not ansible_check_mode`
probe, that consumer's own `when` SHALL be gated `when: not
ansible_check_mode`, so the register is never dereferenced in a run where the
producer was skipped. A conditionally skipped task registers
`{skipped: True, skip_reason: …}` with **no `rc` and no `results` key**.

#### Scenario: The four probes' consumers are all gated
- **WHEN** the consumers of `verify_system_binary_checks`, `verify_cli_tool_checks`, `verify_notifd_binding_checks` and `verify_astal_wp_binding_checks` are inspected
- **THEN** each one's `when` is `not ansible_check_mode`

#### Scenario: An ungated consumer aborts the dry run
- **WHEN** a gated probe's register is dereferenced by a task whose `when` does not check `ansible_check_mode`
- **THEN** the run fails with `object of type 'dict' has no attribute 'results'` and the recap reports `failed=1`
- **AND** the same consumer behind `not ansible_check_mode and <expr>` skips cleanly with `failed=0`

### Requirement: Real-run behaviour of the verify role SHALL be unchanged

`dotfiles-provision verify` runs `verify.yaml` with check=False and is the
authoritative gate. This change is check-mode-only.

#### Scenario: The probes still execute for real
- **WHEN** `verify.yaml` runs without `--check`
- **THEN** all four probes execute and their registers carry real `results` with real `rc` values
- **AND** the four consuming asserts evaluate normally

#### Scenario: A dry run still completes cleanly
- **WHEN** the four probes and their four consumers are driven under `--check`
- **THEN** the recap is `ok=0 changed=0 unreachable=0 failed=0 skipped=8`
- **AND** the same slice without `--check` is `ok=8 changed=0 unreachable=0 failed=0 skipped=0`

### Requirement: Every `packages.yaml` entry SHALL be reachable from a provisioning path, with no unresolved orphans

Every entry in `dotfiles/provisioning/packages.yaml` SHALL be a `group_vars`
`packages` key, a `group_vars` value, or present in `aur_packages` (with the
upstream `-git` suffix stripped). The pinned orphan set
(`_DECLARED_NOT_PROVISIONED`) SHALL be empty, and the assertion SHALL continue
to name both failure directions.

A package with no consumer SHALL NOT be added to a `group_vars` map, and a
package a config or script actually invokes SHALL NOT be removed from the
manifest.

#### Scenario: `xdg-utils` is provisioned because provisioning itself calls it
- **WHEN** `group_vars/arch.yml` and `group_vars/debian-family.yml` are inspected
- **THEN** both carry the key `xdg-utils` mapping to `xdg-utils`
- **AND** the key's provenance comment names the consumers: gui_tools' `xdg-mime default`, verify's `xdg-mime query default`, and the capture tool's and hypr-pano's `xdg-open`
- **AND** `xdg-utils` is not added to `aur_packages`, because it is not AUR-only

#### Scenario: `hyprcursor` is not declared because hyprland already depends on it
- **WHEN** `packages.yaml` is inspected
- **THEN** it contains no `hyprcursor` entry
- **AND** the removal site carries a comment recording that `pacman -Qi hyprland` lists `hyprcursor` as a direct dependency, and that `hyprland` is declared in both maps

#### Scenario: `lf` is not declared because nothing invokes it
- **WHEN** `packages.yaml` is inspected
- **THEN** it contains no `lf` entry
- **AND** no Hyprland keybinding, `autostart.lua` entry, rofi launcher entry, desktop file, shell rc, or `openspec` spec invokes `lf`

#### Scenario: The orphan set is empty but still pinned
- **WHEN** `_DECLARED_NOT_PROVISIONED` is inspected
- **THEN** it is an empty `frozenset`
- **AND** the reachability test still compares the computed orphan set against it exactly
- **AND** a newly declared, unreachable manifest entry fails the test naming the unexpected orphan

#### Scenario: The drift locks are re-snapshotted, not weakened
- **WHEN** the re-snapshotted key sets are inspected
- **THEN** `_LOGICAL_PACKAGE_KEYS` includes `xdg-utils` and the verified manifest set excludes `lf` and `hyprcursor`
- **AND** all three locks remain exact-set equality assertions
- **AND** each added or removed entry carries a provenance comment naming its evidence