# Operational & Failure-Mode Review — Phase 5 Reactive Runtime

- **Reviewer:** operational & failure-mode lens (VALIDATE gate, ad-hoc; spine not edited)
- **Subject:** `ARCHITECTURE-SPINE.md` (AD‑33..AD‑42 + AD‑12 delta), `.memlog.md`, `contracts/event-contract.md|json`, `epics-dotfiles-runtime-phase5.md`
- **Method:** walk each operational situation the spine can face (crash windows, restarts, suspend/resume, multi-session, races, first-run, FS faults, bus faults, disk, upgrade/uninstall, hub SPOF) and ask: does the spine *decide* the behavior, or only imply it?
- **Verdict:** **REJECT AS WRITTEN — the spine's safety story (AD‑33/AD‑41) is not closed for lifecycle, recovery, or environment faults.** Correctness of a *single successful* converge is well specified; the behavior *around* convergence is largely undefined. The blocking theme is that the spine treats the daemon as a durable supervisor while giving it only in-memory recovery state and no start/recovery convergence rule, so it can (a) crash-loop into a `failed` unit on a fresh machine and (b) silently skip reconciliation for every change that happens while it is down.
- **Overlap note:** the contract-semantics lens (`review-contract.md`: C1–C2, H1–H4) and the trust lens (`review-trust.md`: S‑00 + authorization) already own payload/lifecycle semantics and identity. This review does not re-litigate those; it references them and focuses on operational lifecycle, recovery, environment, and race behavior.

Reference points used below: AD‑33 (`ARCHITECTURE-SPINE.md:40`), AD‑35 (`:52`), AD‑36 (`:58`), AD‑37 (`:66`), AD‑38 (`:75`), AD‑39/40 (`:81`,`:87`), AD‑41 (`:93`), AD‑42 (`:99`), conventions (`:101-112`), Deferred (`:172-176`); code facts at `src/runtime/src/runtime/application/reconcile.py`, `adapters/flock_seed_mutex.py`, `adapters/seeder.py`, `adapters/desired_state_reader.py`, `application/derive.py`.

---

## Tier summary

| # | Finding | Tier |
| --- | --- | --- |
| F1 | No converge-on-start/recovery; unseeded daemon crash-loops into a `failed` unit | **CRITICAL** |
| F2 | Daemon is not bound to the existing seed/state mutex by the spine (only by the non-binding memlog) | **HIGH** |
| F3 | Watched-root set is resolved dynamically and can diverge from the derivation input set (install-spine vs repo-ancestor fallback; file-vs-dir ambiguity) | **HIGH** |
| F4 | Crash between `current.json` save and history append creates permanent state/history divergence; the AD‑36 backstop then suppresses the repair | **HIGH** |
| F5 | Multi-session, same user: no session/seat identity; two compositors fight over one per-user state root | **HIGH** |
| F6 | systemd unit lifecycle undefined: start order/env/target, upgrade, uninstall, migration | **HIGH** |
| F7 | Disk-full / persistent derive failure → systemd crash-loop → `failed` unit (AD‑33's "silently dead watcher") | **HIGH** |
| F8 | Mid-edit (non-atomic) template writes derive transient states; debounce is not quiescence | **HIGH** |
| F9 | Observe-only → live promotion mechanism absent; backstop semantics under observe-only ambiguous | MEDIUM |
| F10 | Partial prune failure semantics absent; daemon's use of prune unstated | MEDIUM |
| F11 | Watched root on a non-local FS (NFS) silently never fires; no detection; no polling fallback | MEDIUM |
| F12 | Log / delete-audit growth and location unspecified | MEDIUM |
| F13 | inotify non-recursive: files created inside a new subdirectory are not watched; race to derive before quiescence | MEDIUM |
| F14 | `desired.json` relocation has no migration path; current location already contradicts AD‑5 | MEDIUM |
| F15 | Hub-restart / bus-producer reconnection has no operational degradation contract | MEDIUM (semantics owned by review-contract C2/H1–H2) |
| F16 | Contract enum drift: `prune` (already in code) and `reactive` both missing from the shared-data-contract enum | LOW |
| F17 | Clean-exit / kill-switch interaction with `Restart=on-failure`; orphan staging GC; overflow re-scan coalescing; timestamp ordering | LOW |

---

## CRITICAL

### F1 — No converge-on-start/recovery; an unseeded daemon crash-loops

- **Situation:** daemon is (re)started on a fresh machine before `current.json` exists; or restarted after logout/login, crash, upgrade, suspend, or any downtime during which inputs changed.
- **What the spine accounts for:** AD‑33 makes the daemon a `systemd --user` unit with `Restart=on-failure`; AD‑35 says commands stay authoritative and the daemon is optional; AD‑36 holds the last-converged input hash **in memory**; AD‑40 forbids polling. The Deferred section (`:174`) acknowledges only the unit/login-enablement question.
- **What it does NOT account for:** there is no **converge-on-start** rule and no persisted recovery state. `ReconcileDesktopStateUseCase.run` raises `RuntimeError("nothing to reconcile")` when `current.json` is absent (`reconcile.py:159-160`). A provisioning-enabled unit on a fresh machine will therefore fail its first `ExecStart`; with no `RestartSec`/`StartLimit*` pinned, systemd's default backoff hits the start limit and leaves the unit `failed` — the exact "silently dead watcher" AD‑33 exists to prevent. In steady state the in-memory backstop is lost on every restart; because AD‑40 removes polling and there is no initial reconcile, any input change that occurred while the daemon was down and does not generate a later FS event is **never reconciled**. "Continuous reconciliation" silently degrades to "reconcile only if an event happens to fire after a restart."
- **Minimal decision (spine):** add an AD (or extend AD‑33/AD‑36): (1) on daemon start, run exactly one convergence pass that compares current derivation-input hashes against the last converged state (persisted or reconstructed), independent of any event; (2) if the runtime is unseeded (`current.json` absent), the daemon logs and **idles**, or idempotently triggers first-run seed once — it must never exit non-zero for "nothing to reconcile"; (3) pin `RestartSec`, `StartLimitIntervalSec`, `StartLimitBurst` and an `OnFailure=`/inspect surface so a `failed` unit is visible, not silent.
- **Testable consequence:** `systemctl --user start dotfiles-runtime` on a machine with no `current.json` must reach `active (running)` and not consume the start limit.

---

## HIGH

### F2 — The daemon is not bound to the existing seed/state mutex by the spine

- **Situation:** daemon reconcile and an interactive CLI `reconcile`/`wallpaper set`/`seed`/`regenerate` run concurrently.
- **What the spine accounts for:** the inherited-invariant table cites AD‑11 (seeding) but never names the seed/state mutex; `.memlog.md:18` contains the only statement ("AD‑11 seed mutex + reconcile/set state mutex serialize concurrent CLI + daemon; daemon must not race them"), and the memlog is not binding.
- **What it does NOT account for:** the actual serialization today is `FlockSeedMutex` on `state_root/.seed.lock` and `FlockHistoryMutex` on `state_root/.history.lock` (`flock_seed_mutex.py:77-102`, `seeder.py:794`), injected at the CLI composition root. `daemon run` is a *new* entry point and can construct its own composition root. If it opens a different lock path, or holds non-blocking (`SeedLockedError`) where the CLI holds blocking, the two processes race with no architecture-level guarantee. The memlog's claim is a comment, not an invariant a test can enforce.
- **Minimal decision (spine):** add an invariant: the daemon's composition root MUST reuse the identical `ISeedMutex`/`IHistoryMutex` adapters and lock paths as the CLI, and MUST hold the seed mutex blocking for reconcile; add a shared composition-root factory (or an architecture test) so `daemon run` cannot construct divergent locks. State the one-writer lock paths in an AD, not the memlog.

### F3 — Watched-root set is resolved dynamically and can diverge from the derivation input set

- **Situation:** daemon startup / steady state; the install spine lacks a `find_*` target (dev checkout) or the mapping path resolves to a directory instead of a file.
- **What the spine accounts for:** AD‑39 enumerates the roots "resolved by `derive.find_*`" and claims provisioning owns the daemon configuration (AD‑33); AD‑40 says watch each root explicitly.
- **What it does NOT account for:** `derive.find_*` is a *dynamic* resolver with a repo-ancestor fallback (`derive.py:64-224`), so the watched paths can live outside `<install>`, can change between daemon start and a later reconcile, and `find_icon_mappings` may return a **directory** where AD‑39 says "icon-mappings file" (file root) — a different watch mode. Nothing binds "paths watched" to "paths read by derivation," and AD‑33 (provisioning pins config) contradicts AD‑39 (runtime resolves the set). A resolver drift or install-spine move makes the daemon watch stale paths and silently miss input changes; the AD‑36 backstop cannot help because no event arrives.
- **Minimal decision (spine):** the daemon resolves the watch set at startup (and on a logged re-resolve when the state/install config changes) from the **same** `find_*` calls the derivation uses, logs the resolved set, treats a change in the resolved set as a trigger, and handles dir-or-file roots uniformly (dir watch). Provisioning owns lifecycle/env only, not a duplicated path list. Add a drift test binding watch-root enumeration to derivation-input enumeration.

### F4 — Crash between `current.json` save and history append creates permanent divergence

- **Situation:** daemon crashes (or is killed) after the swap's `current.json` save and before `append_history`. AD‑4/AD‑31 make history the one must-not-lose record; AD‑23 only heals a *torn tail*, not a missing record.
- **What the spine accounts for:** swap order (`shared-data-contract.md` "Swap sequence": … current.json → history → reload); AD‑4 append-before-reload; AD‑23 reader/writer tail tolerance; AD‑31 history lock.
- **What it does NOT account for:** after such a crash the store is updated, history is one line short, and the next reconcile is suppressed by AD‑36 because the input hash is unchanged. Nothing compares `current.json.applied_at` against the last history record, so the divergence is permanent and silent. (The mirror case — history appended, reload not fired — is also unresolvable because there is no reload retry on recovery.)
- **Minimal decision (spine):** on daemon start and in the backstop path, detect `current.json` newer than the last history record (by sequence/position, not wall-clock) and append a `reactive` repair line before treating inputs as converged; define that a failed/reload-pending reconcile is retried on the next trigger. This is the operational completion of AD‑4.

### F5 — Multi-session, same user: no session/seat identity

- **Situation:** two graphical sessions for the same user (nested Hyprland, a second TTY session, dev/test compositor), or two users on one machine.
- **What the spine accounts for:** session D‑Bus is per-user (`event-contract.md:10`); one daemon owns one well-known name (AD‑38); one `state_root` per user (AD‑5). Nothing else.
- **What it does NOT account for:** two users are naturally isolated (separate bus + state root) — but that is never *stated* as the supported model. Two sessions of the **same user** share the user manager/bus and the per-user `state_root`/`desired.json`; `HyprlandMonitorSource` sees that session's outputs, and a `wallpaper set` (or reactive converge) in session A repoints `current/` and reloads consumers for session B. The two compositors overwrite each other's monitor sets. AD‑33's "survives Hyprland reload" is about process lifetime, not session identity, and does not address this.
- **Minimal decision (spine):** declare the invariant explicitly — one reactive runtime per user, exactly one supported graphical session per user — and make the daemon **detect** a second compositor/session and surface a `doctor`/inspect warning rather than silently cross-wiring. Full per-session state is a Phase 6 deferral, but the operational detection must ship with the daemon.

### F6 — systemd unit lifecycle undefined: order, env, upgrade, uninstall, migration

- **Situation:** fresh install; session start ordering; upgrade of the `uv tool` binary; uninstall/role removal; install-spine move; `desired.json` relocation.
- **What the spine accounts for:** AD‑33 provisioning owns the unit and enablement; Deferred (`:174`) admits "no existing role writes `~/.config/systemd/user/`" and that enablement must work with or without a user D‑Bus session, and mentions target + env import as open.
- **What it does NOT account for:** no `After=`/`WantedBy=` decision (graphical-session vs default.target + linger); no `ImportEnvironment`/`EnvironmentFile` decision for `DBUS_SESSION_BUS_ADDRESS`, `XDG_DATA_HOME`/`XDG_CONFIG_HOME`/`XDG_STATE_HOME`, `XDG_RUNTIME_DIR`, and PATH to the `uv tool` shim; no decision whether the daemon starts before the session bus (hub ownership fails) or before Hyprland (reloaders fail, tolerated); no **upgrade** semantics (binary swapped while the old process runs → contract-version skew between bar and daemon); no **uninstall** semantics (disable + stop + remove unit + remove the enablement symlink, else systemd retries a missing `ExecStart` forever); no migration for the `desired.json` move. The Deferred list names the target/env question but no decision is taken, and it does not mention upgrade/uninstall at all.
- **Minimal decision (spine):** pin `WantedBy=graphical-session.target`, `After=graphical-session-pre.target` (and explicitly do **not** `PartOf=` a compositor scope, so a Hyprland reload cannot stop the daemon), an `EnvironmentFile`/`ImportEnvironment` contract rendered by provisioning for all XDG vars + the resolved install spine, and role responsibilities for install/upgrade/uninstall/migration. The daemon must tolerate absent reloaders and absent consumers.

### F7 — Disk-full / persistent derive failure → crash-loop → `failed` unit

- **Situation:** `ENOSPC` (or any persistent derive error) during regeneration; the state root fills.
- **What the spine accounts for:** convention `:112` "reactive trigger failure is logged and retried with backoff"; AD‑41 logs actions; AD‑9 staging; AD‑23 tail healing; palette hard / effects-icons graceful (`reconcile.py`).
- **What it does NOT account for:** a raised palette/history error propagates out of the daemon loop; with `Restart=on-failure` and no pinned `RestartSec`/start-limit policy, persistent `ENOSPC` becomes a hot crash-loop that ends in a `failed` unit (again, AD‑33's silent-death mode). The "backoff" in the conventions is not pinned to the AD and not reconciled with systemd's own restart backoff. Orphan `cache/.staging-<pid>` dirs from a crash are also never garbage-collected (disk grows).
- **Minimal decision (spine):** distinguish fatal startup errors from recoverable reconcile errors: the loop catches typed reconcile failures, logs with trigger, backs off, and keeps the unit `running`; pin `RestartSec`/start-limit; add startup GC of stale `cache/.staging-*`.

### F8 — Mid-edit template writes derive transient states

- **Situation:** user edits one of the four derivation inputs with an in-place writer (truncate+rewrite, e.g. many editors without atomic-replace), or the file is momentarily partial.
- **What the spine accounts for:** AD‑40 coalesce/debounce bursts; AD‑39 file roots watched via immediate parent filtered to the exact filename (atomic-replace safe); AD‑36 hash backstop.
- **What it does NOT account for:** debounce is time-based, not **quiescence**-based. A reconciliation that fires in a quiet gap mid-write reads a half-written template, derives a new (self-consistent) content-addressed entry, repoints the desktop to it, and appends a `reactive` history line. The content-addressed cache means no corruption, but a transient theme is rendered and permanently recorded, and the hash-mismatch guard (`_assert_hash_matches`) does not catch it because the transient input reproduces its own hash. Repeated in-place edits also pollute the cache with transient entries.
- **Minimal decision (spine):** debounce on a settle/quiescence window (no event for N ms), and/or trigger only when the derivation input hash is stable across two reads; require or document atomic-replace edits. Treat derive errors from transient reads as a non-fatal skip (no history line).

---

## MEDIUM

### F9 — Observe-only → live promotion is undefined

- **What the spine accounts for:** AD‑35/AD‑41 "automatic convergence ships observe-only first", opt-in.
- **Gap:** no mechanism — where the flag lives (and whether it can accidentally sit inside a watched root and self-trigger), whether promotion requires a daemon restart, whether the last-converged backstop is advanced while observe-only (if it is, promotion skips all pending changes; if it is not, the first live trigger replays everything), and whether observe-only records "would-have" actions in the trigger log/delete-audit.
- **Minimal decision:** pin the mode source (config under `$XDG_CONFIG_HOME/dotfiles/` outside every watched root, or a systemd drop-in/env), promotion on restart, and the backstop rule under observe-only. State it as an AD‑41 clause, not an epic detail.

### F10 — Partial prune failure and the daemon's use of prune

- **What the spine accounts for:** AD‑30 protected floor; every real prune logs one history line; delete-audit retained; epics say the reactive reconcile "runs the existing use cases."
- **Gap:** no statement that the daemon's reactive converge includes prune at all, nor what happens on partial deletion failure (some entries removed, some EBUSY/permission failures). Partial prune is safe by construction (only unreferenced entries are removed and retry is idempotent), but the spine does not say failures are per-entry logged, retried on next trigger, and never abort a successful wallpaper converge, nor that no failure path may escalate past the AD‑30 floor.
- **Minimal decision:** pin automatic prune as best-effort inside reactive converge; per-entry outcome logging; retry next trigger; never abort the whole converge after wallpaper success; never widen the floor.

### F11 — Non-local watched root (NFS/network mount)

- **What the spine accounts for:** AD‑31 scopes the history lock to local POSIX; addendum B says NFS is "explicitly out of scope." AD‑40 forbids a polling fallback.
- **Gap:** the watched roots include install-spine derivation inputs; if those are on a network mount, inotify does not report remote changes and flock is unreliable. The daemon silently never reacts — no detection, no diagnosis, no failure — which is worse than a hard error because the user believes reactive mode is active.
- **Minimal decision:** at startup `statfs`/stat each watched root; if non-local, `doctor`/inspect warn and automatic mode refuses or degrades explicitly (never silent). Document as unsupported.

### F12 — Log / delete-audit growth and location unspecified

- **What the spine accounts for:** AD‑41 "every automatic action is logged with its trigger; delete-audit is retained"; status via `systemctl` + read-only inspect.
- **Gap:** no location/format/retention. journald handles rotation only if the daemon logs to stderr; a private append-only "delete-audit" file under `state_root` is unbounded, and a watch-storm can make the trigger log high-volume.
- **Minimal decision:** operational logs go to journald (no private log file); the delete-audit is either the existing append-only history or a bounded artifact with a documented retention; no unbounded runtime-authored log.

### F13 — inotify non-recursive: new subdirectories are unwatched

- **What the spine accounts for:** AD‑40 says inotify is not recursive and each root dir is watched explicitly; AD‑39/AD‑40 only claim immediate-parent/root-level watches.
- **Gap:** for directory roots the derivation recurses (`canonical_hash_dir`). If a user creates a nested subdirectory and writes a template inside it, the `IN_CREATE|IN_ISDIR` fires on the root but the file write inside the new dir does not. A reconcile triggered by the mkdir can run before the file lands, and no later event arrives.
- **Minimal decision:** on directory creation within a watched root, add watches to new subdirectories and schedule a quiescence-debounced reconcile; or walk-and-add-watch on each re-scan.

### F14 — `desired.json` relocation has no migration path

- **What the spine accounts for:** AD‑39 relocates intent to `$XDG_CONFIG_HOME/dotfiles/desired.json`, and `memlog.md:46` retires the intent-location deferral.
- **Gap:** the reader (and every planner/CLI call site) currently reads `state_root/desired.json` (`desired_state_reader.py:31-48`); existing users' intent is at the old path. There is no migration, no one-time copy, and no doctor detection. Note that a user-authored file under `state_root` already contradicts AD‑5's "state_root is pure runtime output", so the relocation is fixing a real invariant violation — but it silently drops existing intent.
- **Minimal decision:** pin a one-time migration (copy old→new on first Phase 5 run, or a doctor migration) and add a doctor check for intent present at the old path.

### F15 — Hub-restart / producer-reconnect degradation contract

- **What the spine accounts for:** AD‑38 single hub owner; conventions `:111` "every participant tolerates the others' absence"; `event-contract.md:104-107` absence is a no-op.
- **Gap (operational framing; semantics owned by `review-contract.md` C2/H1–H2 and `review-trust.md`):** the operational behavior after the hub restarts is undefined: jobs/tools that outlive the restart cannot re-announce; `GetTopicState` in-memory state is lost and a bar cannot distinguish "unknown" from "idle"; a consumer holding a proxy must re-hydrate on `NameOwnerChanged`; producers must handle `Emit` failing while the hub is down and re-emit on reconnect. The single process is simultaneously watcher, reconciler, and notifier, so one restart blanks the entire reactive plane.
- **Minimal decision:** add a degradation clause: consumers re-hydrate on hub `NameOwnerChanged` and render "unknown" (not idle) when the hub is absent; jobs re-announce their state topic on hub reappearance; the contract states `GetTopicState` is best-effort in-memory. (Coordinate with the contract/trust findings rather than duplicating their identity fix.)

---

## LOW

### F16 — Contract enum drift (`prune`, `reactive`)

- **Gap:** AD‑42 correctly requires the `reactive` trigger to ship with the shared-data-contract + validator update. But `shared-data-contract.md:45` only enumerates `seed|set|reconcile|force`, while the code already accepts `seed,set,reconcile,force,regenerate,doctor` (`reconcile.py:68`) and `prune` is emitted by AD‑30. Adding only `reactive` leaves `prune`/`regenerate`/`doctor` absent from the authoritative enum.
- **Minimal decision:** the same change reconciles the shared-data-contract enum with the full code enum, not just `reactive`.

### F17 — Smaller operational edges

- **Clean-exit interaction:** `Restart=on-failure` does not restart a loop that returns 0; the daemon must never return 0 except on an explicit stop, or the unit can die cleanly and stay dead. Pin it.
- **Orphan staging GC:** crash mid-derivation leaves `cache/.staging-<pid>` forever (see F7).
- **Overflow re-scan coalescing:** `IN_Q_OVERFLOW` full re-scan (AD‑40) must itself be single-flight and coalesced with an in-flight reconcile, with a logged overflow count; otherwise a storm can nest re-scans.
- **Timestamp ordering:** divergence detection (F4) cannot rely on wall-clock `ts` when CLI and daemon write concurrently; use file position/sequence.
- **Job failure payload:** `JobFinished(exit_code)` is the only terminal signal; a failed speed-test has no reason field. Document that consumers infer failure from `exit_code != 0` (or add a reason) — lives with the contract review's terminal-reconciliation finding.

---

## Consolidated minimal decisions (for the author)

1. **Recovery/lifecycle AD:** converge-once-at-start from persisted/reconstructed input state; unseeded daemon idles (never exits non-zero); pinned systemd `RestartSec`/start-limit/`OnFailure`; startup GC of orphan staging; divergence check `current.json` vs last history record (by sequence) with a `reactive` repair line.
2. **Lock binding AD:** the daemon reuses the exact `ISeedMutex`/`IHistoryMutex` adapters and paths as the CLI; single shared composition root; enforced by test.
3. **Watch-set AD:** resolve at startup from the same `find_*` calls as derivation; log; re-resolve on config change; dir-or-file uniform; provisioning owns lifecycle/env only.
4. **Multi-session AD:** one runtime per user, one supported session; detect a second compositor and surface a warning; per-session state deferred.
5. **Unit lifecycle AD:** target/order/env-file, upgrade restart, uninstall disable+remove, `desired.json` migration.
6. **Fault AD (disk/derive):** recoverable reconcile errors are log+backoff, not crash-loop; observe-only promotion mechanism and backstop semantics pinned; prune best-effort and floor-bounded; non-local watched roots diagnosed as unsupported; logs to journald, bounded delete-audit.
7. **Degradation clause:** hub/bus restart/reconnect behavior and "unknown vs idle" state, coordinated with the contract/trust reviews.

---

*No praise. Verdict is REJECT AS WRITTEN, driven by F1 (blocking) and F2–F8.*
