# Operational Re-Validation — Phase 5 Reactive Runtime

- **Reviewer:** operational edge-case hunter, no prior context (revalidation pass)
- **Subject:** `ARCHITECTURE-SPINE.md` (Phase 5, `status: final`, AD‑33..AD‑44), `.memlog.md`, `contracts/event-contract.md|json`, `epics-dotfiles-runtime-phase5.md`
- **Date:** 2026-09-11
- **Constraint:** reviewer does not edit the spine or contract. Findings only.
- **Method:** take the surviving operational situation list (bus/lifecycle, session faults, first-run/partial spine, intent/backstop integrity, watch integrity, crash/durability windows, concurrency, packaging/upgrade, multi-session) and for each ask: does the *current* spine text decide the behavior, or only imply it? Prior findings are first re-checked against the final text so settled choices are not re-litigated.
- **Verdict:** **CONDITIONAL — no CRITICAL. Five HIGH residual situations remain genuinely unforeseen; the rest are now closed or correctly deferred.** The converged spine (AD‑36 persisted backstop, AD‑39 pinned allowlist + quantified depth, AD‑40 overflow re-scan, AD‑35 per-action lock join, AD‑42/44 single-sourced enum) closes the original blocking theme. The residual risk is narrower and lives at the **process/systemd/bus boundary** (broker replacement, `DO_NOT_QUEUE` contention vs `Restart=always`, fatal-vs-recoverable error routing, watch-registration loss, session-env/hotplug), not in single-converge correctness.

---

## 0. Disposition of the prior operational findings (settled — not re-litigated)

| Prior | Status against final spine | Evidence |
| --- | --- | --- |
| F1 no converge-on-start / unseeded crash-loop | **CLOSED** | AD‑36 (`SPINE:57`): "on any event and **on start**, recompute… else converge and persist"; unseeded "benign no-op… never an error, never a restart"; AD‑33 pins `RestartSec`/`StartLimitIntervalSec`/`StartLimitBurst` |
| F2 daemon not bound to seed/state mutex | **CLOSED (seed/history)** | AD‑35 (`SPINE:51`): daemon "joins the existing `.seed.lock` / `.history.lock` per action, never holding a lock across sleeps". Residual: the **state** mutex is still unnamed (see R‑7c) |
| F3 watched set dynamically resolved / repo fallback | **CLOSED** | AD‑39 (`SPINE:80`) pins an enumerated allowlist of spine locations, not `derive.find_*`; AD‑43 removes the silent repo fallback |
| F4 current.json↔history crash divergence | **PARTIAL → R‑3** | AD‑41 (`SPINE:92`) "assumes its own last write may have failed and re-checks"; doctor detects divergence — but the check/repair is not pinned to a record position |
| F5 multi-session same user | **STATED, NOT MADE SAFE → R‑2** | Convention (`SPINE:126`) "one active graphical session per user is assumed"; Deferred (`:190`) multi-session state_root |
| F6 unit lifecycle (order/env/upgrade/uninstall) | **PARTIAL → R‑4** | AD‑33 pins target + enablement; Deferred (`:188`) leaves env import open; upgrade/uninstall absent |
| F7 disk-full / persistent derive → crash-loop | **PARTIAL → R‑3** | "never crash-loop" convention (`SPINE:125`) + AD‑41 lock, but no fatal-vs-recoverable taxonomy and no orphan staging GC |
| F8 mid-edit transient derive | **OPEN (minor) → R‑6d** | AD‑40 (`SPINE:86`) coalesces/debounces a burst; still time-based, not quiescence-stable |
| F9 observe-only→live promotion | **OPEN → R‑5** | AD‑35/41 "observe-only first" with no mode source / promotion / backstop rule |
| F10 partial prune | **OPEN → R‑6e** | R‑1 story (epics `:20`) adds the audit line; partial-failure semantics unspecified |
| F11 non-local FS (NFS/overlay) | **OPEN → R‑6c** | AD‑40 forbids polling; no local-FS precondition on watched roots |
| F12 log growth/rotation | **OPEN → R‑4d** | AD‑41 logs actions; no location/retention; journald caps only apply if console-logged |
| F13 inotify recursion depth | **CLOSED** | AD‑39 (`SPINE:80`) quantifies: icon-templates up to 4 levels, csg templates up to 2 |
| F14 desired.json migration | **OPEN (minor) → R‑6b** | AD‑39 relocates the path; no one-time migration/doctor check |
| F15 hub-restart reconnect | **CLOSED (state)** | AD‑34 epoch bump + `JobsCleared`; contract `md:56-63` re-hydration; producer re-announce still thin (R‑1d) |
| F16 enum drift | **CLOSED** | AD‑42 (`SPINE:98`) single-sources 7 values; AD‑44 drift test |
| F17 clean-exit/overflow | **CLOSED** | AD‑33 "never exits 0 before owning the name"; AD‑40 overflow re-scan. Residual: overflow re-scan single-flight not stated |

---

## HIGH — unforeseen operational situations

### R‑1 — Bus replacement / broker restart vs `Type=dbus` re-acquisition

**Situation.** The session bus is restarted or the broker replaced (e.g. a `dbus-broker`/`dbus-daemon` upgrade, or a manual `systemctl --user restart dbus`), or the bus is momentarily absent, while the daemon holds `org.dotfiles.Events`; then re-acquisition.

**What the spine says.** AD‑33 (`SPINE:39`) sets `Requires=dbus.socket` + `After=dbus.socket`, `Type=dbus` + `BusName=org.dotfiles.Events`, `Restart=always`, tuned start limits, and: name loss is a *clean stop*; `RequestName(DO_NOT_QUEUE)` "fails fast non-zero on contention"; "never exits 0 before owning the name". AD‑34/contract (`md:56-63`) bump the epoch and emit `JobsCleared` on hub restart; consumers re-hydrate.

**What it omits.**
1. **Socket unit ≠ broker unit.** `dbus.socket` is the socket; the actual session broker on modern systems is `dbus-broker.service` (with `dbus.service` an alias). Ordering only against `dbus.socket` does not order against a broker re-exec, and on a setup without a session `dbus.socket` the `Requires=` may not resolve at all.
2. **Re-acquisition is implicit only.** Nothing says whether the process exits on bus loss (letting `Restart=always` re-run and re-`RequestName`) or stays alive and must reconnect; `Type=dbus` shows systemd the name was lost, but the daemon's own behavior is unstated.
3. **Transient contention vs real contention.** During a broker swap, `RequestName` fails non-zero because there is no bus yet. That is indistinguishable, in AD‑33's wording, from a *second legitimate owner* — both "fail fast non-zero", and with `Restart=always` + start limits a slow upgrade can latch a `failed` unit (the exact mode AD‑33 exists to prevent).
4. **Old bar / new daemon during the window.** If the daemon restarts onto a different interface (`Events1`→`Events2`), the migration rule (AD‑34) allows coexistence but the operational restart ordering is not stated.

**Minimal decision (spine).** Extend AD‑33: (a) order against the real broker unit (`After=dbus.socket dbus.service`, or a provisioning drop-in for `dbus-broker.service`); (b) state that bus loss ⇒ process exit ⇒ `Restart=always` re-acquires, and that the persistence of `seq`/`epoch` is resumable via `JobsCleared`; (c) distinguish "no bus available / retryable" from "name owned by a peer" (the latter is benign-and-idle, not a crash-loop — see R‑2). **Or** record as Deferred: broker-specific unit wiring.
**Testable consequence.** With `dbus-broker` restarted while the daemon runs, the unit returns to `active (running)` and re-owns `org.dotfiles.Events` without consuming the start limit.

---

### R‑2 — `DO_NOT_QUEUE` contention from a legitimate second session / stale owner vs `Restart=always`

**Situation.** Two graphical sessions of the same user (nested/second TTY/dev compositor), or a previous daemon instance stopping slowly (SIGTERM/name-release in flight), or a name already owned by a peer. `RequestName(DO_NOT_QUEUE)` fails; AD‑33 says "fails fast non-zero on contention" and `Restart=always`.

**What the spine says.** Convention (`SPINE:126`): "one active graphical session per user is assumed; `state_root` is per-user (multi-session scoping deferred)"; Deferred (`:190`) per-session scoping. AD‑38: exactly one owner; AD‑33: fail-fast non-zero, `Restart=always`.

**What it omits.** The assumption is *stated but not made safe*. Contention with a **legitimate** peer (second session, or a slow-dying old instance) is treated exactly like an internal failure: non-zero exit → `Restart=always` → contention again → start limit → `failed`. The two sessions also share `state_root` and `desired.json`, so even if only one owns the hub, a `wallpaper set`/converge in session A repoints consumers for session B (cross-wiring), and `HyprlandMonitorSource` output is per-session. User **switch** is safer (different user ⇒ different user manager/bus/state), but the same user with lingering sessions is not. This is a direct collision between the single-session assumption and AD‑33's restart policy.

**Minimal decision (spine).** Make the assumption operational: on start, if the name is already owned, the daemon exits **cleanly** (idle/no-op, code that `Restart=always` does not retry into a loop) or enablement is per-user-singleton; add a `doctor`/inspect detector for a second compositor/session. Keep per-session `state_root` Deferred (already is). **Or** state explicitly that contention is expected and the unit must be `PartOf=graphical-session.target` plus user-singleton enablement.
**Testable consequence.** Starting the unit twice (simulating a second session) yields one `active` hub and one cleanly-idle non-looping second start, never a `failed` unit.

---

### R‑3 — AD‑43's "loud typed failure" and crash windows have no fatal-vs-recoverable routing

**Situation.** (a) Daemon starts before the runtime was ever seeded, before spine assets exist, or with a **corrupt/partial** spine. (b) `ENOSPC` during regenerate (disk full). (c) Power loss between `current.json` save and history append. (d) Power loss between a successful converge and backstop persist.

**What the spine says.** AD‑36 (`SPINE:57`): unseeded (`no current.json`) is a benign no-op, never seeds. AD‑43 (`SPINE:104`): a missing input is a "**loud typed failure**, never a silent repo read"; `verify` asserts content. AD‑41 (`SPINE:92`): "the daemon assumes its own last write may have failed and re-checks rather than trusting it"; doctor detects/repairs `current.json`↔history divergence. Convention (`SPINE:125`): "never crash-loop". AD‑36: backstop persisted on success.

**What it omits.**
1. **No error taxonomy.** "Loud typed failure" (AD‑43) is not routed to a recoverable path. With `Restart=always` + start limits, a missing/corrupt spine input at startup, or a corrupt `current.json` (malformed ≠ absent — AD‑36 only defines *absent*), or persistent `ENOSPC` during regenerate, can propagate out of the loop and latch `failed` — contradicting the "never crash-loop" convention and AD‑33's own intent.
2. **AD‑41's re-check is not pinned.** "Re-check rather than trust" does not state *what* is compared or *how* it is repaired. AD‑6's crash repair (`08-18 SPINE:68`) covers symlinks/`current.json`; AD‑23 covers a torn tail only. The crash window where `current.json` is written but its history line is not still has no pinned detection (compare `current.json`'s applied sequence/position, not wall-clock) or repair (`reactive` line).
3. **Corrupt backstop unspecified.** Missing backstop ⇒ converge (AD‑36, safe). Corrupt/unparseable backstop ⇒ undefined; a parse error must not suppress convergence.
4. **Orphan staging.** A crash/power loss mid-derivation leaves `cache/.staging-<pid>/` (AD‑9) with no startup GC.

**Window (d) is actually safe by design** — converge succeeded, backstop persist failed ⇒ next start sees a stale record ⇒ recomputes ⇒ re-converges (idempotent). Confirm it explicitly; no gap.

**Minimal decision (spine).** AD‑36/AD‑41 clause: missing/corrupt spine input and corrupt `current.json`/backstop at start are **recoverable** — log with trigger, surface via inspect/`doctor`, back off, unit stays `running`; never seed; never consume the start limit. Pin the divergence check to a record position/sequence and its `reactive` repair line. Add startup GC of stale staging. **Or** Deferred: staging GC as an implementation story.
**Testable consequence.** A machine with `current.json` present but `effects.yaml` deleted reaches `active (running)` and surfaces the typed failure in inspect; it does not consume the start limit.

---

### R‑4 — Unit lifecycle across upgrade / uninstall / missing binary / log bounds

**Situation.** Upgrade the installed runtime (swap the `uv tool` binary while the daemon process runs; multiple installed versions); uninstall the runtime/role; unit enabled but binary missing; log growth/rotation/journald caps.

**What the spine says.** AD‑33: provisioning owns the unit + enablement (`graphical-session.target.wants/` when no live user manager); Deferred (`:188`) admits no role writes `~/.config/systemd/user/` today, and names the target/env question as open. AD‑34: `Events1`/`Events2` may coexist during migration. AD‑41: every action logged with trigger.

**What it omits.**
1. **Upgrade semantics.** Swapping the `uv tool` binary under a running process leaves old process + new contract; nothing says the unit restarts on binary change or how bar↔daemon version skew across an upgrade is handled (AD‑34's coexistence rule is a wire rule, not an upgrade procedure).
2. **Uninstall semantics.** No disable + stop + unit removal + `graphical-session.target.wants/` symlink removal. With `Restart=always`, a leftover enabled unit whose `ExecStart` is gone retries forever / lands `failed` — the "unit enabled but binary missing" case is entirely unhandled (no `ExecCondition=`/`ConditionPathExists=`).
3. **Multiple versions.** Which installed version `ExecStart` resolves to is unspecified.
4. **Log bounds.** AD‑41 logs actions but not *where*; journald caps only apply if logs go to the journal (console). A private append-only artifact under `state_root` would be unbounded under a watch storm.

**Minimal decision (spine).** Role responsibilities: upgrade restarts the daemon when the binary changes (and states the bar/daemon version-skew handling); uninstall disables+stops+removes the unit and its enablement symlink; `ExecStart` pins the installed binary (or `ConditionPathExists`); operational logs go to journald (bounded by journald policy), delete-audit is the history line or a bounded artifact. **Or** Deferred: upgrade/uninstall role work.
**Testable consequence.** Uninstalling the runtime leaves no enabled unit, no `wants/` symlink, and no restart loop.

---

### R‑5 — Watch-registration loss beyond `IN_Q_OVERFLOW` (exhaustion, root-dir replacement, symlinks, non-local FS)

**Situation.** `max_user_watches`/`max_user_instances` exhaustion when `inotify_add_watch` is called; a watched **directory root** is replaced/moved/renamed so the watch is orphaned on the old inode; a watched root (or `desired.json`) is a symlink; a watched root lives on NFS/overlay.

**What the spine says.** AD‑40 (`SPINE:86`): inotify over the AD‑39 roots, coalesce/debounce; on `IN_Q_OVERFLOW` do a full recursive re-scan; "a directory watch persists across in-directory atomic replaces"; NO polling; non-recursive so watches install per level to bounded depth. AD‑39 (`:80`): file roots via immediate parent filtered to the exact filename; depth quantified (4/2).

**What it omits.**
1. **Watch-registration failure.** `IN_Q_OVERFLOW` is handled; `inotify_add_watch` returning `ENOSPC`/`ENOSPC`-class exhaustion (or `EMFILE`) is not. A failed registration silently drops that root — permanent blindness, and with AD‑40's no-polling rule nothing recovers it.
2. **Watch invalidation on the root itself.** "Directory watch persists across atomic replaces of files *inside* it" covers files, not the **directory root** being swapped/renamed (`IN_MOVE_SELF`/`IN_DELETE_SELF`/`IN_IGNORED`). A replaced root orphans its watch; the bounded-depth subwatches may survive on the old tree while the path now points elsewhere.
3. **Symlinked root.** inotify follows a symlink to its target; replacing the symlink does not re-target any watch, and writes at the symlink path may produce no event. No realpath/unsupported rule.
4. **Non-local FS.** Prior F11 remains: if `<install>` (the spine) is NFS, inotify reports no remote changes and flock is unreliable; the daemon silently never reacts. Overlayfs upper-layer behaviour is also unpinned.

**Minimal decision (spine).** AD‑40 clause: on registration failure or watch invalidation (`IN_IGNORED`/`IN_MOVE_SELF`/`IN_DELETE_SELF`) log the failure, re-establish watches, and perform a full re-scan of that root; if registration cannot be established, degrade **explicitly** (surface in inspect/`doctor`), never silently. AD‑39: resolve roots via `realpath` and reject/skip non-local FS with a `doctor` warning. **Or** Deferred: local-FS precondition + watch-loss recovery story.
**Testable consequence.** Exhausting `max_user_watches` yields a surfaced degradation and a re-scan, not silent non-reaction.

---

## MEDIUM / LOW — residuals worth a line or a Deferred entry

### R‑6 — Integrity and semantics edges
- **(a) Session env staleness / hotplug.** AD‑33 (`:39`) binds to `graphical-session.target` and survives a Hyprland *reload*; but on **suspend/resume** or a Hyprland **restart**, reloaders invoked by a converge use the compositor env (`HYPRLAND_INSTANCE_SIGNATURE`, `WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR`) captured when the unit started. The spine leaves env import open (Deferred `:188`) and never says reloaders re-read env or that a compositor restart restarts the unit. **Monitor/GPU hotplug changes no watched root** — AD‑36 (`:57`) restricts reactions to the watched root set, so no converge is triggered and the desktop can be stale; this is a *design* consequence, not a bug, but it is neither stated as a non-goal nor deferred. **Minimal:** document monitor/topology change as out of AD‑36 scope (Deferred), and pin that reloader env is resolved per invocation or the unit is restarted on compositor restart; state logout teardown (`PartOf=`/logind kill) so the daemon does not outlive a dead session bus.
- **(b) Intent-document integrity.** `desired.json` deletion should be defined (**no-op, never a clear/revert**); corrupt JSON should be a logged recoverable skip; a **symlink** at `desired.json` should be rejected or `realpath`-watched. AD‑39/AD‑40 cover atomic replace of the file but not these three states, and AD‑39's file-root watch via the immediate parent does not see writes through a symlink. **Minimal:** pin absent/corrupt/symlink semantics; backstop corrupt ⇒ treat-as-absent and converge (never suppress).
- **(c) Prune killed mid-delete / partial failure.** R‑1 (epics `:20`) adds the audit line; AD‑42 (`:98`) appends exactly one line per real prune. No statement that automatic prune is **best-effort and idempotent**, that per-entry failures are logged and retried next trigger, that a killed prune is safe (unreferenced entries only, never past the AD‑30 floor), or whether the audit line is written before/after deletion (a kill between them loses the audit record). **Minimal:** pin idempotent best-effort prune with per-entry audit and floor-bounded retry.
- **(d) Overflow re-scan and trailing-change coalescing.** AD‑40's full re-scan on `IN_Q_OVERFLOW` is not stated single-flight/coalesced with an in-flight reconcile, so a storm can nest re-scans. Separately, "coalesce bursts into a single reconcile" does not guarantee a reconcile runs *after* the **last** event: a change arriving during an in-flight reconcile can be folded in and never re-run. **Minimal:** single-flight the re-scan with a logged overflow count; add a dirty-flag "re-run once after" rule to the debounce.
- **(e) Quiescence vs debounce.** AD‑40's debounce is time-based; an in-place (non-atomic) template write can be read mid-edit in a quiet gap and permanently record a transient theme (prior F8). **Minimal:** debounce on quiescence / stable-hash-across-two-reads; document atomic-replace edits; transient derive errors are a non-fatal skip (no history line).
- **(f) `desired.json` migration.** AD‑39 relocates the path; existing users' intent sits at `state_root/desired.json`. No one-time migration or `doctor` detection. **Minimal:** doctor migration/check.

### R‑7 — Concurrency semantics
- **(a) Observe-only → live promotion.** Still no mechanism: where the flag lives (must be outside every watched root or it self-triggers), whether promotion needs a restart, whether the backstop advances while observe-only (advance ⇒ promotion skips pending work; do not advance ⇒ promotion replays), and whether observe-only records "would-have" actions. **Minimal (AD‑41 clause):** pin mode source, promotion on restart, and backstop rule under observe-only.
- **(b) Two rapid commits / daemon+CLI simultaneous converge.** AD‑40 coalesces; AD‑35 (`:51`) joins `.seed.lock`/`.history.lock` *per action*. Still implicit: the **state** mutex named in `.memlog.md:18` is not in the spine, and "per action, never across sleeps" means two converges can compute concurrently and serialize only at the write (last-writer-wins, two history lines). Idempotency likely saves this, but it is not decided. **Minimal:** name the state mutex alongside seed/history in AD‑35; state the accept-last-writer outcome.
- **(c) Hub-restart producer re-announce.** `JobsCleared` + contract re-hydration handle consumer state; a long-lived job that outlived the hub cannot re-announce (AD‑34/38 silence it), and a producer calling `Emit` while the hub is down gets a hard failure. **Minimal:** contract clause "producers re-announce state on hub reappearance; `Emit` while absent is a logged drop."

---

## Consolidated minimal decisions (ranked, for the author)

1. **Bus/broker + contention (R‑1, R‑2):** order against the real broker unit; distinguish retryable bus-absence from peer-owned name; make legitimate contention a clean idle, not a `Restart=always` crash-loop; operationalise the single-session assumption (detector or user-singleton enablement).
2. **Recoverable-vs-fatal (R‑3):** route missing/corrupt spine and `ENOSPC`/typed derive errors to log+backoff with the unit `running`; pin the `current.json`↔history check by record position and its `reactive` repair; treat corrupt backstop as absent; GC stale staging.
3. **Watch integrity (R‑5):** recover registration failure and root-dir invalidation via re-establish + re-scan; resolve roots by realpath; diagnose non-local FS explicitly.
4. **Packaging lifecycle (R‑4):** upgrade restart + version-skew, uninstall disable/remove, missing-binary condition, journald log bounds.
5. **Session/env/hotplug + remaining semantics (R‑6, R‑7):** document monitor/topology as out of AD‑36 scope; reloader-env resolution; logout teardown; intent absent/corrupt/symlink; idempotent best-effort prune; single-flight overflow + dirty-flag re-run; quiescence; observe-only promotion; state mutex.

## Proposed Deferred additions

- Session-topology (monitor/GPU hotplug, compositor restart) does **not** trigger convergence; a session-event trigger would violate AD‑36 and is a future-phase item.
- Broker-specific unit wiring (`dbus-broker.service` vs `dbus.socket`) if not adopted as an AD‑33 clause.
- Upgrade/uninstall role responsibilities and version-skew handling.
- Orphan staging GC and local-FS precondition as implementation stories.
- Per-session `state_root` scoping (already Deferred) — keep, now with an operational detector.

## Verdict

**CONDITIONAL — no CRITICAL; five HIGH residuals (R‑1..R‑5).** The final spine genuinely closes the earlier blocking findings (F1–F3, F13, F15 state, F16, F17) with citable text, and correctly defers multi-session state. The remaining unforeseen situations cluster at the process/systemd/bus boundary and in error routing; each is fixable by a clause or an explicit Deferred entry above. Proceed after the five HIGH items are pinned or deferred.

*No praise.*
