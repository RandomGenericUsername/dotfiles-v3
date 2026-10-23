# Tasks: enable-ci-gates

## 1. Establish which gates are CI-safe (do this before editing anything)

- [x] 1.1 Inspect every gate's real dependencies — do not trust the prose. For the four
      Python gates, `grep -n '^import\|^from'` and account for each import.
- [x] 1.2 Confirm `capture-hexagonal-gate`'s single `subprocess` call is `git check-ignore`,
      not a desktop/compiler invocation, and that it degrades safely.
- [x] 1.3 Confirm `capture-test` needs no `gi://*` / `ags/*`: read `tsconfig.tests.json`
      (`"types": ["node"]`, no `typeRoots`) and `tests/ts/`.
- [x] 1.4 Determine the Node version floor for unflagged `.ts` type-stripping (22.18) and
      decide whether to inherit the runner's Node or pin one. → **pin `24`**.
- [x] 1.5 Read `capture-typecheck` → `capture-types` → `ags types -d … -u` and confirm it
      needs AGS + Astal + GIR, produces ~49 MB of host-specific output, and that its tolerated
      third-party bucket is keyed to `/usr/share/ags/js/`.
- [x] 1.6 Write the findings into `design.md` with the evidence, not a conclusion.

## 2. Split the gate set in the Makefile

- [x] 2.1 Introduce `GATES` and keep `gates: $(GATES)` with all seven, unchanged order.
- [x] 2.2 Add `gates-ci: $(filter-out capture-typecheck,$(GATES))` — the six CI-safe gates.
- [x] 2.3 Add `gates-ci` to `.PHONY`.
- [x] 2.4 Delete the Makefile comment that says CI is dead ("the push trigger cannot fire …
      repairing the trigger is a separate change the owner deferred"). It is now false, and it
      is the reason a future reader would believe CI is still broken.
- [x] 2.5 Replace it with a comment stating *why* `capture-typecheck` is excluded (it cannot
      run there, not that it is inconvenient there) and that `make gates` still runs it.

## 3. Repair the workflow

- [x] 3.1 `push: branches: [main]` → `push: branches: [master]`.
- [x] 3.2 Keep `pull_request` unfiltered so any PR is still checked.
- [x] 3.3 Add `workflow_dispatch:` so a CI run can be reproduced on demand.
- [x] 3.4 Add the missing `capture-hexagonal-gate` job.
- [x] 3.5 Add the missing `capture-test` job, with `actions/setup-node@v4` at `node-version: '24'`.
- [x] 3.6 Do **not** add `capture-typecheck`; document in the workflow header why, so the
      omission reads as a decision rather than an oversight.
- [x] 3.7 Do **not** add `npm install` to the `capture-test` job; document why (the `@types/node`
      defect would turn it red, and the target's optional `tsc` sub-step self-skips loudly).
- [x] 3.8 Keep one job per gate. Do not collapse into a single combined job.

## 4. Validate before claiming it works

- [x] 4.1 Parse the workflow YAML programmatically; assert the job graph: 6 jobs, all
      `ubuntu-latest`, no inter-job dependencies.
- [x] 4.2 Build a clean simulated checkout from tracked files only (no `node_modules/`, no
      `.venv`) and run `make gates-ci` there. → exit 0.
- [x] 4.3 Prove no desktop-dependent command leaked into the CI set:
      `make -n gates-ci | grep -cE 'ags types|npm install'` → 0.
- [x] 4.4 Run all seven gates on this machine and confirm each is green, including the
      desktop-only one.
- [x] 4.5 Record what could NOT be verified (no GitHub Actions run — no SSH key, no push
      access) in `design.md` under "Verification NOT performed".

## 5. Report

- [x] 5.1 Per-gate table: what it needs, whether `ubuntu-latest` has it, and the evidence.
- [x] 5.2 The split, the justification, and what a developer still runs locally.
- [x] 5.3 The workflow diff plus the YAML validation output.
- [x] 5.4 The CI-safe subset run locally, green.
- [x] 5.5 `git diff --stat`, `git status --porcelain`, `pwd`.

## Follow-ups explicitly NOT in this change

- [ ] F1. Fix the missing `@types/node` so `make capture-test`'s `tsc` sub-step can pass at all
      (currently TS2688 on this machine). Until then CI runs 114 pass / 1 named skip rather than
      115 pass. See `design.md` § "The `@types/node` defect".
- [ ] F2. Decide whether `capture-typecheck` ever gets CI coverage — e.g. a container image
      with AGS/Astal pinned, so the type surface it checks is reproducible rather than
      host-specific. Out of scope here; the honest answer today is "no".
- [ ] F3. Watch the first real CI run on `master` and triage anything the months of
      gate-by-hand execution let drift.
