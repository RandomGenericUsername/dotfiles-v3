# Design: fix-verify-hyprland-probe-check-gate

## Two different "skipped" shapes

The whole design turns on a distinction that is easy to miss, because both
results render as the bare line `skipping: [localhost]` with no reason:

| how the task was skipped | registered result | has `rc`? |
|---|---|---|
| library short-circuit (ungated command under `--check`) | `{skipped: True, msg: 'Command would have run if not in check mode', rc: 0, stdout: '', …}` | **yes — `0`** |
| `when: not ansible_check_mode` (conditional skip) | `{skipped: True, skip_reason: 'Conditional check was false', …}` | **no** |

The first is a *fabricated success*: a command that never ran, reported as
exit 0. The second is an honest "I did not run" with no exit status at all.

Measured on this worktree with ansible-core 2.21.2, both via a minimal
unconditional probe playbook and via the role itself. The decisive evidence for
the first row is the absent side effect — a probe appending to a log file left
the file uncreated, so no process was spawned.

This is why the fix cannot be a one-liner. See below.

## Why the gate is still worth adding, given the short-circuit

The short-circuit means the *behaviour* is currently safe. Adding the gate is
still the right call, for three reasons:

1. **It restores a declared invariant.** The role's header states the contract,
   the sibling tasks implement it, and a test enforces it. One ungated task made
   the documentation a lie in the direction that hides future drift.
2. **It removes a dependency on library behaviour for a host-state property.**
   `command` is documented `check_mode: support: partial`. The observed
   short-circuit is an action-plugin behaviour, not a stable public guarantee.
   An ansible-core release that starts *executing* check-mode commands would turn
   this task into a real `hyprctl version` spawn during every `bootstrap.yaml
   --check` — with no test failing, because the gate tests the YAML text, not
   the runtime. Explicit `when:` is the only thing that survives that.
3. **It eliminates the fabricated `rc: 0`.** Under `--check` the probe currently
   reads as "Hyprland IPC is reachable". Nothing acted on it (the consuming
   assert is gated), so this is latent — but it is a lie in the register that a
   future ungated reader would trust.

Cost of the gate: one line, no behavioural delta on a real run.

## The consumer, and why `and` is load-bearing

Adding the gate alone turns a red test green and breaks the dry run:

```
TASK [verify : Check whether Hyprland IPC is reachable] ***
skipping: [localhost]

TASK [verify : Warn when the AGS gate is skipped without Hyprland] ***
[ERROR]: Task failed: A 'when' expression failed: Error while evaluating
conditional: object of type 'dict' has no attribute 'rc'

PLAY RECAP ***
localhost : ok=5 changed=0 unreachable=0 failed=1 skipped=28
```

The warn task is a `debug` keyed off `verify_hyprland_check.rc != 0`. Once the
producer is conditionally skipped the register has no `rc`, and Ansible treats
the missing attribute as a **hard evaluation error**, not a false condition —
`failed_when` on a `debug` task does not apply to `when` evaluation.

Two candidate fixes:

**(a) `when: verify_hyprland_check.rc | default(1) != 0`** — tolerates the
missing key. But it fabricates a *negative* verdict (`rc=1` ⇒ "no Hyprland") for
a probe that did not run, under `--check`, where the truth is "unknown". It also
leaves a non-empty warning firing in dry runs about a gate that is itself being
skipped — noise that trains a reader to ignore warnings.

**(b) `when: not ansible_check_mode and verify_hyprland_check.rc != 0`** —
Jinja `and` short-circuits left to right, so under `--check` the right-hand
expression is never evaluated and the missing attribute is never touched. On a
real run `ansible_check_mode` is False and the condition is byte-for-byte the old
behaviour.

**(b) is chosen.** It makes "unknown" render as silence instead of as a false
alarm, it preserves real-run behaviour exactly, and it matches the role's
dominant idiom — every other state-consuming task in the file is gated
`when: not ansible_check_mode`.

## Why the warn task must be gated, not made tolerant

The tempting alternative is to leave the warn task alone and rely on
`default(...)`. That keeps a check-mode run emitting:

> no Hyprland IPC in this session — … the always-on AGS gate below is skipped
> meanwhile.

during a dry run in which the AGS gate is skipped *by the gate itself*, not by
missing IPC. The warning would be describing a cause that was never evaluated.
Gating it is both cheaper to read and more truthful.

## Scope boundaries

| path | touched | why |
|---|---|---|
| `Check whether Hyprland IPC is reachable` (`command`) | **yes** | the ungated probe; the failing invariant |
| `Warn when the AGS gate is skipped without Hyprland` (`debug`) | **yes** | the direct consumer; hard-errors once the producer is gated |
| `Assert always-on AGS instances are running` (`assert`) | no | already gated; its vacuous-pass shape is pinned by `test_ags_gate_is_session_aware` |
| `Check AstalNotifd/Wp binding package is installed` (`shell`) | no | same class of ungated probe, but outside this change's concern and not covered by the failing invariant — recorded as a follow-up |
| `packages.yaml`, `group_vars/*`, `test_ansible_scaffold.py` | no | a second, larger change is queued against this worktree |

## Ordering constraint

The two `when:` edits are **not independent**. The first alone turns a red test
into a failing playbook run. They must land in the same change, which is why
both are in this one.

## Verification

- **Behavioural, before/after:** `verify.yaml --check` must end
  `failed=0` with an unchanged recap (`ok=19 changed=0 unreachable=0 failed=0
  skipped=83`). If the recap shifts, the gate changed more than the skip path.
- **Intermediate state is a real failure mode** and was captured on purpose:
  gate-without-consumer fails at `main.yml:508`. A fix that only adds the first
  `when:` is detectable by running the playbook.
- **The named test** `test_settings_parse_gate_tasks_exist_and_are_check_gated`
  goes green without being edited.
- **No test regressions** elsewhere in `tests/unit`.

## Risk

Low. Two `when:` expressions in one role, no module changes, no register
consumers beyond the one handled. The gate-without-consumer intermediate was
demonstrated and closed, so the known failure mode is not being shipped.

Residual risk is the ungated `shell` probes noted above: same future-upgrade
exposure, out of scope here, and reported rather than silently fixed.
