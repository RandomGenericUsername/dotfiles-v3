# Design: fix-provisioning-suite-failures

## §1 Baseline — establish it, do not inherit it

Run the suite and capture the failures with their names:

```bash
uv run --directory src/provisioning pytest -q > /tmp/pytest.txt 2>&1
grep -E "^(FAILED|ERROR)" /tmp/pytest.txt
tail -3 /tmp/pytest.txt          # the pass/fail/skip counts
```

MEASURED on `master` @ `5531cde2`:

```
6 failed, 792 passed, 5 skipped in 1198.45s (0:19:58)
```

The suite takes **19m58s**. That is part of the finding: a feedback loop that
does not fit in a sitting is part of why these went unwritten.

Confirm the list is unchanged before starting (rerun in the background), then for
each failure run it alone and capture the assertion:

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

### The measured shape

All six are named in `proposal.md`. The two `test_btop_theme_e2e` failures need a
real pty (theme loading and a visible repaint). The four `test_verify_role`
failures all fail through a done-criterion that expects **rendered runtime icons**
under a synthetic state-home, and the criterion's own message is informative:

```
the runtime icons output is missing: expected
  /tmp/.../state-home/dotfiles/current/icons/ as a directory with each of
  battery-0.svg, settings-panel-wifi.svg, volume-low.svg, ... bluetooth-off.svg
  present (done-criterion — runtime icons, Epic 4 current-only).
  Run `dotfiles-runtime wallpaper set`
```

Note what that says: the icons provisioning role is **deleted**, and runtime
icons are now produced by the wallpaper pipeline. So the four are not obviously a
test-fixture problem — they may be telling the truth about a criterion that
outlived the thing that fed it. That is why classification is a task and not an
assumption; read each one before assigning a bucket.

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
