# Design: prove-ci-matches-gates

## §1 The drift, measured

The workflow's job **keys**, read from `.github/workflows/gates.yml` (the
2-space keys under `jobs:` — two jobs carry a `name:` that differs from the key,
which the mapping table beside §3 reconciles):

```
contracts                wifi-mock-parity         battery-mock-parity
icons-json-drift         ansible-embedded-template-lint
speedtest-mock-parity    speedtest-no-new-architecture
capture-hexagonal        capture-test             ags-test
```

`make gates-ci` is `GATES` minus the two gates that need the desktop stack
(`capture-typecheck`, `bar-typecheck`). MEASURED from `make -pn gates-ci`
(2026-10-07): eleven targets, including `bluetooth-mock-parity`:

```
contracts-check          wifi-mock-parity         bluetooth-mock-parity
battery-mock-parity      speedtest-mock-parity
speedtest-no-new-architecture capture-test         ags-test
capture-hexagonal-gate   icons-json-drift
ansible-embedded-template-lint
```

Comparing them:

| gate (`gates-ci`) | CI job | status |
|---|---|---|
| `bluetooth-mock-parity` | — | **MISSING** |
| `contracts-check` | `contracts` | renamed |
| `capture-hexagonal-gate` | `capture-hexagonal` | renamed |
| everything else | same name | ok |

Two of the three differences are renames that a human reads past. The third is
the defect: the gate exists, is in the authoritative set, and no job runs it.

MEASURED: `bluetooth-mock-parity` was added to the `Makefile` by
`add-bluetooth-bar-popup` and has never had a CI job. It passes locally (19
states, 406 tokens) and has never once run on a push.

## §2 Why the header's claim did not hold

The workflow says it is "the place a future change cannot quietly drop one". That
is a statement about a *capability*, and no code implemented it. A comment cannot
enforce anything, and a hand-maintained list that is never compared to its
source of truth drifts the first time someone edits one side.

The repo already solved this shape twice and did not reuse it here:

- `bluetooth-mock-parity.py` grew an **orphan-cell check** after
  `popup-scanning-devices` was drawn in the mock and the gate said nothing —
  the mock was edited, the gate's `ANCHORS` list was not, and the contract was
  invisible rather than unenforced.
- `harden-capture-typecheck-config` pinned an ambient-type surface explicitly
  rather than relying on where a directory happened to sit on disk.

Same class: **a fact that is only true because nobody checked.**

## §3 The options

### Option A — add the job only (rejected)

Fixes today's symptom and re-arms the same trap. The next gate added to `GATES`
is dropped from CI by exactly the same inattention, and the header will still
claim otherwise.

### Option B — generate the workflow from `GATES` (rejected)

Attractive, and wrong here: the workflow carries per-job structure the Make
targets do not — `runs-on`, a `name:`, setup steps, and in some cases a reason
comment. Generating it would either lose that or require the Makefile to grow CI
metadata it has no business holding. The two lists are genuinely different
artifacts that must agree, which is a parity check, not a generation problem.

### Option C — a parity check, with declared renames (**chosen**)

A script that:

1. extracts the `gates-ci` targets from the `Makefile` (the authoritative set by
   the workflow's own statement), and
2. extracts the job keys from the workflow YAML,
3. compares them, resolving differences through an explicit **mapping table**
   for renames (`contracts-check → contracts`,
   `capture-hexagonal-gate → capture-hexagonal`),

and fails non-zero naming anything unmatched in either direction.

The mapping table is the same device `bluetooth-mock-parity.py` uses for
`CLASS_MAP`: a rename is a claim, so it is written down and reviewed rather than
inferred. A renamed job with no entry is a failure, not a pass.

It runs as a gate (`make ci-gates-parity`), needs no desktop stack (stdlib +
PyYAML via the provisioning env, like `icons-json-drift`), and belongs in
`gates-ci` itself — a gate that proves the gate list is complete has to be in the
list it is proving.

## §4 What "the same set" means, precisely

Both directions are checked, because each fails differently:

- **A gate with no job** — the `bluetooth-mock-parity` case: the gate runs
  locally and never on a push.
- **A job with no gate** — a job running a command that is not a gate, which is
  how a CI-only check becomes invisible to developers and drifts from the
  Makefile.

Extra CI jobs that are deliberately not gates (e.g. a setup or lint job that has
no `make` target) need a declared exemption with a reason, in the same table.
None exist today; the mechanism is there so adding one is a decision rather than
an accident.

## §5 Scope boundaries

Touches the workflow, the `Makefile`, and one new script. No runtime behaviour,
no provisioning outcome.

Explicitly **not** in scope:

- **Adding `capture-typecheck` / `bar-typecheck` to CI.** They cannot run there
  (no AGS, no Astal, no GTK4), the workflow header explains why at length, and
  this change does not relitigate that. It only makes the exclusion *stated*
  rather than *implicit in an absence*.
- **The trigger.** `push: branches: [main]` cannot fire because the default
  branch is `master`; the header already records that as repaired elsewhere. Not
  re-opened here.
