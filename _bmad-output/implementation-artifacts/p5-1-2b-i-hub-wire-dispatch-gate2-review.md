# Gate 2 Review — P5‑1‑2b‑i (Hub Wire Dispatch, jeepney)

Status: APPLIED — Items 1–3 resolved and verified (runtime 1151 passed,
2 skipped; layering green; contracts-check green; mypy --strict clean;
ruff no new; live re-smoke green, bus clean).

## Verification (DEV)

- New suites: dispatch 43 + conformance 8 passed. Full runtime suite:
  1147 passed, 2 skipped. Layering: 80 passed. Contracts-check: 15 passed.
- `mypy --strict` on the new adapter: clean (after a `jeepney.*`
  `ignore_missing_imports` override, same pattern as `fastjsonschema`).
  Whole-src mypy: 6 pre-existing, zero new.
- `ruff check`/`format` on touched files: clean except the 2 pre-existing
  B008 in `cli/main.py`.
- Live smoke (manual, deleted after): real session bus — acquire,
  BeginJob→job id, GetActiveJobs, full lifecycle, sink order, Emit→
  UnknownMethod loud, Introspect without Emit, release; plus live
  contention (reply code 3 → `BusNameContentionError`); bus clean after.
- `contracts/` diff: empty. Pre-existing dirt ignored (2 arch-prose files).

## Panel

- Blind Hunter (correctness): no blockers, 6 minors (all jeepney-API
  verified, incl. a live serialise/parse round-trip).
- Edge Hunter (edges): 3 majors + 5 minors, several reproduced by
  execution against the real code.
- Acceptance Auditor: AC2/3/4/5/6/7/8 MET; AC1 PARTIAL (jeepney shipped
  vs dasbus written — all sub-checks green); AC9 PARTIAL (gates green;
  snake↔Pascal seam doc missing). No scope creep, no leak. Verdict:
  **dasbus→jeepney pivot ACCEPTABLE without re-ballot** (story
  pre-authorized the fallback; `gi` absence evidenced) **conditional on
  a story amendment**.

## Findings → ballot items

### Item 1 (adapter correctness)

- **Redundant Hello (Blind #1 / Edge #2):** `DBusConnection.__init__`
  already Hellos (verified in jeepney source); the explicit Hello is a
  protocol duplicate whose error reply goes unchecked. **Patch:** delete
  the explicit Hello (constructor failure already maps to
  `BusUnavailableError`).
- **RequestName error-reply misclassified (Blind #2 / Edge #3):**
  error-type replies have no `u` body — `body[0]` misreads as
  contention. **Patch:** branch on `message_type`; non-`method_return`
  (or empty body) → close + `BusUnavailableError`.
- **Re-acquire serves nothing (Blind #3 / Edge #1):** `release()` sets
  `_stopped`, never cleared — second `acquire()` starts a stillborn
  thread and `wait()` returns instantly (silent readiness lie).
  **Patch:** `self._stopped.clear()` after ownership confirmed.
- **Unwrapped `_answer` kills the thread silently (Blind #4):** reply
  construction/serialization failures escape the thread function.
  **Patch:** wrap the `_answer` call in try/except-log (loop continues).
- **Bus-death silence (Blind #5):** `OSError → break` covers release
  (correct) and bus death (silent park on a dead name). **Patch:** log
  + `self._stopped.set()` + break (release already set it — still
  correct).
- **Foreign interface dropped (Blind #6 / Edge #5):** our-path +
  foreign-interface gets no reply (caller hangs to its own timeout),
  contradicting "never dropped silently". **Patch:** reply
  `UnknownMethod` (wrong-path ignore stays).
- **Arity mismatch misnamed (Edge #4):** existing method + wrong arg
  count should be `InvalidArgs`, not `UnknownMethod`. **Patch:**
  one-line error-name swap.
- **Hot-spin on persistent receive failure (Edge #8):** non-OSError
  every iteration → log-spam/CPU loop. **Patch:** small sleep in the
  generic handler.
- **Defensive `None` shapes (Edge #7):** `dispatch(member, None)` →
  bare `TypeError`. **Patch:** `WireError(InvalidArgs)` guard at entry.

### Item 2 (docs + comments)

- **snake↔Pascal seam table (Auditor AC9):** the mapping
  (`job_started`→`JobStarted`, …; `job_adopted`/`pid` dropped on the
  wire) lives only in domain prose, not at the wire seam.
  **Patch:** ~6-line table in the adapter docstring/head comment.
- **Width-before-identity deviation note (Edge #6):** `AdoptJob`/
  `EndJob` check widths before liveness (both loud typed errors, wire
  impact nil, but contradicts the domain's documented order).
  **Patch:** one-line comment at both call sites.
- **Story amendment (Auditor deviation a):** AC1 + Dev Notes + Gate-1 Q2
  must record jeepney-won/dasbus-rejected with the `gi` evidence
  (ModuleNotFoundError in the hermetic venv, breaking both tests and
  the deployed tool env).

### Item 3 (tests)

- Re-acquire serves again (acquire→release→acquire dispatches).
- Hello-failure → `BusUnavailableError` (scripted error reply).
- RequestName error reply → `BusUnavailableError`, not contention.
- Foreign interface on our path → `UnknownMethod` reply (assert via
  `_answer` with a scripted message + recording conn).
- Arity mismatch → `InvalidArgs`.
- `dispatch(member, None)` → `WireError(InvalidArgs)`.

### Declined with rationale (no action unless you object)

- Second Hello as belt-and-braces (deleted instead — constructor owns it).
- `wait-then-release` reuse guard beyond `_stopped.clear()` (clear
  restores full semantics; single-use documentation unnecessary).
- `receive()` returning `None` guard (jeepney never does; over-defensive).
- Per-message `sender` allowlisting (AD-38 forbids identity
  authorization; structural-only stands).
- Retrying `RequestName` code 2/in-queue (correctly treated as
  contention/fail-fast under DO_NOT_QUEUE).
- 10k-job perf, `METHODS` mutation, empty-METHODS XML (assessed benign).

## Ballot (Approve / Request-changes PER ITEM — nothing applied yet)

- Item 1 (adapter correctness batch)?
- Item 2 (seam table + deviation notes + story amendment)?
- Item 3 (six tests)?
