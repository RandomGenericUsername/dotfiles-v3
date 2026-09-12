# Integration Edge-Case Re-Validation — Phase 5 Reactive Runtime (`reval-integration`)

- **Reviewer:** integration edge-case hunter, no prior context
- **Date:** 2026-09-11
- **Subject:** `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-09-11-phase5/ARCHITECTURE-SPINE.md` (AD-33..AD-44), `contracts/event-contract.md|json`, `epics-dotfiles-runtime-phase5.md`, and the **actual** Phase-4 runtime code.
- **Method:** for the daemon↔existing-machinery seam, trace the exact code path the spine implies (which use case runs, which lock is taken, what is hashed, what a crash leaves behind) and compare it to the spine's text. A finding is genuine only if a conformant implementation of the spine either cannot work against the shipped code or reproduces a defect the spine does not decide.
- **Constraint:** reviewer does not edit the spine. Findings only.
- **Scope note:** this is the last of the `reval-*` pass; where a prior review already owns a gap it is labelled `[covered: X]` and not counted in the top five. The five findings below are the **genuinely new / materially corrected** integration gaps.

**Verdict: REJECT AS WRITTEN for the daemon-integration seam — one HIGH self-deadlock trap, one HIGH missing converge use case, three MEDIUM/HIGH unpinned integration decisions. All are local spine/contract amendments; none requires reversing a settled decision.**

---

## 1. Direct answers to the integration questions

| # | Question | Answer (traced) |
| --- | --- | --- |
| Q1 | Which use case exactly runs on a daemon converge? | **Unspecified in the spine, and the two candidate use cases are not interchangeable.** Plain `reconcile` converges to *recorded* state (`reconcile.py:336-386` only regenerates on a missing/incomplete entry) and **cannot** regenerate a complete-but-stale entry: its AC-6b guard `_assert_hash_matches` (`reconcile.py:345,362,382`) raises when a re-derived entry hash differs from the recorded one. Only `RegenerateStaleUseCase` re-derives on input change (`regenerate.py:79-123`, via `CheckInputsUseCase`). The spine never names it. |
| Q2 | Does one trigger cover all derivations? | **For the four spine inputs, yes — via `regenerate`:** `CheckInputsUseCase` reports palettes/effects/icons stale in one pass (`check_inputs.py:56-83`), and `regenerate` handles the structural icons⇄palette cascade (`regenerate.py:110-117`). But a second, disjoint trigger surface (intent/`desired.json`) drives wallpaper+prune convergence, which `regenerate` never runs (see F2). One hash covers all four derivation inputs; it does **not** cover intent. |
| Q3 | Does a spine-input change actually cause regeneration today? | **Not on any automatic path.** There is no watcher/daemon in the repo (`src/runtime/src/runtime/daemon/` does not exist; only `contracts/` and planning docs mention it). Regeneration exists and works, but only behind the manual flag `reconcile --regenerate-stale` → `_run_regenerate_stale` (`main.py:663-737,1096-1139`). Plain `reconcile` repoints to existing cache entries; it does not re-derive. A Phase-5 story must wire "input changed → regenerate"; the spine does not name the unit. |
| Q4 | Lock participation: does the daemon hold `.seed.lock` / `.history.lock` or race it? Re-entrancy/self-deadlock? | **AD-35's wording invites a self-deadlock, and nothing in the code prevents it.** `flock` is per open-file-description, non-reentrant; `FlockSeedMutex.hold()` opens a fresh fd each call (`flock_seed_mutex.py:54-64`), so a second `LOCK_EX` in the **same process** blocks. `reconcile` acquires `.seed.lock` internally, blocking (`reconcile.py:183`), and `append_history` acquires `.history.lock` internally (`seeder.py:848`). The existing code explicitly warns about the pattern: "The lock is RELEASED before `reconcile.run()` (which locks internally; nesting flock acquisitions deadlocks)" (`regenerate.py:23-24`). See **F1**. |
| Q5 | Partial converge: does converge-on-start + the input-hash backstop repair it? | **No — and the spine itself says the backstop hashes *inputs*.** If a crash leaves `current.json` saved but history/reload incomplete (order: repoint → save → history → reload, `reconcile.py:234-300`; guarded save → reconcile, `regenerate.py:152-123`), the next start recomputes input hashes, finds them unchanged, and skips. `[covered: review-operational F4 / reval-operational R-3]`. The additional code fact: `doctor` — which AD-41 (`SPINE:92`) says detects/repairs `current.json`↔history divergence — **cannot** detect it; see **F3**. |
| Q6 | Persisted backstop vs existing cache/state: what is hashed, where stored, does a format change migrate? | **Unspecified, and the only existing hash API omits intent.** `[covered: reval-adversarial Scenario 4]` for path/schema/version. New code fact: `IInvalidationQuery.recompute_input_hashes()` hashes only the four derivation inputs and returns `wallpapers: None`, with no intent key (`invalidation.py:139-159`); `desired.json` is a watched root (AD-39) but is **not** in that hash. See **F5**. |
| Q7 | Concurrent CLI `wallpaper set` vs daemon converge; the seed path. | **Serializes correctly at the write, with two caveats.** `apply` and `reconcile` both take `.seed.lock` blocking around the RMW (`apply_wallpaper.py:182`, `reconcile.py:183`); derivation runs outside; `reconcile` re-derives inside the lock if the wallpaper hash changed while it derived (`reconcile.py:188-204`). Caveats: (a) `regenerate`'s CAS aborts loud on wallpaper drift (`regenerate.py:152-161`) — the daemon must retry, not fail; (b) seeding takes the lock **non-blocking** (`seed_cache.py:157`), so a daemon that wrongly holds `.seed.lock` across a converge makes a concurrent first-run `seed` fail (`main.py:173-174`). |

---

## 2. Findings

### F1 — HIGH — AD-35's "daemon joins `.seed.lock` / `.history.lock` per action" self-deadlocks against use cases that acquire the same flock internally

**Evidence.**
- AD-35 (`ARCHITECTURE-SPINE.md:51`): "The daemon **joins the existing `.seed.lock` / `.history.lock` per action**, never holding a lock across sleeps."
- `FlockSeedMutex.hold()` / `FlockHistoryMutex.hold()` call `os.open()` on every invocation (`flock_seed_mutex.py:54`) and then `fcntl.flock(fd, LOCK_EX…)` (`:58,60`). Linux `flock(2)` treats each open file description independently: *two fds in the same process can block each other.* There is no reentrancy guard.
- The use cases already acquire those locks internally: `ReconcileDesktopStateUseCase` holds `.seed.lock` blocking (`reconcile.py:183`); `ApplyWallpaperUseCase` likewise (`apply_wallpaper.py:182`); `CacheSeeder.append_history` holds `.history.lock` (`seeder.py:848`).
- The codebase documents the trap: "The lock is RELEASED before `reconcile.run()` (which locks internally; **nesting flock acquisitions deadlocks**)" (`regenerate.py:23-24`).
- A daemon that follows AD-35 literally wraps an action such as:

  ```python
  with FlockSeedMutex(state_root / ".seed.lock").hold(blocking=True):
      ReconcileDesktopStateUseCase(...).run(trigger="reactive")   # blocks forever at reconcile.py:183
  ```

  The result is not a crash — it is a **wedged process that still owns `org.dotfiles.Events`** (the exact "active but not serving" mode AD-33 exists to prevent; `readiness-alternatives.md:130` notes `Type=dbus` cannot detect it).

**Why the spine misses it.** AD-35 was written to stop daemon/CLI races; it does not account for the fact that the mutex abstraction is *already owned by the callee*. `reval-operational R-7b` recommends naming the state mutex and says two converges "serialize only at the write"; `review-operational F2` even recommended the daemon "MUST hold the seed mutex blocking for reconcile" — which is precisely the deadlock.

**Minimal decision.** Rewrite AD-35's lock clause to: *the daemon never acquires `.seed.lock` or `.history.lock` around a use-case call; the use cases own their locks; the daemon only takes a lock for a direct write it performs itself (of which there are none in Phase 5).* Add an architecture test that asserts no daemon composition root holds a mutex across a `run()`.

---

### F2 — HIGH — No single converge use case covers both derivation-staleness and intent convergence; plain `reconcile` structurally cannot regenerate

**Evidence.**
- `ReconcileDesktopStateUseCase._ensure_entries` regenerates palette only when the recorded entry is **incomplete**, effects/icons only when their entry dir is **absent** (`reconcile.py:336-386`); it never compares recorded inputs to current inputs. If inputs changed but the recorded entry exists and is complete, it silently repoints to the old entry.
- If it did re-derive, `_assert_hash_matches` (`reconcile.py:345,362,382`) raises `RuntimeError("cache entry … cannot be regenerated from current spine inputs; re-run wallpaper set")` because the new entry hash differs from the recorded one. So reconcile cannot converge to changed inputs **by construction**.
- `regenerate.py` itself states the split (`:8-10`): "reconcile converges to RECORDED state (stale entries are cache hits, so it changes nothing); regen converges to CURRENT-INPUT state."
- `RegenerateStaleUseCase` re-derives stale layers + cascade (`regenerate.py:79-129`) but **never runs the declarative/intent converge**: the CLI branch for `--regenerate-stale` returns immediately (`main.py:1096-1139`) and never calls `_run_converge()`, whereas the default `reconcile` branch does (`main.py:1251-1272`). `_run_converge` may itself fire a nested `_run_wallpaper_set` (`main.py:1349`, which appends `trigger="set"` at `main.py:299`).
- Consequently, **no existing command performs derivation-regeneration *and* intent convergence in one action.** A daemon that picks `reconcile` misses all input-derived staleness; a daemon that picks `regenerate` misses `desired.json`.

**Why the spine misses it.** AD-36 (`SPINE:57`) says "else converge" without naming the use case; AD-42 assigns triggers by *initiator* (`reactive`) while the code assigns them by *use case* (`regenerate` hardcoded at `regenerate.py:123`, `doctor` at `doctor.py:308`, `set` at `main.py:299`). `[covered in part: reval-adversarial Scenario 5]` — but the structural impossibility of `reconcile` re-deriving, and the absence of any combined path, are not stated.

**Minimal decision.** Name the daemon's converge as an explicit composite use case — `CheckInputs → RegenerateStale → Reconcile → declarative converge` — and pin it in AD-36 (or require `reconcile` to call `CheckInputs` and defer to regenerate when stale). Also state the action→trigger rule: one daemon action = one `reactive` line (inner `set` suppressed), plus at most one `prune` line, and thread an actor/trigger parameter through `RegenerateStaleUseCase.run` so it can emit `reactive` instead of its hardcoded `regenerate`.

---

### F3 — MEDIUM/HIGH — AD-41 claims `doctor` detects/repairs `current.json`↔history divergence; the code cannot detect it

**Evidence.**
- AD-41 (`ARCHITECTURE-SPINE.md:92`): "`doctor` detects and repairs `current.json`↔history divergence."
- `DoctorUseCase.check()` runs exactly two legs — cache entries (`doctor.py:91-187`) and `current/` symlinks (`doctor.py:189-241`); there is **no history read**.
- `DoctorRepairUseCase.repair()` (`doctor.py:286-328`) only additionally heals a **torn history tail** via the injected `heal_torn_history_tail` callback (`main.py:805`), which handles mid-write truncation (`seeder.py:697-792`) — not a missing record for an already-saved `current.json`.
- Therefore the daemon's documented recovery path for the save↔history crash window has no implemented detector; a daemon would have to build its own state↔history sequence check.

**Why the spine misses it.** The claim was asserted in the AD but never checked against the Phase-3 doctor, which was deliberately scoped to store/symlink/cache. `[partially covered: review-operational F4, reval-operational R-3]` say the check is "not pinned to a record position"; the harder fact is that **no such check exists at all**.

**Minimal decision.** Either (a) add a sequence/position-based `current.json`↔last-history check to `DoctorUseCase` (history has no sequence; position plus `applied_at` is insufficient under concurrency — see `review-operational F17`), or (b) remove the claim from AD-41 and give the daemon its own completion record. Do not leave the AD asserting a capability the code lacks.

---

### F4 — MEDIUM — Converge-on-start vs D-Bus readiness (`Type=dbus`) ordering is unspecified and can exceed `TimeoutStartSec`

**Evidence.**
- AD-33 (`SPINE:39`): `Type=dbus` + `BusName=org.dotfiles.Events`, "systemd considers it started only when the name is owned", "never exits 0 before owning the name".
- AD-36 (`SPINE:57`): "on any event and **on start**, recompute input hashes … else converge". A start-time converge runs the full derivation, which invokes CSG/WEG/ITR subprocesses that "must not serialize concurrent CLIs for minutes" (`reconcile.py:29-33`, `regenerate.py:16-18`).
- systemd's default `DefaultTimeoutStartUSec` is **1min 30s**, and a `Type=dbus` unit whose `ExecStart` does not acquire the name within it is killed and retried (`readiness-systemd-dbus.md:39-45,164,221`, with a live reproduction).
- The spine pins neither the order ("name first, then converge" vs "converge, then name") nor a `TimeoutStartSec`. A conformant implementation that converges before `RequestName` on a cold cache is SIGTERM'd mid-derivation → `Restart=always` → repeat (a start-limit crash-loop).

**Why the spine misses it.** AD-33's readiness rule and AD-36's start-converge rule were authored independently; the start-time budget between them is undecided. `readiness-systemd-dbus.md` analysed never-acquired-name timeouts but not the "name acquired only after a long converge" case.

**Minimal decision.** Pin the ordering: the daemon acquires `org.dotfiles.Events` **first** (readiness), then performs the start converge as a non-gating action, and/or set `TimeoutStartSec=infinity` with a stated reason. Add the ordering to AD-33/AD-36. Converge must never gate name ownership.

---

### F5 — MEDIUM — The backstop hash source (`recompute_input_hashes`) omits the intent document, so `desired.json`-only changes are suppressed

**Evidence.**
- AD-39 (`SPINE:80`) puts `$XDG_CONFIG_HOME/dotfiles/desired.json` in the watched set; AD-36 (`SPINE:57`) makes the persisted backstop the gate: "if unchanged, do nothing; else converge and persist."
- The only shipped input-hash source is `IInvalidationQuery.recompute_input_hashes()` / `InvalidationQueryAdapter` (`invalidation.py:139-159`), which hashes exactly `palettes` (csg templates), `effects` (weg catalog), `icons` (icon templates + mappings) and returns `wallpapers: None`; `compare_against_meta` explicitly drops `wallpapers` (`invalidation.py:204-221`). **There is no intent/`desired.json` hash.**
- The intent reader is a separate adapter (`desired_state_reader.py:42-48`, currently `state_root/desired.json` — relocation `[covered: reval-adversarial S4 / review-operational F14]`). A daemon that reuses the existing invalidation adapter as its backstop will fire an inotify event for a `desired.json` edit but compute an **unchanged** backstop hash → skip → the intent change is never converged. This is the same failure class as the crash window (F3/prior F4), but caused by *hash coverage*, not by timing.

**Why the spine misses it.** AD-36 says "input hashes" generically; `reval-adversarial Scenario 4` fixes the backstop's key set at design level but not the code-level fact that the only ready-made hash API excludes intent. `recompute_input_hashes` cannot simply gain an intent key without changing `IInvalidationQuery`/`reconcile` sematics (`desired.json` is not a derivation input for any layer).

**Minimal decision.** Define the backstop record as `{schema_version, derivation_inputs: {palettes,effects,icons}, intent_hash: sha256(desired.json bytes)}`, sourced from `recompute_input_hashes()` **plus** a distinct intent hash, and add it to the AD-44 machine-enforced contract set. Absent/corrupt intent ⇒ treat as changed (never suppress).

---

## 3. Disposition of prior coverage and residual items

Already owned by the prior `reval`/`review` corpus; this review confirms them rather than re-litigating:

| Integration edge | Owner |
| --- | --- |
| Which trigger a derivation vs intent change emits; one-line-per-action | `reval-adversarial` Scenario 5; `review-adversarial` F5-7 (`:96-108`) |
| Backstop record path/schema/version/migration; `desired.json` relocation key-set change | `reval-adversarial` Scenario 4; `review-operational` F14 |
| Unseeded daemon crash-loop on `RuntimeError("nothing to reconcile")` | `reval-adversarial` Scenario 3; `review-operational` F1 |
| Save↔history crash window suppressed by the input-hash backstop | `review-operational` F4; `reval-operational` R-3 |
| Watched-root set vs `derive.find_*` dynamic/repo fallback; recursion depth ≠ hash depth | `review-adversarial` (old) F3; `reval-adversarial` Scenario 2/6 |
| Trigger enum drift (`reactive`/`prune`/`force`; three hardcoded copies at `reconcile.py:68`, `inspect.py:69`, `seeder.py:816-818`) | `reval-operational` F16 disposition; R-2 |
| Prune audit line never written (`_run_prune` deletes with no `append_history`, `main.py:1735-1752`; declarative `remove_entry` likewise, `main.py:1354-1358`) | `review-operational` F10; reval-adversarial Scenario 7 |
| `current.json` corrupt (≠ absent) has no distinct no-op/fatal routing | `reval-operational` R-3; `reval-adversarial` Scenario 3 |
| Overflow re-scan single-flight / change-during-converge dirty flag | `reval-operational` R-6d |

Residual (not integration-blocking, listed for completeness): the daemon composition root would be the fourth independent construction of `JsonStateRepository`/`CacheSeeder`/`FlockSeedMutex` (`main.py:468-488, 678-736, 775-803`); AD-35 does not require a shared factory, so a divergent lock path remains possible `[covered in spirit: review-operational F2]`.

No finding in this review requires reversing a settled Phase-5 decision.

*No praise.*
