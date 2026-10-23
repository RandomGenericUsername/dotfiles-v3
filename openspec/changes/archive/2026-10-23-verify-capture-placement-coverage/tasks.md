# Tasks: verify-capture-placement-coverage

Verification coverage only. **No deployed source changes** — `gui_tools_app_files`,
`gui_tools/vars/main.yml` and everything under `src/gui-tools/capture-tool/` are
untouched.

Each task states its acceptance as a *command output*, not an opinion. Invariants
across every task:

- `python3 scripts/capture-hexagonal-gate.py` → **PASS**
- `make capture-test` → **85**
- `cd src/gui-tools/capture-tool && uv run --with pytest python -m pytest tests/ -q` → **97**
- `uv run --directory src/provisioning pytest tests/unit -q` → **4 failed / 659 passed**,
  the same 4 names, never more. The 4 are owned by a separate change and are NOT
  fixed here.
- `git diff --stat src/gui-tools/capture-tool/ src/provisioning/ansible/roles/gui_tools/`
  → **empty**

---

## 1 — Prove the gap before touching anything

- [ ] 1.1 Write a throwaway script under `/tmp/opencode/` that loads
      `gui_tools/vars/main.yml` and `verify/vars/main.yml` with
      `ansible.parsing.dataloader.DataLoader` (`load_from_file` — **not** `load`,
      which returns a tagged str and makes the check vacuous), derives the
      `ags-capture/`-relative dest tail from each side, and prints the set
      difference.
- [ ] 1.2 Record the output. Expected: 24 placed, 19 verified, **5 missing** —
      `domain/capture-request.ts`, `domain/cli-args.ts`, `ui/shared/groups.ts`,
      `ui/shared/icons.ts`, `ui/shared/rows.ts` — and **0** verify entries with no
      placement.
- [ ] 1.3 If the missing set is not exactly those 5, **stop**. The premise is
      wrong; adapt the change to the measured reality rather than making the
      report true by construction.

**Acceptance:** the script's output pasted above, showing exactly 5 and only those 5.

---

## 2 — Close the coverage gap

- [ ] 2.1 Add the 5 paths to `verify_gui_tools_app_files` in
      `src/provisioning/ansible/roles/verify/vars/main.yml`, grouped with the
      layer they belong to (`domain/` after the existing pure-domain entries,
      `ui/shared/` after the classic-layout entries).
- [ ] 2.2 Comment each group with the bundling consequence of its absence, in the
      register of the existing capture entries — per file, not one blanket note.
      `domain/cli-args.ts` earns the longest: it is the single request→argv
      translator and carries the two argparse-rejected tokens (`--size 75` not
      `75%`, `--audio mic` not `microphone`), so its absence is a capture that
      silently never happens.
- [ ] 2.3 **Do not** touch `gui_tools/vars/main.yml`. The placement list is
      already correct; only its verification was incomplete.

**Acceptance:** re-running 1.1's script prints `covered: 24/24`, `MISSING from
verify (0)`, `verify entries with no placement (0)`.

---

## 3 — Make the gap unreintroducible

- [ ] 3.1 Add a derived-coverage test to
      `src/provisioning/tests/unit/test_verify_role.py`, in `TestVerifyVars`
      beside the other cross-role parity locks, using the file's existing `_vars()`
      and `_sibling_vars()` helpers.
- [ ] 3.2 Derive the expected set **from `gui_tools_app_files`** — every
      `ags-capture/` dest tail — and assert every one is present in
      `verify_gui_tools_app_files`. Assert **subset, not equality** (see design.md
      §"Where the assertion lives"), because the verify list spans four placement
      manifests and this change owns only the capture app.
- [ ] 3.3 Assert both sides duplicate-free before differencing, so a repeated dest
      cannot be collapsed away by the set.
- [ ] 3.4 Assert `verified - placed` is empty for `ags-capture/`, so verify never
      demands a path no placement task creates.
- [ ] 3.5 Name the missing paths in the failure message. "these 5 are listed" is
      not a test; "the next placement entry added without a matching verify entry
      fails loudly, naming the path" is.

**Acceptance:** the test passes, and its failure mode is demonstrated in task 4.

---

## 4 — Negative-test the new test

- [ ] 4.1 Delete one `verify_gui_tools_app_files` entry
      (`.../config/ags-capture/domain/cli-args.ts` — the highest-consequence one).
- [ ] 4.2 Run `uv run --directory src/provisioning pytest
      tests/unit/test_verify_role.py -q` → **RED**, with the failure naming
      `domain/cli-args.ts`.
- [ ] 4.3 Restore the entry. Run again → **GREEN**.
- [ ] 4.4 Paste both outputs. A test that cannot be shown red was never proven to
      bite.

**Acceptance:** the red and green outputs pasted, red naming the exact path.

---

## 5 — Keep the fixture honest

- [ ] 5.1 Add the 5 files to `_build_provisioned_layout` in
      `test_verify_role.py`. Without this,
      `test_verify_passes_on_a_provisioned_machine` fails — correctly, because
      the stand-in machine is no longer provisioned.
- [ ] 5.2 The fixture must list the 5 explicitly, not derive them from
      `gui_tools_app_files`. A fixture derived from the manifest under test stops
      being an independent stand-in.

**Acceptance:** `uv run --directory src/provisioning pytest
tests/unit/test_verify_role.py tests/unit/test_gui_tools_role.py -q` → green.

---

## 6 — Full-suite confirmation

- [ ] 6.1 `uv run --directory src/provisioning pytest tests/unit -q` → **4 failed /
      659 passed**, the same 4 names (`test_packages_manifest_has_verified_set`,
      `test_arch_packages_cover_exactly_logical_set`,
      `test_debian_family_packages_cover_exactly_logical_set`,
      `test_settings_parse_gate_tasks_exist_and_are_check_gated`). The count must
      not rise and the set of names must not change.
- [ ] 6.2 `python3 scripts/capture-hexagonal-gate.py` → **PASS**.
- [ ] 6.3 `make capture-test` → **85**.
- [ ] 6.4 `cd src/gui-tools/capture-tool && uv run --with pytest python -m pytest
      tests/ -q` → **97**.
- [ ] 6.5 `git diff --stat` → only `openspec/changes/verify-capture-placement-coverage/**`,
      `verify/vars/main.yml`, `tests/unit/test_verify_role.py`. Nothing under
      `src/gui-tools/` and nothing under `roles/gui_tools/`.

**Acceptance:** all five command outputs pasted.