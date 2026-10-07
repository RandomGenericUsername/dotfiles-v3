## Why

`.github/workflows/gates.yml` has never run. Not "has been flaky", not "is failing" — it has
never executed a single gate, because it triggers on a branch that does not exist:

```yaml
on:
  push:
    branches: [main]     # this repository's default branch is `master`
  pull_request:
```

`origin/HEAD -> origin/master`, and `main` exists neither locally nor on the remote. The push
trigger therefore cannot fire for any commit in this repository's history. The only live path
is `pull_request`, and the last PR-triggered run was 2026-06-17 while the workflow file itself
was last modified 2026-09-30 — months of gate work have landed since with no CI behind it.

**The repair is not one word.** `make gates` runs seven gates and the workflow only ever
covered four of them. Adding the missing three naively turns the first push red:

| gate | on `ubuntu-latest`? | why |
|---|---|---|
| `contracts-check` | yes | pure-Python deps from PyPI; `setup-uv` fetches them |
| `wifi-mock-parity` | yes | stdlib only |
| `speedtest-mock-parity` | yes | stdlib only |
| `speedtest-no-new-architecture` | yes | stdlib only |
| `capture-hexagonal-gate` | yes | stdlib only; its one `subprocess` call is `git check-ignore` |
| `capture-test` | yes | `node --test` on Node ≥ 22.18; no GTK, no network, no bundler |
| `capture-typecheck` | **NO** | needs `ags` + Astal/GIR; the runner has no AGS, no Astal, no GTK4 |

This is almost certainly why the trigger stayed broken. A workflow that parses but fails on the
runner is worse than no workflow: it teaches everyone that red means nothing.

## What Changes

- **Trigger fixed**: `push: branches: [master]` (plus `workflow_dispatch` for on-demand runs).
  `pull_request` stays unfiltered, so any PR is still checked.
- **`capture-hexagonal-gate` and `capture-test` added to CI** — the two gates that were added
  after the workflow was written, both of which are in fact CI-safe. Their absence was part of
  the same defect.
- **`capture-typecheck` stays a developer gate, and says so.** It is not listed in the workflow
  and it is not in `make gates-ci`, because it cannot run there. It is *not* removed,
  weakened, or made to no-op: `make gates` still runs all seven.
- **`make gates` gains a documented split**: `GATES` (all seven, developer) and `gates-ci`
  (`$(filter-out capture-typecheck,$(GATES))`, what CI runs). The Makefile comment that
  claimed "there is no working CI for any of these gates" is now false and is corrected.
- The pre-existing Makefile comment justifying the broken trigger is deleted rather than left
  to rot, since it is the reason the next reader would believe CI is still dead.

## Non-goals

- **Not** changing what any gate asserts. No tolerance widened, no check removed, no ALLOWLIST
  entry added. This change is only about *which gates run where*.
- **Not** installing AGS/Astal/GTK4 on the runner. A 49 MB machine-specific type dump, an
  npx-pulled `ts-for-gir`, and an error bucket keyed to the literal path `/usr/share/ags/js/`
  are a desktop, not a CI step. `capture-typecheck` is honest about needing a desktop.
- **Not** fixing the pre-existing missing-`@types/node` defect that makes `capture-test`'s
  optional `tsc` sub-step fail locally with TS2688. It is a real bug in a different gate and
  is filed in the design doc rather than smuggled in here.
- **Not** collapsing the workflow into one combined job. One job per gate is deliberate: a
  failure must name the gate that broke.

## Impact

- `.github/workflows/gates.yml` — trigger branch, plus two new jobs and a `setup-node` step.
- `Makefile` — `gates` is now variable-driven; new `gates-ci` target; corrected comment block.
- Nothing under `src/` changes. No gate's assertions change.
- Risk: the first push to `master` after merge runs CI for the first time in the repository's
  history, so it may surface failures that have been latent for months. That is the point —
  but it is the honest risk of this change and is stated rather than hidden.
