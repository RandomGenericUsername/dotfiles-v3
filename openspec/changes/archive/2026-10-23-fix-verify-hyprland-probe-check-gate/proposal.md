## Why

`Check whether Hyprland IPC is reachable` was the **only** command task in the
`verify` role without a `when: not ansible_check_mode` gate. Every sibling probe
(`Check AstalWp binding package is installed`, `Check masked systemd user units`,
`Gate csg settings parse`, …) carries one, and
`tests/unit/test_verify_role.py::TestVerifyTasks::test_settings_parse_gate_tasks_exist_and_are_check_gated`
asserts the invariant over *every* `_command_tasks()` entry:

```python
for task in _command_tasks():
    assert task.get("when") == "not ansible_check_mode", (
        f"parse gate {task.get('name')!r} must be check-gated"
    )
```

The test was red. That is the reported defect.

## Root cause — with a correction to the assumed mechanism

The task brief asserted that under `--check`, `ansible.builtin.command` still
EXECUTES, so a check-mode run really invokes `hyprctl version`, and the missing
`when:` is what lets it through.

**That is not what ansible-core 2.21.2 does.** Measured on this worktree
(`ansible [core 2.21.2]`), an ungated `command` task under `--check` is
short-circuited by the action plugin and never spawns a process. A minimal
playbook with no conditions at all:

```
TASK [Unconditional command] ************************************************
skipping: [localhost]
TASK [Report] ******************************************************************
    "msg": "result={'changed': False, 'failed': False, 'skipped': True,
              'msg': 'Command would have run if not in check mode',
              'rc': 0, 'stdout': '', ...}"
=== did anything run? ===
NOTHING RAN
```

The proof is the side effect: the probe shelled out to `echo ... >> ran2.log` and
the file was never created. `shell` behaves identically.

This matches what the role's own file header already documented
(`roles/verify/tasks/main.yml:58`):

> Under `--check`: stat tasks run and report honestly (no mutation — fine
> ungated); command/shell tasks are SKIPPED by ansible-core 2.20.3

So the described *consequence* — `hyprctl version` actually being invoked during a
check-mode run — does not occur, and the BEFORE `--check` output confirms the task
already reported `skipping`. The gate was never what prevented execution.

## What the defect actually is

Three real problems, all in the check-gate concern:

1. **A declared invariant was broken.** The role claims every probe is
   check-gated; one was not. The gates are the role's *declared* contract, and
   relying on a library short-circuit for a security-relevant property
   ("a dry run must not touch host state") inverts the dependency: an
   ansible-core upgrade that made `command` check-mode-aware would silently turn
   this into a real `hyprctl` invocation. The gate makes the property explicit
   and version-independent.

2. **The short-circuit fabricates `rc: 0`.** "Command would have run if not in
   check mode" returns `skipped: True, rc: 0` — a *successful* exit for a process
   that never started. Under `--check`, `verify_hyprland_check.rc == 0` therefore
   read as **"Hyprland IPC is reachable"**, a fabricated positive. It was inert
   only because the always-on AGS assert that consumes it is itself gated.

3. **The gate has a consumer that breaks when applied.** This is the part the
   brief did not anticipate, and it is why the change is two lines rather than
   one. The next task dereferences the register unconditionally:

   ```yaml
   - name: Warn when the AGS gate is skipped without Hyprland
     when: verify_hyprland_check.rc != 0
   ```

   A *conditionally* skipped task registers `{'skipped': True, 'skip_reason': ...}`
   with **no `rc` key at all** — a different shape from the library short-circuit's
   `rc: 0`. So adding the bare gate alone does not fix the test and quietly breaks
   the dry run:

   ```
   TASK [verify : Check whether Hyprland IPC is reachable] ***
   skipping: [localhost]

   TASK [verify : Warn when the AGS gate is skipped without Hyprland] ***
   [ERROR]: Task failed: A 'when' expression failed: Error while evaluating
   conditional: object of type 'dict' has no attribute 'rc'

   PLAY RECAP ***
   localhost : ok=5 changed=0 unreachable=0 failed=1 skipped=28
   ```

   `bootstrap.yaml --check` must "complete cleanly without mutation" (AC 5).
   The warn task must therefore short-circuit on `not ansible_check_mode` first.

## What Changes

- **`when: not ansible_check_mode` on `Check whether Hyprland IPC is reachable`**,
  placed as the last key to match the sibling gates exactly.
- **`when: not ansible_check_mode and verify_hyprland_check.rc != 0` on the
  `Warn when the AGS gate is skipped without Hyprland` consumer**, so the `rc`
  dereference is reachable only where the probe actually ran. Jinja's `and`
  short-circuits, which is what makes this safe rather than a second failure.
- A comment block recording why both lines are needed, so the pair is not
  "simplified" apart later.

**No new test.** `test_settings_parse_gate_tasks_exist_and_are_check_gated`
already pins the first line, and it was red on the merits.

## Non-goals

- Not changing what the AGS gate asserts. The always-on assert keeps its
  `verify_hyprland_check.rc != 0 or …` vacuous-pass shape —
  `test_ags_gate_is_session_aware` pins it, and it is already gated.
- Not touching the ungated `shell` probes (`Check AstalNotifd binding package is
  installed`, `Check AstalWp binding package is installed`). They are outside this
  change's scope and are not covered by the failing invariant, which iterates
  `ansible.builtin.command` only. Flagged as a separate finding — see below.
- Not changing real-run behaviour. `dotfiles-provision verify` runs check=False,
  where the probe still executes and still gates the warn exactly as before.
- Not removing or relaxing any gate or test.

## Follow-up finding (NOT fixed here — out of scope)

`roles/verify/tasks/main.yml:412` and `:419` use `ansible.builtin.shell`
(`pacman -Q …`) with no `when:`. The failing invariant does not cover them, so
they stay red-free — but they are the same class of ungated probe and the same
future upgrade risk. Left alone deliberately: this worktree has a second change
queued against it, and broadening scope here risks the manifest-drift work.

## Impact

- `src/provisioning/ansible/roles/verify/tasks/main.yml` — one added `when:` on
  the probe, one amended `when:` on its consumer, one comment block.
- No behaviour change on a real run; no change to the `--check` outcome
  (`ok=19 changed=0 failed=0 skipped=83` before and after).
- One existing test goes red → green. None edited.
