## ADDED Requirements

### Requirement: The gates workflow SHALL trigger on the branch that actually exists

`.github/workflows/gates.yml` SHALL trigger on `push` to `master`, the repository's default
branch (`origin/HEAD -> origin/master`), and SHALL continue to trigger on `pull_request`
without a branch filter so a PR from any branch is checked. It SHALL additionally offer
`workflow_dispatch`.

`main` does not exist in this repository, locally or on the remote, so
`push: branches: [main]` can never fire. A trigger naming a branch that does not exist is not a
weakened gate; it is a gate that has never run.

#### Scenario: A push to master runs the gates

- **WHEN** a commit is pushed to `master`
- **THEN** the `gates` workflow starts and all six of its jobs are scheduled

#### Scenario: A pull request still runs the gates

- **WHEN** a pull request is opened or its head branch is updated, from any branch
- **THEN** the `gates` workflow starts and all six of its jobs are scheduled

#### Scenario: The trigger no longer names a non-existent branch

- **WHEN** the workflow's `on.push.branches` list is read
- **THEN** it contains `master` and does **NOT** contain `main`

#### Scenario: A CI run can be reproduced on demand

- **WHEN** the workflow is dispatched manually from the Actions UI
- **THEN** the same six jobs run

### Requirement: CI SHALL run every gate that can run on a hosted runner

The workflow SHALL contain one job per CI-capable gate, so a failure names the gate that broke
instead of hiding behind a combined command's exit code. As of this change the set is exactly
the six gates in `make gates-ci`:

`contracts-check`, `wifi-mock-parity`, `speedtest-mock-parity`,
`speedtest-no-new-architecture`, `capture-hexagonal-gate`, `capture-test`.

#### Scenario: Each CI-capable gate has its own job

- **WHEN** the workflow's job list is enumerated
- **THEN** it contains exactly one job per gate in `make gates-ci`, each `runs-on: ubuntu-latest`

#### Scenario: capture-test runs without the desktop stack

- **WHEN** the `capture-test` job runs on `ubuntu-latest`
- **THEN** Node is pinned to a version whose built-in `.ts` type-stripping is unflagged (≥ 22.18),
      no `npm install` and no `ags types` step are present, and `make capture-test` executes
      `node --test` over the domain unit tests

#### Scenario: The capture hexagonal gate runs in CI

- **WHEN** the `capture-hexagonal-gate` job runs
- **THEN** `python3 scripts/capture-hexagonal-gate.py` exits 0 with check 6 reporting 33 used /
      28 styled class names

#### Scenario: The contract drift gate runs in CI

- **WHEN** the `contracts-check` job runs
- **THEN** `uv` is provisioned via `astral-sh/setup-uv` and `make contracts-check` exits 0

### Requirement: A gate that cannot run in CI SHALL be declared, not faked

`capture-typecheck` SHALL NOT appear in the workflow, because a hosted runner has no AGS, no
Astal and no GTK4 for `ags types` to introspect, its ~49 MB of generated `.d.ts` describe one
developer's machine rather than the runner, and its tolerated-third-party error bucket is keyed
to the literal path `/usr/share/ags/js/`, which does not exist on a runner — so listing it would
not make the gate stricter, it would make every push red on a gate that examined nothing.

The gate itself SHALL be left intact and SHALL remain runnable by a developer. The workflow and
the Makefile SHALL each state in prose that it is excluded because it cannot run in CI.

The governing rule: if a gate cannot run in CI, the honest statement is **"this gate does not
run in CI"** — never "this gate passes in CI" and never a skipped step that reports green.

#### Scenario: capture-typecheck is absent from the workflow

- **WHEN** the workflow's job list is enumerated
- **THEN** no job runs `make capture-typecheck` or `ags types`

#### Scenario: The exclusion is documented, not silent

- **WHEN** the workflow header or the `gates-ci` comment is read
- **THEN** it names `capture-typecheck` and gives the desktop-stack reason for its absence

#### Scenario: No gate is weakened to reach green

- **WHEN** this change is reviewed against the pre-change `scripts/` and `Makefile`
- **THEN** no gate's assertions, thresholds, ALLOWLIST entries or exit codes have changed, and
      no gate has been deleted, stubbed, or made to no-op

### Requirement: A developer SHALL still be able to run every gate with one command

`make gates` SHALL continue to run **all seven** gates, including the desktop-only one, in the
documented reviewer order. No gate is dropped for convenience from the developer set. The
CI/dev split SHALL be expressed as two named targets over a shared `GATES` variable, not as an
environment-conditional inside `gates`, so that a gate's assertions never depend on where it
runs.

#### Scenario: make gates runs all seven

- **WHEN** `make gates` is expanded
- **THEN** it expands to all seven gates including `capture-typecheck`, in the documented order

#### Scenario: make gates-ci runs the six CI-capable gates

- **WHEN** `make gates-ci` is expanded on a machine with no desktop stack
- **THEN** it expands to six gates and contains no `ags types` and no `npm install` command

#### Scenario: A local CI reproduction does not need the desktop

- **WHEN** `make gates-ci` runs in a clean checkout with no `node_modules/` and no `ags` on PATH
- **THEN** it exits 0 and every gate it ran reported its own result

#### Scenario: A developer is never misled about CI being dead

- **WHEN** the comment block above the `gates` target is read
- **THEN** it does **NOT** claim that the push trigger cannot fire, and it does **NOT** describe
      CI as absent or deferred

### Requirement: A skipped check SHALL be loud, not silent

Where a check genuinely cannot execute in a given environment, the gate SHALL print a named
`NOTE` explaining what was unavailable. A gate that silently no-ops is the failure mode this
repository's own `speedtest-no-new-architecture.py` docstring warns about, and a reduction in
what CI executes must be visible in CI output rather than inferred.

#### Scenario: The absent-TypeScript skip is named in CI output

- **WHEN** the `capture-test` job runs on a clean checkout where `node_modules/.bin/tsc` does
      not exist
- **THEN** the output contains `NOTE: typescript not installed, skipping the test-file
      typecheck` and the test run reports `skipped 1` — not a clean 115

#### Scenario: The skipped compiler-evidence test names itself

- **WHEN** `typecheck-config.test.ts` cannot resolve a `tsc` binary
- **THEN** it prints its own `NOTE` and calls `t.skip("typescript not installed")` so the skip
      appears in the test summary
