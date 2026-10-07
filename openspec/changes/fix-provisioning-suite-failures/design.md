# Design: fix-provisioning-suite-failures

## §1 Baseline — establish it, do not inherit it

Run the suite and capture the failures with their names:

```bash
uv run --directory src/provisioning pytest -q > /tmp/pytest.txt 2>&1
grep -E "^(FAILED|ERROR)" /tmp/pytest.txt
tail -3 /tmp/pytest.txt          # the pass/fail/skip counts
```

TIMING: the suite exceeds 15 minutes on this machine (a 900 s run reached ~50%),
so run it in the background or with a generous timeout. That itself is a finding
worth recording — a developer feedback loop that cannot complete inside a
reasonable window is part of why the failures went unwritten.

Then, for each failure, run it alone and capture the assertion:

```bash
uv run --directory src/provisioning pytest <nodeid> -q
```

**Record the list in this file before changing anything.** The proposal names
reported failures that are unverified; if the measured list differs, the measured
list wins and the proposal's note is corrected in place (house style —
`harden-capture-typecheck-config` did the same to its own reported blast radius).

## §2 The classification, and why it decides the fix

Every failure goes in exactly one bucket, and the bucket selects the fix:

| bucket | meaning | fix |
|---|---|---|
| **A — real defect** | the test asserts something true that the code does not do | fix the code; the test was right |
| **B — environment-dependent** | the test needs infrastructure a stock runner lacks (a pty, an X display, a GIR typelib, runtime icons) | make it hermetic, or skip it *explicitly* with a reason |
| **C — wrong test** | the test encodes an assumption that is no longer true | fix the test, and say what changed |

The buckets are not cosmetic. A is the only one that changes shipped behaviour; B
is the one that misleads CI; C is the one that hides a real regression behind a
stale expectation. Treating them uniformly — "just make the suite green" — is how
a real defect gets skipped along with the environmental noise.

### The reported shape, unverified

The implementing agent reported:

- 2 × `tests/integration/test_btop_theme_e2e.py` — needs a real pty / theme load
- 4 × `tests/unit/test_verify_role.py` — expects runtime icons under a synthetic
  state-home

If that holds, all six are bucket B, and the change is about hermeticity rather
than behaviour. **Do not assume it.** `test_verify_role` in particular is worth
reading closely: it asserts on the verify role, and a test that fails because
icons are missing may be telling the truth about a fragile assumption.

## §3 What "hermetic" means here, concretely

Bucket B has three honest endings, in order of preference:

1. **Supply the missing thing in the test's own fixture** — a tmp state-home with
   the icons the assertion needs, a fake pty, an injected clock. The test then
   proves the same thing everywhere.
2. **Skip with a machine-readable reason** (`@pytest.mark.skipif(...)` or
   `pytest.skip("needs a real pty: ...")`) so the skip *count* is visible and the
   reason is in the output. A silent `return` or a deleted test is not this.
3. **Move it behind an explicit marker** (e.g. `-m integration` deselect) when it
   genuinely cannot be made hermetic, with the marker documented in the suite's
   README/comment so CI's selection is a stated choice.

Deleting the test or weakening its assertion to pass is **not** an option in any
bucket. That is the failure mode the repo keeps hitting: a green signal that no
longer means anything.

## §4 Scope boundaries

- **Not** a provisioning behaviour change. If bucket A turns out non-empty, that
  is a real defect discovered *by* this change; it is fixed here and named in the
  report, or split out if it deserves its own change.
- **Not** a rewrite of the suite or a change to how it is invoked.
- **Not** the `INJECT_FACTS_AS_VARS` deprecation. Verified separately as not
  firing: `verify` emits zero warnings today because the tree's structural test
  forbids bare facts. Recorded so it is not swept in here.
