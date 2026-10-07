## Why

`uv run --directory src/provisioning pytest` does not finish green on a
provisioned desktop. The failure count has been carried as "known, pre-existing"
without ever being written down, so every change that touches provisioning
re-measures it from scratch and every reviewer has to take "pre-existing" on
trust.

> **The exact count and identities are UNCONFIRMED at the time of writing.** An
> agent implementing an unrelated change reported **792 passed / 6 failed / 5
> skipped**, splitting the six as 2 × `tests/integration/test_btop_theme_e2e.py`
> and 4 × `tests/unit/test_verify_role.py`, and reported reproducing all six with
> its own diff stashed. A confirming full run is in flight. **Task 1 is to
> establish the list from the machine**, and every later task depends on it.
> Do not build on the reported split.

The reported shape is that the failures are **environment-dependent rather than
code defects**: tests that need a real pty (theme loading) and tests that expect
runtime icons to exist under a synthetic state-home. If that holds, the defect is
that the suite's success depends on ambient machine state rather than on the
repository — which is the same class as `harden-capture-typecheck-config` (an
app's ambient type surface depending on where a directory sat) and the
`bar-typecheck`/`capture-typecheck` symlink omissions.

## What Changes

- **Measure the list, then fix, don't re-guess it.** Phase 1 establishes exactly
  which tests fail, why, and whether each is a defect in the test, a defect in
  the code, or a legitimate environment dependency.
- **Classify each failure** as one of: the test asserts something true that the
  code does not do (a real defect → fix the code); the test needs infrastructure
  a stock runner lacks (→ make it hermetic, or skip it *explicitly* with a reason
  and a marker); or the test is simply wrong (→ fix the test).
- **Nothing is silenced by deletion.** A test that cannot run everywhere is
  skipped with a stated reason and a shape that CI can see, never removed and
  never weakened to pass.

## Capabilities

### New Capabilities

- `provisioning-suite-determinism`: the provisioning test suite's result depends
  on the repository, not on the ambient state of the machine it runs on — every
  skip and every failure is explained, and the count is written down.

### Modified Capabilities

- *(none — this change fixes test infrastructure, it does not change what
  provisioning does)*
