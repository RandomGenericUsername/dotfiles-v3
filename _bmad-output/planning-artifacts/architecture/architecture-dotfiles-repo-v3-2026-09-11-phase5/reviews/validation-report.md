# Phase 5 Architecture — Validation Report

**Intent:** validate (critique, no spine changes).
**Date:** 2026-09-11
**Spine:** `architecture-dotfiles-repo-v3-2026-09-11-phase5/ARCHITECTURE-SPINE.md` (status: final)
**Companion:** `contracts/event-contract.md` / `.json`

## Verdict

**NOT READY for story breakdown.** Mechanical lint passed (0 findings), but a
scaled reviewer gate returned **REJECT / CONDITIONAL REJECT** from every
judgment lens. The spine specifies a *single-converge correctness* model but
leaves the *contract semantics, recovery behavior, supervision, and trust
boundary* under-specified — enough that two AD-conformant units can build
incompatibly, and one CRITICAL internal contradiction makes the driving use case
(ICME save → regenerate) unimplementable as written.

## Method

`lint_spine.py` (0 findings) + 6 parallel lenses, each written to `reviews/`:

| Lens | File | Verdict |
| --- | --- | --- |
| Rubric walker | `review-rubric.md` | CONDITIONAL REJECT |
| Reality-check (floor) | `review-reality.md` | PASS WITH FINDINGS (1C/4H/5M/4L) |
| Adversarial-divergence (floor) | `review-adversarial.md` | REJECT |
| Operational / failure-mode | `review-operational.md` | REJECT AS WRITTEN |
| Trust & security | `review-trust.md` | FAIL (blocking) |
| Contract robustness | `review-contract.md` | REJECT |

---

## CRITICAL

**C1 — AD-36 forbids the very reaction AD-37/AD-42 require.**
AD-36: "the daemon reacts **only** to the watched root set." AD-37/AD-42: ICME
`icme.saved` → the daemon triggers regeneration. A file-watch-only trigger
surface makes the contract event an orphan, or violates AD-36. *(rubric,
adversarial)*
→ **Fix:** redefine the daemon's trigger surface as **watched roots ∪ authorized
domain-event topics**; AD-36 loops-safety applies to the root set only.

**C2 — `Job*` lifecycle signals have no producer path.**
The contract exposes only `Emit(topic, payload)`→`DomainEvent`; `JobStarted/
Progress/Finished` are hub-only signals, yet AD-37 says a lifetime job
"publishes lifecycle" and AD-38 says only the hub emits. Dead interface.
*(adversarial, contract, reality)*
→ **Fix:** pin one path — e.g. jobs call hub methods (`BeginJob/ReportJob/EndJob`)
and the **hub** emits `Job*`; the contract's method set must expose it.

**C3 — AD-38 caller→topic authorization is unenforceable on a session bus.**
Same-UID processes; unique names rotate; PID→exe is TOCTOU-unsound; policy XML
cannot match executables. Any same-user process can forge `icme.saved` /
`capture.state` / `Job*` and drive regeneration. There is no threat model.
*(trust, reality)*
→ **Fix:** decide the trust posture explicitly. Session-bus trust is *same-UID*;
make the guarantee real (hub-spawned jobs carry a capability cookie; hub validates
the cookie + sender), or **downgrade the claim** to "same-user trust; no
integrity guarantee beyond AD-30 floor." Do not assert an enforceable mapping you
cannot implement.

**C4 — AD-33 supervision does not do what it claims.**
`Restart=on-failure` never restarts a clean exit; `StartLimit` drops the unit to
`failed` on a crash-loop; `Type=simple` marks the unit active **before**
`org.dotfiles.Events` is acquired (active with no hub); no **session target /
environment import** → the daemon cannot reach the session bus or its reloaders.
*(reality, rubric, operational)*
→ **Fix:** use `Type=dbus` + `BusName=org.dotfiles.Events` (or `Restart=always`
with `StartLimitIntervalSec=0` + `RequestName(DO_NOT_QUEUE)` exiting non-zero on
loss), and bind the unit to `graphical-session.target` with the uwsm session env.

**C5 — No converge-on-start / recovery; downtime changes are lost forever.**
The last-converged hash backstop is **in-memory only** and polling is banned, so
any change made while the daemon was down is never reconciled. An unseeded daemon
hits `nothing to reconcile` → `Restart=on-failure` crash-loop → `failed` unit.
*(operational, contract, rubric)*
→ **Fix:** converge once on startup; persist the last-converged input hashes
(under `state_root`) so the first post-restart run repairs downtime drift; treat
"unseeded" as a benign no-op, never an error.

**C6 — AD-42's premise is already false.**
`shared-data-contract.md` pins `seed|set|reconcile|force`; shipped code enforces
six values (`+regenerate,+doctor`) in `reconcile.py`, `inspect.py`, `seeder.py`.
"no trigger value absent from the contract" cannot hold. *(rubric, reality)*
→ **Fix:** sync the shared-data-contract + add a cross-copy drift test **before**
adding `reactive`.

---

## HIGH

**H1 — Watched roots: recursion and coverage.** inotify is non-recursive, but
`icon-templates/` is nested (`<...>/status-bar/<app>/<variant>/icon.svg`) and
`canonical_hash_dir` hashes recursively → deep edits fire nothing. The watched
set also **omits the wallpaper bytes** (`sha256(file_bytes)` is a derivation
input), and calls `icon-mappings` a *file* where `shared-data-contract` says
*directory*. *(reality, adversarial, operational)* → bounded recursive watch;
include the wallpaper source; resolve dir-vs-file from the real repo.

**H2 — The daemon is not bound to the existing mutexes.** Nothing binds
`daemon run` to `.seed.lock` / `.history.lock` (only the memlog mentions it); a
separate composition root can race the CLI. *(operational)* → add an AD: the
daemon join the existing locks per action; never hold across sleeps.

**H3 — Crash between `current.json` save and history append.** Leaves permanent
store/history divergence; the unchanged-input backstop then *suppresses* repair
(AD-23 only heals torn tails). *(operational)* → extend doctor/verify to detect
store↔history divergence and repair it; the daemon must not assume its own last
write succeeded.

**H4 — Two same-user sessions share one `state_root`.** No session/seat identity,
so two compositors overwrite each other's monitor sets and cross-fire reloaders.
*(operational)* → scope state by session, or explicitly document single-session.

**H5 — Contract semantics absent.** Delivery (signals are at-most-once — a bar
starting mid-event misses `JobFinished`), ordering, `job_id` generation/scope/
lifetime across restarts, staleness/heartbeat, schema evolution (additive vs
breaking), `a{sv}` validation + size/depth limits, and `GetTopicState` authority/
retention/absence/restart are all unspecified. *(contract, adversarial, trust)*

**H6 — Hydrate-then-subscribe race.** No `seq`/generation and no subscribe-order
rule → lost updates permanently (polling banned). *(contract, adversarial)* →
subscribe-before-hydrate + per-topic monotonic `seq`.

**H7 — AD-19 misattributed.** Phase-2 AD-19 has no presence/absence/recovery
content (it defers daemons to Phase 5). Absence/recovery needs a Phase-5
invariant, not an inherited row. *(reality, rubric)*

**H8 — `capture.state` cannot rebuild the timer.** Payload is `{state}` only; no
monotonic start anchor, so the no-polling elapsed indicator is unimplementable
across bar/hub restarts. *(rubric, role, contract)* → add a start anchor (or a
`started_at` field/topic).

**H9 — `desired.json` relocation is incomplete.** No writer exists for it and the
reader still targets `state_root`; AD-39 wants it under `$XDG_CONFIG_HOME`.
*(reality)* → the relocation is a real story with a reader/writer move.

---

## MEDIUM / LOW (tail)

- GJS `a{sv}` needs `recursiveUnpack()` — document the consumer idiom. *(reality)*
- `Type=simple` + in-memory hub state: no re-announce after hub restart; consumers
  keep stale state. *(reality)*
- Unbounded `a{sv}` (size/depth) → memory exhaustion; no runtime validation.
  *(trust)*
- Audit flooding; `desired.json` is user-writable so `last-N` is attacker-tunable
  within the floor; regeneration cost unbounded. *(trust)*
- High-frequency `JobProgress` (speed test) needs coalescing/rate policy.
  *(contract)*
- `GetActiveJobs a{ss}` cannot express staleness. *(contract)*
- Observe-only → live promotion mid-session unspecified. *(operational, medium)*
- Log growth/rotation, uninstall/upgrade, watch limits (`max_user_watches`).
  *(operational, medium/low)*
- Hub is a single point of failure for signals *and* authorization. *(trust,
  operational)*

---

## Recommendation

Treat this as an **Update pass**, not a patch:
1. Resolve **C1–C6** (contradictions, supervision, recovery, trigger sync).
2. Decide the **trust posture** (C3) — enforce with a capability, or document
   same-UID trust honestly.
3. Specify **contract semantics** (H5/H6/H8) and revise `event-contract.json`
   with required/enum/range/limits + `seq` + job epoch.
4. Add Phase-5 invariants for **recovery/converge-on-start**, **lock participation**,
   **absence/recovery (replacing the AD-19 row)**, and **session scoping**.
5. Update the epics to make `desired.json` relocation and the contract-semantics
   work first-class stories.

Until then, **do not freeze epics/stories.**
