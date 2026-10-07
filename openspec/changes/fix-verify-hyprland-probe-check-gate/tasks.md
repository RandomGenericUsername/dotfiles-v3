## 1. Confirm the mechanism BEFORE changing anything

- [x] 1.1 Capture the pre-change `--check` task-level output:
      `ANSIBLE_CONFIG=src/provisioning/ansible/ansible.cfg uv run --directory src/provisioning ansible-playbook "$PWD/src/provisioning/ansible/playbooks/verify.yaml" --check -e install_dir="$PWD"`
- [x] 1.2 **Contradict-check the assumed mechanism.** The brief claims `ansible.builtin.command` still EXECUTES under `--check`. Prove it either way with a minimal, entirely unconditional probe playbook that spawns a side effect (`sh -c 'echo … >> ran.log'`).
- [x] 1.3 Record the finding. On ansible-core 2.21.2 the probe is short-circuited (`msg: 'Command would have run if not in check mode'`, `skipped: True`, `rc: 0`) and the side-effect file is **never created** — no process is spawned. `shell` behaves identically. This matches the role's own header at `roles/verify/tasks/main.yml:58`.
- [x] 1.4 Therefore: the described consequence (`hyprctl version` actually invoked under `--check`) does not occur, and the BEFORE output already shows the task as `skipping`. State this in the report rather than proceeding as if the premise held.
- [x] 1.5 Identify the defect that IS real: the role's declared invariant (every probe check-gated, enforced by `test_settings_parse_gate_tasks_exist_and_are_check_gated`) had exactly one exception.

## 2. The gate

- [x] 2.1 Add `when: not ansible_check_mode` to `Check whether Hyprland IPC is reachable`, as the final key, matching the sibling probes' placement.
- [x] 2.2 Leave `argv`, `register`, `changed_when`, `failed_when` untouched.
- [x] 2.3 Add a comment block explaining why the gate is declared rather than inherited, and recording the fabricated-`rc: 0` finding.

## 3. The consumer — NOT optional, discovered by running it

- [x] 3.1 Apply 2.1 **alone** and run the check-mode playbook. Capture the failure verbatim:
      `[ERROR]: Task failed: A 'when' expression failed: … object of type 'dict' has no attribute 'rc'` at `main.yml:508`, recap `failed=1`.
- [x] 3.2 Explain the mechanism: a *conditionally* skipped task registers `{skipped: True, skip_reason: …}` with **no `rc` key**, unlike the library short-circuit's `rc: 0`. `failed_when: false` does not apply to `when` evaluation.
- [x] 3.3 Fix the consumer: `Warn when the AGS gate is skipped without Hyprland` →
      `when: not ansible_check_mode and verify_hyprland_check.rc != 0`. Jinja `and` short-circuits left to right, so `verify_hyprland_check.rc` is never evaluated in check mode.
- [x] 3.4 Reject the alternative (`| default(1)`): it fabricates a "no Hyprland" verdict for a probe that never ran and emits a misleading warning during a dry run.
- [x] 3.5 Keep the warn task's `msg` intact — it names the first-login `autostart`, pinned by `test_ags_gate_is_session_aware`.

## 4. Tests — confirm coverage rather than duplicate it

- [x] 4.1 **Do not add a new test.** `test_settings_parse_gate_tasks_exist_and_are_check_gated` already iterates every `_command_tasks()` entry and asserts `when == "not ansible_check_mode"` — it pins exactly this line and was red on the merits.
- [x] 4.2 **Do not edit or weaken that test.** Record explicitly in the report that no new test was needed and why.
- [x] 4.3 Confirm `test_ags_gate_is_session_aware` still passes (it locates the probe by name substring and asserts `hyprctl` appears in the task — both preserved).

## 5. Verification — machine-checkable, no human eyes

- [x] 5.1 The post-change check-mode run skips the probe **and** the warning, with `failed=0` and **no** `[ERROR]` anywhere in the output.
- [x] 5.2 The recap is byte-identical to the BEFORE recap: `ok=19 changed=0 unreachable=0 failed=0 skipped=83`. A shifted recap would mean the gate changed more than the skip path.
- [x] 5.3 `uv run --directory src/provisioning pytest tests/unit -q` → **3 failed / 684 passed** (from 4 / 684), and the three remaining are exactly `test_packages_manifest_has_verified_set`, `test_arch_packages_cover_exactly_logical_set`, `test_debian_family_packages_cover_exactly_logical_set` — the queued package-manifest-drift failures, none caused by this change.
- [x] 5.4 `python3 scripts/capture-hexagonal-gate.py` → PASS (check 6: 33 used / 28 styled).
- [x] 5.5 `make capture-typecheck` → 0 errors.
- [x] 5.6 `make capture-test` → 115. capture `pytest tests/` → 97.

## 6. Scope discipline

- [x] 6.1 Touch nothing outside the check-gate concern. `packages.yaml`, `group_vars/*`, and `test_ansible_scaffold.py` are untouched — the second queued change owns them.
- [x] 6.2 No `when:` removed, no assertion relaxed, no test weakened anywhere.
- [x] 6.3 `node_modules` stays gitignored; nothing committed.

## 7. Follow-up reported, not fixed

- [x] 7.1 `roles/verify/tasks/main.yml:412` and `:419` use `ansible.builtin.shell` (`pacman -Q …`) with no `when:` — the same class of ungated probe, and the same future-upgrade exposure. The failing invariant covers `ansible.builtin.command` only, so they are not caught.
- [x] 7.2 Record this in the proposal as an explicit out-of-scope finding rather than silently fixing it or silently omitting it, because this worktree has a second change queued against it.
