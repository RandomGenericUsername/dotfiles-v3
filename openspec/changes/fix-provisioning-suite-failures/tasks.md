## 1. Measure — before touching anything

- [x] 1.1 Run the suite and capture failures by name (background it; it exceeds
      15 minutes):
      ```bash
      uv run --directory src/provisioning pytest -q > /tmp/pytest.txt 2>&1
      grep -E "^(FAILED|ERROR)" /tmp/pytest.txt
      tail -3 /tmp/pytest.txt
      ```
- [x] 1.2 Confirm the recorded baseline still holds. It is MEASURED, not
      inherited: 6 failed / 792 passed / 5 skipped in 1198.45s, with all six
      nodeids named in `proposal.md`. If a rerun differs, correct the proposal
      **in place** — the measurement wins.
- [x] 1.3 For each failure, run it alone and capture the assertion text.
- [x] 1.4 Confirm the suite's runtime. If it exceeds ~15 minutes, record by how
      much — the length of the feedback loop is part of why these went unwritten.

## 2. Classify every failure

- [x] 2.1 Put each failure in exactly one bucket (design §2): **A** real defect,
      **B** environment-dependent, **C** wrong test. Write the bucket and the
      one-line reason next to each nodeid in `design.md`.
- [x] 2.2 For any bucket B, name the missing infrastructure precisely (a real
      pty, an X display, a GIR typelib, runtime icons under a state-home).
      "Flaky" is not a classification.
- [x] 2.3 For any bucket A, stop and report it before fixing — a failing
      assertion about shipped behaviour is a finding, not a test problem.
      (No bucket A found: shipped code is self-consistent.)

## 3. Fix, by bucket

- [x] 3.1 **Bucket A** — fix the code so the assertion holds. The test was
      right. Name the defect in the report. (Bucket A empty.)
- [x] 3.2 **Bucket B, preferred** — supply the missing thing in the test's own
      fixture (tmp state-home seeded with the icons the assertion needs; a fake
      pty; an injected clock) so the test proves the same thing everywhere.
      (No bucket B; the same "seed it in the fixture" shape was applied to the
      drifted bucket-C fixture.)
- [x] 3.3 **Bucket B, fallback** — an explicit skip with a stated reason and a
      marker, so the skip count and the reason are visible in output. Never a
      silent return, never a deletion. (Not needed — no skips added.)
- [x] 3.4 **Bucket C** — fix the test and say what changed underneath it. A test
      encoding a stale assumption is hiding whatever replaced it.
- [x] 3.5 **Prove each fix bites.** For a test you made hermetic, break the thing
      it asserts and confirm it still fails — a test that passes by no longer
      checking anything is the failure mode this repo keeps hitting.

## 4. Verify

- [x] 4.1 The suite is green, with an explicit skip list whose reasons are
      visible in the output.
- [x] 4.2 The counts in `design.md` are updated to the post-fix reality, not left
      as the baseline.
- [x] 4.3 `make gates` exit 0 and `make gates-ci` exit 0.
- [x] 4.4 Re-run the whole suite a second time and confirm the same result — a
      determinism change that is itself non-deterministic is not done.
- [x] 4.5 Confirm no test was deleted and no assertion was weakened. Diff the
      test files and read it; state the result either way.

## 5. Record

- [x] 5.1 The final pass/fail/skip counts, in `design.md`, in the place a future
      reader will look before re-measuring.
- [x] 5.2 Every skip and its reason, so "5 skipped" is never again an unexplained
      number.
- [x] 5.3 The suite runtime, if it changed materially.
