# Gate 2 Review — P5‑1‑2a (Hub Registry + Leases + Epoch)

Status: APPLIED — Items 1–3 resolved and verified (runtime 1096 passed,
2 skipped; layering green; contracts-check green; mypy --strict clean on
new files; ruff no new).

## Verification (DEV)

- Hub suite: 29 passed. Full runtime suite: 1089 passed, 2 skipped.
- Layering: 80 passed. `make contracts-check`: 15 passed.
- `mypy --strict` on the 3 new source files: clean. Whole-src `mypy src`:
  6 pre-existing errors, zero new.
- `ruff check` on the 4 new files: **6× N818** (see Item 1m — a
  story-vs-lint conflict, not a code bug). Tree-wide ruff noise otherwise
  byte-identical on stash. Format clean.
- `contracts/` diff: empty (verified).

## Panel

- Blind Hunter (correctness): 2 majors (sink-raise partial mutation;
  unbounded ended-record retention), 10 minors. No blockers.
- Edge Hunter (edges): 1 blocker (re-entrant sink crashes `_sweep` —
  reproduced), 3 majors, 10 minors. Two findings reproduced by execution
  (sweep crash, unhashable action).
- Acceptance Auditor: AC2/AC4/AC6/AC7 MET; AC1/AC3/AC5 PARTIAL (test pins
  only); AC8 PARTIAL (N818 + uncommitted scope). No scope creep, no
  out-of-scope leak, Gate-1 recs 1–6 all visible.

## Findings → ballot items

### Item 1 (code + doc hardenings)

- **Re-entrant sink crashes `_sweep` (Edge blocker, reproduced):** a sink
  calling `hub.begin()` during sweep mutates the dict mid-iteration →
  `RuntimeError`. **Patch:** iterate a snapshot —
  `for job_id, record in list(self._jobs.items()):`.
- **Sink-raise partial mutation (Blind major / Edge major):** `begin`
  orphans a live job, `end` loses the finish, sweep aborts mid-loop when
  the sink raises. Production (`logger.debug`) and test (`list.append`)
  sinks cannot raise; 2b's future D-Bus emitter can. **Patch (documented
  precondition, not rollback):** state on `EventHub` that the sink must
  not raise (infallible by construction — same standing as a non-raising
  clock); 2b owns emitter infallibility (queue-then-emit or emit outside
  the registry). Rollback discipline was considered and rejected as
  complexity against a broken-seam trigger.
- **Unhashable `action` leaks `TypeError` (Blind minor / Edge major,
  reproduced):** `control(job, ["pause"])` raises instead of
  `NotControllable`. **Patch:** `isinstance(action, str)` guard (mirrors
  the existing `job_id` guard).
- **`id_factory` output unvalidated + unbounded collision loop (Blind
  minors / Edge minors):** non-str/empty ids stored unreachable;
  constant-collision factory hangs. **Patch:** validate
  (`isinstance str` + non-empty → else `RuntimeError`) and bound retries
  (100 → `RuntimeError("id_factory exhausted")`).
- **`ttl=0` docstring overstates (Blind minor):** it survives `begin`,
  dies on the next call. **Patch:** correct the `_sweep` docstring.
- **Allowlist aliasing (Blind minor / Edge minor):** default branch shares
  the global dict. **Patch:** always `dict(CONTROL_ALLOWLIST)` copy.
- **Reserve `-1` exit code (Blind minor / Edge major):** explicit
  `end(job, -1)` is byte-identical to synthetic expiry in the sink.
  **Patch:** reject `-1` in `_validate_exit_code` (`ValueError`); the
  synthetic path writes the constant directly, unaffected.
- **Single-threaded caller note (Blind minor):** 2b dispatch threads must
  serialize. **Patch:** document on the class.
- **Wire-width conversion note (Blind minor / Edge minor):** `float` ttl
  and unbounded ints are 2a-domain; 2b validates `u32`/`i32`.
  **Patch:** note the rule in the port docstring.
- **Emit-side error details (Blind minor):** `UnknownTopic`/
  `PayloadTooLarge`/`RateLimited` are bare vs the story's "carrying
  detail". **Patch:** constructors with `topic`/`detail` attrs mirroring
  the siblings.
- **Contract-name alignment (Blind minor):** `job_kind` → `kind` (matches
  the `JobStarted` member); explicit 2b mapping note (snake_case tags vs
  PascalCase signals; `job_adopted`/`pid` have no wire signal — 2b drops
  them, ownership trail stays in-process).
- **N818 vs contract names (Auditor AC8):** the six typed errors MUST keep
  contract-exact names (approved story) but ruff N818 demands `*Error`.
  **Patch:** `# noqa: N818` on each with a contract-mandate comment
  (minimal; no pyproject rule change).
- **`begin` sweeps after validation (Edge minor):** invalid calls skip
  lazy expiry, contradicting "every public entry". **Patch:** move
  `self._sweep()` above validation in `begin`.
- **Huge-int ttl `OverflowError` (Edge minor, reproduced):** `float(10**400)`
  escapes as `OverflowError`, not the documented `ValueError`.
  **Patch:** wrap the conversion.
- **`-0.0` normalization (Edge minor):** record `float(fraction) + 0.0`.
- **Single clock sample (Edge minor):** thread `now` through
  `_sweep(now)`; `renew` reuses it for the deadline.
- **Retention policy (Blind major):** ended records are kept forever (the
  `JobEnded`-vs-`UnknownJob` distinction requires it). **Patch:** document
  intentional unbounded retention + follow-up note (a future `ForgetJob`
  or bounded LRU would change tested semantics — out of 2a scope).

### Item 2 (tests)

- `report_progress` with an unknown string id → `UnknownJob` (AC1 gap).
- `adopt` after expiry → `JobEnded` (AC3 gap).
- `control` on expired-but-unswept → `JobEnded` (Edge coverage gap).
- Stale id on a NEW hub instance → `UnknownJob` (AC5 restart pin).
- `epoch` asserted on the synthetic-expiry record (AC5 minor).
- Unhashable action → `NotControllable`; non-str factory output →
  `RuntimeError`; `end(job, -1)` → `ValueError` (pair with Item 1).

### Item 3 (docs)

- Story: status done + Gate 2 outcome at commit time. Review doc: status
  APPLIED at commit time.

### Declined with rationale (no action unless you object)

- Full rollback discipline for raising sinks (chose the documented
  precondition; infallible sinks in 2a; 2b owns emitter design).
- TTL magnitude cap (after inf/overflow rejection, residual float fuzz is
  inherent; `ttl:u` bounds arrive with 2b validation).
- Registry eviction/`ForgetJob` now (would break the tested
  second-End-→-`JobEnded` contract; follow-up owns it).
- Renew sink record (renewals aren't lifecycle transitions — no contract
  signal exists for them; "every state change" read literally overclaims,
  story frames the sink as lifecycle records).
- 10k-job O(n²) sweep (fine at daemon scale; bulk-begin is not a path).

## Ballot (Approve / Request-changes PER ITEM — nothing applied yet)

- Item 1 (code + doc hardenings)?
- Item 2 (eight tests)?
- Item 3 (landing updates at commit time)?
