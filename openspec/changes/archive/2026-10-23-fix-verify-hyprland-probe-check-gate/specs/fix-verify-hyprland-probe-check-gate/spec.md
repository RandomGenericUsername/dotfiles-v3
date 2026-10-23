## ADDED Requirements

### Requirement: Every probe in the verify role SHALL declare `when: not ansible_check_mode`

Every `ansible.builtin.command` task in `roles/verify/tasks/main.yml` SHALL carry
`when: not ansible_check_mode` as its final key, matching the placement used by
the sibling probes (`Gate csg settings parse`, `Gate weg settings parse`, `Gate
itr list against icons.yaml`, `Check masked systemd user units`, `Check running
state of masked systemd user units`).

Rationale. `bootstrap.yaml --check` must "complete cleanly without mutation"
(AC 5) and stay green on a partially-provisioned host. The role's gates are its
*declared* contract; a task that relies on the library short-circuit instead is
relying on an action-plugin behaviour (`command` is documented `check_mode:
support: partial`) for a host-state property. An ansible-core release that began
executing check-mode commands would make such a task spawn a real process during
every dry run with no test failing, because the gate tests YAML text rather than
runtime behaviour.

#### Scenario: The Hyprland IPC probe is check-gated
- **WHEN** `roles/verify/tasks/main.yml` is parsed and the task named `Check whether Hyprland IPC is reachable` is inspected
- **THEN** its `when` is exactly `not ansible_check_mode`
- **AND** its module is `ansible.builtin.command` with `argv: [hyprctl, version]`, `register: verify_hyprland_check`, `changed_when: false`, `failed_when: false`

#### Scenario: No command task is left ungated
- **WHEN** every task whose module is `ansible.builtin.command` in `roles/verify/tasks/main.yml` is enumerated
- **THEN** each one has `when == "not ansible_check_mode"`
- **AND** this is already pinned by `test_settings_parse_gate_tasks_exist_and_are_check_gated`, which iterates all `_command_tasks()` entries

#### Scenario: A check-mode run does not spawn the probe
- **WHEN** `ansible-playbook playbooks/verify.yaml --check -e install_dir=<abs>` runs
- **THEN** the task `Check whether Hyprland IPC is reachable` is reported as skipped
- **AND** no `hyprctl` process is spawned by it

### Requirement: A task consuming a check-gated register SHALL NOT dereference it unconditionally

Where a task reads a registered variable produced by a `when: not
ansible_check_mode` task, the reading condition SHALL short-circuit on
`not ansible_check_mode` first, so the register is never dereferenced in a run
where the producer was conditionally skipped.

Rationale. A conditionally skipped task registers
`{skipped: True, skip_reason: …}` with **no `rc` key**. That differs from the
library check-mode short-circuit, which registers `skipped: True` **and
`rc: 0`**. A bare `verify_hyprland_check.rc` therefore raises a hard evaluation
error — `object of type 'dict' has no attribute 'rc'` — under `--check`,
aborting the dry run. `failed_when: false` does not apply to `when` evaluation.
Jinja's `and` short-circuits left to right, so
`not ansible_check_mode and <expr>` never evaluates `<expr>` in check mode.

#### Scenario: The AGS-skip warning is gate-safe
- **WHEN** the task named `Warn when the AGS gate is skipped without Hyprland` is inspected
- **THEN** its `when` is `not ansible_check_mode and verify_hyprland_check.rc != 0`
- **AND** its `msg` still names the first-login `autostart` that launches the bar and overlay

#### Scenario: The check-mode run completes cleanly
- **WHEN** `ansible-playbook playbooks/verify.yaml --check -e install_dir=<abs>` runs
- **THEN** the recap is `failed=0` with no `[ERROR]` in the output
- **AND** the recap is unchanged from before the gate was added: `ok=19 changed=0 unreachable=0 failed=0 skipped=83`

#### Scenario: The gate and its consumer land together
- **WHEN** the probe is gated but the warning task is not
- **THEN** `verify.yaml --check` fails at the warning task with `object of type 'dict' has no attribute 'rc'`
- **AND** the recap reports `failed=1`
- **AND** therefore the two edits are not independent and must ship in one change

### Requirement: A check-mode run SHALL NOT assert a host-state verdict it never evaluated

Under `--check`, a probe's registered exit status SHALL NOT be consumed as
though the probe had run. The library short-circuit returns `rc: 0` — a
fabricated **success** — for a process that never started, which would otherwise
read as a positive verdict ("Hyprland IPC is reachable") on a dry run.

#### Scenario: No fabricated positive under check mode
- **WHEN** `verify.yaml --check` runs and the probe is skipped
- **THEN** the probe's register carries no `rc` that downstream logic reads as a successful probe
- **AND** the always-on AGS assert remains gated `when: not ansible_check_mode`, so it does not consume the value at all in a dry run

#### Scenario: The vacuous-pass shape survives on a real run
- **WHEN** `test_ags_gate_is_session_aware` inspects the always-on AGS assert
- **THEN** its `that` still contains `verify_hyprland_check.rc != 0 or`, so a machine with no Hyprland IPC passes vacuously instead of failing the provision

### Requirement: Real-run behaviour SHALL be unchanged

The authoritative gate is `dotfiles-provision verify`, which runs with
check=False. This change is check-mode-only and SHALL NOT alter what a real run
executes, asserts, or warns about.

#### Scenario: The probe still executes for real
- **WHEN** `verify.yaml` runs without `--check`
- **THEN** `hyprctl version` executes and `verify_hyprland_check.rc` reflects its real exit status

#### Scenario: The warning still fires for a session without Hyprland
- **WHEN** `verify.yaml` runs without `--check` on a host where `hyprctl version` exits non-zero
- **THEN** the task `Warn when the AGS gate is skipped without Hyprland` runs and prints its message

#### Scenario: No gate or test was weakened to achieve this
- **WHEN** the diff for this change is reviewed
- **THEN** no `when:` clause is removed, no assertion is relaxed, and no test is edited or skipped
- **AND** `test_settings_parse_gate_tasks_exist_and_are_check_gated` goes green on the merits, unmodified
