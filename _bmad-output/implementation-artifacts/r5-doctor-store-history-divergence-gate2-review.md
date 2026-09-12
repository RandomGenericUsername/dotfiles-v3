# Gate 2 Review — R‑5 (Doctor Store↔History Divergence)

Status: APPLIED — Items 1–3 resolved and verified (1039 passed, 2 skipped;
layering green; contracts-check green; ruff/mypy no new).

## Verification (DEV)

- Full suite: 1030 passed, 2 skipped. Targeted (doctor check/repair/tail): 68 passed.
- Layering (`tests/architecture/test_layering.py`): 75 passed.
- `make contracts-check`: 15 passed.
- `ruff check` on touched files: 2 errors (B008 `typer.Option` in `cli/main.py`) —
  proven pre-existing (identical on `git stash`). `ruff format`: all 4 touched
  files clean (only my new lines needed collapsing; applied).
- `mypy src`: 6 errors in 3 files, proven pre-existing (identical on stash;
  only a line-number shift from my +2 CLI lines). No doctor/inspect errors.
- Pre-existing dirt (NOT mine, untouched): `shared-data-contract.md` (+6) and
  Phase 5 `ARCHITECTURE-SPINE.md` (1 word) were already modified before R-5
  DEV started; they stay out of the R-5 commit.

## Panel

- Blind Hunter (correctness): no blockers, 4 minors.
- Edge Hunter (edge cases): 2 majors (TOCTOU duplicate append; history-ahead
  rewind), 6 minors, rest handled-verified.
- Acceptance Auditor: AC1 MET; AC2/AC3/AC4/AC5 PARTIAL (test-coverage gaps
  only — no implementation gaps except Item 1 below).

## Findings → ballot items

### Item 1 (code) — pre-append tail re-verify (Blind #1 + Edge major #2)

**Problem:** `_repair_history_only` classifies on the (instantly stale)
`check()` report and appends unconditionally. If a concurrent writer
converged store+history between `check()` and the append, repair appends a
redundant duplicate `doctor` line; if an `apply` saved a newer store in
between, the re-read store is still correct (fresh `load_current`), but the
duplicate-line case is real.

**Proposed patch:** after `load_current()`, re-read the tail
(`InspectHistoryUseCase.run(limit=1)`), rebuild the 4-hash projection, and
when it already agrees return `RepairResult((), (), None, (),
history_tail_quarantined=tail)` instead of appending. Plus a test with a
fake diverged-report doctor over agreeing store+history asserting no append.

### Item 2 (tests) — close the Auditor coverage gaps

**Gaps (all test-only, AC-pinned):**
- (a) torn tail tolerated THROUGH `DoctorUseCase.check` (AC2) — reader suite
  covers the reader, not the doctor leg.
- (b) `effects`/`icons` payload-matches-store assertions in the pure-repair
  test (AC3 — currently only wallpaper/palette asserted).
- (c) `current/` symlinks untouched pin (before/after link-target snapshot)
  in the pure-repair test (AC3 — reload + generator non-invocation already
  pinned).
- (d) `trigger="reactive"` tail stays clean (AC4 names it explicitly).
- (e) `source_path`-differing tail stays clean (AC4 names it explicitly).
- (f) same-trigger line differing only in `details` stays clean (AC4
  isolation; currently bundled with a prune-trigger change).
- (g) zero-mutation `diverged-history`/`absent-history` params (AC5 —
  proves check has no heal/append side-effect when the new leg fires).
- (h) store-vanishes-between-check-and-append → `RuntimeError` (Edge minor;
  reachable, untested).
- (i) repair-path corrupt-middle line → `ValueError` propagates, nothing
  quarantined/appended (Edge minor; untested on the repair path).

**Proposed patch:** add the nine tests (a)–(i). No production-code change.

### Item 3 (docs) — story file landing updates

**Problem:** story still reads `Status: draft (Gate 1 pending)`, all 7 task
boxes unticked; task text cites `ok`/`diverged`/`missing` vocabulary while
the approved Gate-1 rec implements absent→`diverged` (no `missing` emitted
for `kind="history"`).

**Proposed patch:** at commit time, mark status done, tick the boxes, record
the Gate 2 outcome, and reconcile the vocabulary note (absent→`diverged`
per Gate-1 rec). No code change.

### Declined with rationale (no ballot action unless you object)

- **Input-kind dirt escalates to full reconverge (Blind #3):** preserves
  pre-R-5 semantics (any non-clean report reconverges); narrowing
  `other_dirty` to entry/symlink would change long-standing behavior for
  unactionable input dirt — out of R-5 scope.
- **No post-append full re-check (Blind #2):** consistent with the existing
  full path, which also never re-verifies; the next `check()` catches
  residual dirt. No over-claim beyond what repair already does today.
- **Fallback-path weight (Blind #4):** dead in prod (CLI injects both
  seams); documented in the docstring; keeps backward-compatible ctor.
- **History-ahead direction detection (Edge major #1):** indistinguishable
  by design (comparison is symmetric; `applied_at`/`ts` can't order it);
  store-wins was the approved Gate-1 rec (decision 2) with 3-to-1
  corroboration (store+cache+links vs tail); append-only log preserves the
  superseded record. No code change possible without a schema change
  (`details` is closed-shape per R-1/R-4).
- **Case-insensitive hash compare (Edge #10):** self-healing (one diverged
  verdict → store-case append → clean); only reachable via hand-edited
  history.
- **`errno` preservation (Edge #16):** the wrap lives in R-1's
  `seeder.append_history` seam — pre-existing, out of scope.
- **CLI "quarantined 0, regenerated none" text (Edge #20):** identical text
  already renders today for symlink-only full repairs; special-casing would
  change existing output.
- **Apply-window transient (Edge #13):** self-converging (both lines agree);
  noted here, no code change.
- **Clean-after-real-reconcile (Auditor AC4 gap):** already covered —
  `test_pure_divergence_repaired_by_single_doctor_line` asserts
  `check_clean()` immediately after `_Env.apply()` (real apply +
  reconcile), and `test_second_repair_is_noop` pins post-repair clean.

## Ballot (Approve / Request-changes PER ITEM — nothing applied yet)

- Item 1 (pre-append tail re-verify + test)?
- Item 2 (nine Auditor/Edge coverage tests (a)–(i))?
- Item 3 (story landing updates at commit time)?
