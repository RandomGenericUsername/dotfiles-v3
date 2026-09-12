# Adversarial-Divergence Review — Phase 5 Reactive Runtime Spine

- **Reviewer:** adversarial-divergence (bmad-architecture reviewer gate; VALIDATE)
- **Subject:** `ARCHITECTURE-SPINE.md` (Phase 5, `status: final`), `.memlog.md`, `contracts/event-contract.md|json`, `epics-dotfiles-runtime-phase5.md`
- **Constraint:** reviewer does not edit the spine. Findings only.
- **Method:** pair Phase 5 units (epics/stories) and require **each** to obey every AD, the Consistency Conventions, and the event contract **to the letter**; then check interoperability on the one shared artifact chain (`org.dotfiles.Events` + `state_root` + `$XDG_CONFIG_HOME/dotfiles/desired.json`). A finding is valid only when **both** units can cite exact spine text for their opposite choices.
- **Verdict:** **REJECT — do not proceed to story breakdown with the spine as written.** The spine is a good philosophy (hub-and-contract, edge-only reactivity, disjoint roots) but the **shared interface is not yet a contract**: the only publish method in `event-contract.json` cannot emit the lifecycle signals the consumer depends on; `GetTopicState` has no authority/retention/absence semantics; the watched-root set is not the invalidation-input set; and `…Events1` has no compatibility rule for its own `a{sv}` payloads. Three critical findings (F5-1, F5-2, F5-3) mean two teams that obey every AD build a hub and a watcher that cannot interoperate.

---

## 1. Two conformant units

For each finding below, Unit **A** and Unit **B** are staffed independently from the spine + contract alone. Both may point at an exact line for every decision; neither violates an AD as written; the pair is nonetheless incompatible on the wire or on disk.

| Dimension | Unit A choice | Unit B choice | Spine authority both cite |
| --- | --- | --- | --- |
| Who emits `JobStarted/Progress/Finished` | the **hub** (only process that can emit its own `Job*` signals; it supervises the child) | the **job** (AD-37 says the lifetime job owns the child and "publishes lifecycle") | AD-37 line 66/69; AD-38 line 75; contract methods `Emit` only |
| `GetTopicState` for an absent/never-emitted topic | empty `a{sv}` (in-memory, lost on hub restart) | last-known `{state:"idle"}` (rebuilt from the controller's state file) | contract md line 32–35; Convention "write-behind projection… never the authority"; memlog D/NEW-2 |
| Watched roots | exactly the five enumerated in AD-39 | the five + the wallpaper source (it is a derivation input) | AD-39 line 81; AD-40 line 87; shared-data-contract line 115; inherited AD-21/AD-32 |
| Hydration order | hydrate, then track signals | subscribe, then hydrate (apply `seq`) | contract md line 32–35 ("hydrates once … then tracks signals") |
| Adding an optional key to `capture.state` | non-breaking, stays `…Events1` | breaking, becomes `…Events2` (drift test does key-set equality) | AD-34 line 46; contract md line 88; AD-38 line 75 |
| `icme.saved` → converge → auto-prune | one `reactive` line (folds the prune) | two lines: `reactive` + `prune` | AD-42 line 99; AD-30 line 40; shared-data-contract line 45 |
| Daemon absent, speed-test job | publishes nothing; icon never animates | job publishes `speedtest.*`; icon animates | AD-37 line 66; AD-38 line 75; contract md line 17–18 |

Narrative failure on the shared bus: U-B's capture controller (a lifetime job, per AD-37) tries to report lifecycle; the only method it may call is `Emit(topic, payload)`, whose only signal is `DomainEvent`. The hub's caller→topic authorization rejects a topic absent from `event-contract.json` (AD-38). The controller is left with no legal way to say "I started," `GetActiveJobs` is empty, and the wifi animation (Epic 5-4, driven by `JobProgress`) never receives a fraction. Every unit's own drift test passes, because `Job*` is in their constants; the interface between them is simply dead.

---

## 2. Findings

### F5-1 — CRITICAL — Lifecycle signals (`Job*`) have no producer path; AD-37's "job owns the child" and AD-38's "hub is the only emitter" are mutually exclusive

- **Units:** 5-1 "hub process owning `org.dotfiles.Events`" (epics line 32) vs 5-4 "capture controller becomes a resident lifetime job (owns recorder) publishing `capture.state`" (epics line 35).
- **Exact text both satisfy:**
  - AD-37 (spine line 66): "Lifetime jobs (capture recorder, speed test) **publish lifecycle + domain events**. A lifetime job is the long-lived, D-Bus-capable owner that outlives and holds the observed child…"
  - AD-37 (line 69): "Lifecycle and domain events are distinct: **a supervisor infers lifecycle**; only the tool emits domain events."
  - AD-38 (line 75): "exactly one process — the runtime daemon — owns the well-known name `org.dotfiles.Events` and is the signal hub. Jobs and tools emit through the hub's interface and never `RequestName` an `org.dotfiles.*` name…"
  - `event-contract.json`: the only method that injects anything is `Emit {in:[topic:s,payload:a{sv}]}`; `JobStarted`/`JobProgress`/`JobFinished` exist **only as signals** with no corresponding method and no `topics` entry.
- **Incompatibility:** `Job*` signals can only be emitted by the process that owns the interface — i.e. the hub. But the child is owned by the job (AD-37), so the hub cannot infer lifecycle and must not own the child. U-A therefore makes the hub the supervisor (contradicting AD-37's ownership); U-B makes the job the owner but has no way to publish (contradicting AD-37's "jobs publish lifecycle"). `GetActiveJobs` is served by a hub that never learns a job exists; `JobProgress` — the declared driver of the speed-test wifi animation — is unreachable. Two compliant hubs disagree on whether `GetActiveJobs` returns `{job:capture}` or `{}`.
- **Tightening:** Add a hub method `EmitJob(kind:s, phase:s, ...)` (or `EmitJobStarted/Progress/Finished`) with explicit caller→`Job*` authorization, **or** delete `Job*` from the contract and define lifecycle as a hub-internal derivation from job-emitted start/stop topics that are enumerated in `event-contract.json`. Either way, add one spine sentence naming the single supervisor of each lifetime child (the job that spawned it), and pin how `GetActiveJobs` is populated from it.

### F5-2 — CRITICAL — `GetTopicState` has no domain-state authority, retention, absence, or restart semantics; two units legitimately disagree on empty-vs-idle

- **Units:** 5-2 bar consumer binding `GetTopicState` (epics line 33) vs 5-4 capture controller maintaining its state (epics line 35).
- **Exact text both satisfy:**
  - `event-contract.md` lines 32–35: "A consumer needing current state **hydrates once via the hub's `GetTopicState(topic)`** … then tracks signals — it never polls, and **never reads a tool's write-behind state file for truth**."
  - Consistency Conventions (spine line 107): "a tool's own state file is a **write-behind projection** of its event stream, never the authority for a live consumer; on divergence **the event stream wins** and doctor repairs the file."
  - memlog NEW-2: "the hub exposes `GetTopicState(topic)` as the sole domain-state hydration path; consumers never read write-behind files."
  - AD-33 (line 40): `Restart=on-failure` — the hub may restart at any time.
- **Incompatibility:** Nothing pins (a) what a never-emitted / absent-producer / post-restart topic returns, (b) whether topic state survives a hub restart, (c) how "the event stream wins" is enforced when the hub has no retained stream. U-A's hub keeps last payloads **in memory only** (memlog: the backstop is in-memory); after a `Restart=on-failure` the bar hydrates `capture.state` as empty while the recorder is still live — and polling is forbidden, so it never self-corrects. U-B's hub answers `GetTopicState` by reading the controller's write-behind state file — exactly what the convention forbids. Both are compliant readings; the bar cannot be written once to work against both.
- **Tightening:** Pin in the contract: unknown/never-emitted/absent-producer → empty `a{sv}`; retained topic state is in-memory and **does not** survive hub restart; on restart the bar treats empty as unknown and each producer must **re-announce** its current state on connect (define a `*.state` re-announce obligation); the hub is forbidden from reading any tool state file for `GetTopicState`; and pin who runs divergence repair and when (name `doctor`, or drop the repair sentence).

### F5-3 — CRITICAL — The watched-root set is not the invalidation-input set: wallpaper bytes are unwatched, and `icon-mappings` is a file in one contract and a directory in another

- **Units:** 5-3 "enumerated watched roots (AD-39)" + "loop-safety backstop (AD-36)" (epics line 34) vs the inherited `CheckInputsUseCase` / `IInvalidationQuery` (AD-21/AD-32).
- **Exact text both satisfy:**
  - AD-39 (line 81): "the watched roots are an **explicit enumerated allowlist**: the four derivation inputs resolved by `derive.find_*` (**CSG templates dir, WEG effects catalog, icon-templates dir, icon-mappings file**) plus the relocated intent document …"
  - AD-40 (line 87): "watch **only** the AD-39 roots… inotify is not recursive, so each root directory is watched explicitly."
  - AD-36(B) (line 58): "on any event, recompute the input hashes; if unchanged, do nothing."
  - Inherited AD-32 (Phase 4 spine line 52): "an invalidation check MUST recompute input hashes **from the source**"; shared-data-contract line 115: "wallpaper | `sha256(file_bytes)` | the wallpaper file itself."
- **Incompatibility:**
  1. **Wallpaper bytes.** The wallpaper file is a derivation input (its `entry_hash` is `sha256(file_bytes)`), but it is not one of AD-39's five roots. If the user replaces the image *at the same path* (or edits it in place), no watch fires, the daemon never recomputes, the AD-36 backstop never runs, and the AD-21/AD-32 invalidation obligation is silently unmet. U-A obeys the closed allowlist and is blind; U-B, obeying AD-21/AD-32's "all derivation inputs," adds a watch on the wallpaper source and thereby violates AD-40's "only the AD-39 roots."
  2. **`icon-mappings` shape.** AD-39 calls it a *file* and applies the file-root rule ("watched via its immediate parent directory filtered to the exact filename"); shared-data-contract line 118 calls it `icon-mappings/` (a directory) and hashes it with `canonical_hash_dir`. U-A watches the filtered filename; if it is a directory, it watches nothing (silent). U-B watches it as a directory but, per AD-40 (non-recursive), misses nested changes. One unit is blind on this layer; the other violates a different clause.
- **Tightening:** Enumerate the watched set with **exact absolute root paths and file-vs-directory kind**, one row per derivation input (including the wallpaper source path and the resolved `derive.find_*` outputs), and state the invariant that the watched set **equals** the AD-32 checked-input set. If any input is intentionally unwatched, say so and define the compensating detection (this would be the first AD-21 exception and must be explicit). Pin `icon-mappings` as exactly one of {file, directory} and align AD-39 with shared-data-contract line 118.

### F5-4 — HIGH — Hydrate-then-track has no ordering or replay guarantee: a lost event is permanent (polling forbidden) and a late hydration can regress state

- **Units:** 5-2 bar consumer (epics line 33) vs 5-1 hub serving `GetTopicState` (epics line 32).
- **Exact text both satisfy:**
  - `event-contract.md` lines 32–35: "hydrates **once** via the hub's `GetTopicState(topic)` … **then tracks signals**".
  - Consistency Conventions (line 106/109): "state transitions are event-sourced; **nothing polls state**"; "State is pushed, never polled."
- **Incompatibility:** The contract fixes *that* hydration precedes tracking but not the atomicity between them. There is no per-topic sequence number, generation/epoch, subscribe-before-hydrate rule, or replay. U-A subscribes first, then hydrates: a newer event already applied is overwritten by an older hydration (regression) or double-applied. U-B hydrates first, then subscribes: an event in the gap is lost forever and the bar shows stale state permanently, because polling is banned. A fast `recording → idle` around hub restart or bar reload makes the indicator stick on "recording." Both orderings satisfy "hydrate once … then tracks signals."
- **Tightening:** Pin the consumer protocol (subscribe **then** hydrate) and add a monotonic per-topic `seq` (or generation) echoed by both `GetTopicState` and every `DomainEvent`; consumers apply a hydration only when `seq` is not older than the last seen. Simpler alternative: make every `DomainEvent` carry the full authoritative topic state so no hydration race exists. Pin the gap behavior so the two units cannot disagree.

### F5-5 — HIGH — `a{sv}` payloads have no compatibility rule; additive keys are either non-breaking or `…Events2`, and the hub's `Emit` validator is unspecified

- **Units:** 5-3 producer side (`capture.state`, `icme.saved`) vs 5-2 consumer + per-language drift tests (epics lines 33–34).
- **Exact text both satisfy:**
  - AD-34 (line 46): "the JSON carries both names and payload schemas and is the test-time source of truth… **a breaking shape change is `…Events2`**."
  - `event-contract.md` line 88: "A shape change is a breaking change (`…Events2`)."
  - AD-38 (line 75): "The hub pins a caller→topic authorization mapping … and **rejects a non-conforming `Emit`**."
  - memlog D-5: "event-contract.json carries allowed enum values, not just types."
- **Incompatibility:** Payloads are open variant maps (`a{sv}`), and "shape change" is undefined for: adding an optional key (`capture.state` gains `path`), widening a declared enum (add `stopping`), changing `i`↔`d`, or emitting a key subset. U-A treats an added optional key as non-breaking and stays `…Events1`; U-B's drift test compares key sets and the hub rejects the extra key as "non-conforming" — a compliant producer is dropped by a compliant hub. U-B instead migrates to `…Events2` for the additive key while U-A still emits `…Events1`; now the consumer listens on an interface with no producer. Neither side's test fails: each is internally consistent and externally incompatible.
- **Tightening:** State the compatibility contract explicitly in both `.json` (as `compat` metadata) and `.md`: for `a{sv}`, unknown/extra keys are ignored by consumers and **permitted** by the hub; **adding an optional key is non-breaking** (stays `…Events1`); removing/renaming/retyping a declared key, or adding a value to a declared enum, is breaking (`…Events2`). Pin hub `Emit` validation to the declared **required** keys/types only, never set-equality. Add cross-version fixtures (old consumer/new producer and new consumer/old producer).

### F5-6 — HIGH — Job-lifetime handoff is named but not defined; "hands ownership to the daemon (hub)" has no wire mechanism, no reaping owner, and no exit ordering

- **Units:** 5-4 capture controller (epics line 35) vs 5-1 hub that receives the handoff (epics line 32).
- **Exact text both satisfy:**
  - AD-37 (line 66): "a wrapper must never exit while a child it spawned still lives — **if residency is impossible, it hands ownership to the daemon (hub)**."
  - memlog D-2: same rule, "hands ownership to the daemon/hub."
  - AD-38 (line 75) + `event-contract.json`: the only wire method is `Emit(topic,payload)`; topics are enumerable and hub-validated.
- **Incompatibility:** "Hands ownership" has no contract representation: no reserved topic, no fd/PID-transfer method, no authorization entry, and no reaping owner after transfer (a hub that did not `fork`/`exec` the child is not its parent and cannot `waitpid`; it can only watch `/proc`). AD-34's "JSON carries … names" means a `capture.handoff` topic invented by U-A is rejected by any conforming hub. U-A's controller emits an unlisted handoff topic → the hub drops it and the recorder is orphaned or leaks. U-B instead makes the **hub** spawn the child on request — contradicting AD-37's "the lifetime job … holds the observed child" and the capture controller's very design. The unit pair also disagrees on exit ordering: does the wrapper exit only after the hub acks ownership (U-A), or can it exit immediately leaving a race (U-B)?
- **Tightening:** Either (a) define a handoff contract — reserved topic/method (`CaptureHandoff(pid, fd_or_unit)`) with caller→topic authorization, the hub's obligation to become a subreaper/accept the child, and an ack that gates the wrapper's exit — or (b) **reject** handoff and pin "residency is always possible" with the mechanism that guarantees the job stays resident (e.g. systemd `--user` activation of the controller). Pin child reaping ownership and the exact wrapper exit ordering.

### F5-7 — HIGH — `reactive` history trigger collides with the existing `reconcile`/`set`/`prune` paths and with observe-only; "one line per reconcile" is not satisfiable by all compliant units

- **Units:** 5-3 "reactive reconcile runs the existing use cases; `reactive` history trigger (AD-42)" (epics line 34) vs 5-1 "observe-only default; trigger-logged actions + delete audit" (epics line 32).
- **Exact text both satisfy:**
  - AD-42 (line 99): "a **daemon-initiated converge** appends history with the new `reactive` trigger. Adding the value ships **in the same change** as the shared-data-contract enum update and the inspect validator update."
  - AD-30 (line 40): "Every real prune execution appends **exactly one** `history.jsonl` line with `trigger=\"prune\"` and counts; dry-run appends nothing. Automatic execution uses `reconcile --plan` preview followed by logged `reconcile` execution."
  - AD-36(B) / AD-35 (lines 52/58): hash backstop no-ops; "Automatic convergence is **opt-in, ships observe-only first**"; commands "yield the same results with the daemon absent."
  - shared-data-contract line 45: trigger enum `seed|set|reconcile|force`.
- **Incompatibility:**
  1. **Which trigger.** AD-42 says "runs the existing use cases" *and* "appends `reactive`." The existing `reconcile` primitive already appends `trigger="reconcile"`, and a desired-intent change may internally call `wallpaper set` → `trigger="set"` (shared-data-contract line 45). U-A injects a trigger override so the daemon path logs `reactive`; U-B reuses `reconcile` unchanged and logs `reconcile`. Both claim AD-42/AD-35. The inspect validator is updated for one value, and the other's history is "unknown trigger."
  2. **One vs two lines.** One automatic converge-with-deletes is simultaneously an AD-42 `reactive` line and an AD-30 `prune` line. U-A emits `reactive` (folded counts); U-B emits two lines (`reactive` + `prune`). "One line per reconcile" (AD-4 lineage) cannot decide between them, and history consumers see different row counts for the same run.
  3. **Observe-only.** AD-41/AD-35 ship observe-only first; AD-42 says a daemon converge appends history. U-A appends `reactive` while observe-only (a mutation line for a non-mutating run); U-B appends nothing until auto mode is enabled and surfaces observations only via inspect. Same code, different history ledgers.
- **Tightening:** Add an action→trigger→line-count table: daemon converge = exactly one `reactive`; daemon prune = exactly one `prune` (with counts); an inner `set` performed during a daemon converge is **suppressed** and represented by the `reactive` line; observe-only appends **no** history line and exposes observation only through `inspect`. Pin that the shared-data-contract enum + inspect-validator update are a single atomic contract change (AD-42 already says "same change" — make it a merge gate), and add the allowed-trigger enum to `event-contract`-style drift tests so an unknown value fails loudly.

### F5-8 — HIGH — Jobs "publish their own events" (AD-37) vs "the hub is the only `org.dotfiles.*` owner; absent → publish nothing" (AD-38); the daemon-optional promise fails for shell reactivity

- **Units:** 5-4 speed-test job + wifi animation and 5-4 ICME `icme.saved` (epics line 35) vs 5-1/5-2 hub ownership (epics lines 32–33).
- **Exact text both satisfy:**
  - AD-37 (line 66–67): "**Lifetime jobs … publish lifecycle + domain events**"; "**Interactive apps with domain meaning (ICME) publish their own domain event at the meaningful moment**."
  - AD-38 (line 75): "**exactly one process** — the runtime daemon — owns the well-known name `org.dotfiles.Events` … Jobs and tools emit **through the hub's interface** … **if the daemon is absent they publish nothing** (consumers show no state, never a shadow hub). … `producer` is validated by the hub, **never self-asserted**."
  - AD-33 (line 40) / AD-35 (line 52): "The daemon must be **optional**: commands remain authoritative and work with it absent."
- **Incompatibility:** AD-37 says jobs/apps "publish their own domain event"; AD-38 says only the hub publishes and, absent the hub, jobs publish **nothing**. U-A (5-4) reads AD-37 literally and has the speed-test job emit `speedtest.*` directly, so the wifi icon animates with the daemon absent; but that requires either an `org.dotfiles.*` name (forbidden) or an unlisted signal on the hub's interface — rejected by a conforming hub, and `producer` would be self-asserted (forbidden), so this is not AD-conformant. U-B has the job call the hub's `Emit`, so the icon is dead whenever the daemon is absent. The pair disagree on the producer identity the hub stamps (`producer` must be hub-derived from the caller identity — unique name? PID/`SO_PEERCRED`? well-known name?) and on whether a `speedtest.finished` domain event even exists without the daemon.
- **Tightening:** Pick one and state it: either (a) jobs/apps are **not** independent producers — they submit intents to the hub and the hub stamps `producer` from validated caller credentials (unique bus name → exe allowlist), and the "publish their own events" language in AD-37 is scoped to "through the hub"; or (b) define a distinct job publication surface and the daemon-absent behavior (accepting that shell reactivity requires the daemon). Also name the producer-identity source (unique name vs credentials) and pin the absence/no-shadow-hub test.

---

## 3. Lower-tier findings

### F5-9 — HIGH — `desired.json` relocation can make the runtime write a watched root (AD-36 violation) or silently drop existing intent

- **Units:** 5-3 "relocate `desired.json` to `$XDG_CONFIG_HOME/dotfiles/`" (epics line 34) vs 5-1 daemon loop-safety (AD-36).
- **Text:** AD-36(A): roots are "file-wise **disjoint** from everything the runtime writes"; AD-36(B): "The runtime **never writes a watched root**." AD-39 puts `$XDG_CONFIG_HOME/dotfiles/desired.json` **in** the watched set.
- **Incompatibility:** Phase 4's intent file is `state_root/desired.json` and "nothing provisions intent files — user authors them" (p4-3-2 line 48). "Relocate" is undefined: Unit A performs a one-time runtime migration (read old, write new) → it writes a watched root, and the write wakes the watcher (a real feedback edge the in-memory backstop only masks). Unit B changes only the read path → existing users' intent vanishes silently (reader returns `None` → no convergence), with no loud error. Both satisfy "relocated intent document."
- **Tightening:** State that intent is **user/provisioning-authored only** and the runtime never creates or migrates it; pin the missing-file behavior after relocation (loud one-time warning naming the old path, not silent `None`); if a migration ever runs, it must be an explicit user-invoked command, not daemon startup.

### F5-10 — MEDIUM — Watch target vs. dotfile-manager symlinks in `$XDG_CONFIG_HOME`

- **Text:** AD-39 "a file root is watched via its **immediate parent directory filtered to the exact filename (atomic-replace safe)**"; provisioning docs: "config-in-spine: `~/.config/<name>` → spine, backup guard."
- **Incompatibility:** `$XDG_CONFIG_HOME/dotfiles` is frequently a **symlink** into the install spine (that is the provisioning model). If the file is `…`-vs-spine, atomic replacement of the **symlink** is a change in `$XDG_CONFIG_HOME`, not in the watched immediate-parent target, so the watcher misses it; and if the parent is the spine, AD-39's "no watches above a root's immediate parent" may make the runtime watch provisioning-owned paths. Phase 4's reader also **rejects** a symlinked `desired.json` outright (spoofing policy) — so the same layout that is idiomatic for dotfiles is refused. Two units watch/read differently against the same filesystem.
- **Tightening:** Pin how a symlinked `~/.config/dotfiles` (and symlinked `desired.json`) is handled — watch the symlink's containing dir filtered to the name, or resolve and watch the target with an explicit exception in AD-39 — and reconcile AD-39 with the existing symlink-refusal policy.

### F5-11 — MEDIUM — Authorized-topic set vs. deletion triggers: which topics may indirectly cause an automatic prune

- **Text:** AD-38 "**No automatic deletion may be triggered by an untrusted publisher**"; AD-30 automatic prune; AD-41 "observe-only first."
- **Incompatibility:** `icme.saved` (authorized) triggers a converge that may run AD-30 deletes. The caller→topic map authorizes *senders per topic*, not *which topics are delete-capable*. Unit A lets any authorized domain topic trigger a full converge + prune; Unit B restricts convergence-triggering topics to an explicit subset. Both satisfy AD-38 as written; one lets a tool's save cause deletion, the other does not.
- **Tightening:** Pin a `trigger` flag per topic in `event-contract.json` (which topics may initiate convergence, and that convergence in observe-only mode never deletes), and state that only trigger-authorized topics can lead to an AD-30 delete.

### F5-12 — LOW — `GetActiveJobs` carries no state; `JobProgress` is optional, so "animated" cannot be contract-tested

- **Text:** `event-contract.json` `GetActiveJobs {out:[jobs:a{ss}]}`; `JobProgress [job_id, fraction]`.
- **Incompatibility:** The hub may never emit `JobProgress` (no obligation), so a bar relying on it stalls while a bar relying on a timer violates "nothing polls." A `job_id→kind` map cannot express "running/paused."
- **Tightening:** Either require progress cadence for jobs that declare it, or drop the animation dependency and pin a discrete state signal.

---

## 4. Summary of holes to close

| # | Action | Severity |
| --- | --- | --- |
| F5-1 | Give `Job*` a producer path **or** move lifecycle wholly into the hub; pin the single supervisor and `GetActiveJobs` population | CRITICAL |
| F5-2 | Pin `GetTopicState` semantics: empty for unknown/absent, in-memory/no-restart, producer re-announce, hub never reads state files | CRITICAL |
| F5-3 | Watched set = AD-32 checked-input set; enumerate exact roots + file/dir kind (wallpaper bytes, `icon-mappings`) | CRITICAL |
| F5-4 | Pin subscribe-then-hydrate + per-topic `seq`/generation (or state-in-every-event) | HIGH |
| F5-5 | Pin `a{sv}` compatibility: additive optional keys non-breaking, hub validation = required keys only, cross-version fixtures | HIGH |
| F5-6 | Define the handoff contract (method/topic, auth, reaping owner, exit ack) **or** forbid handoff and pin residency | HIGH |
| F5-7 | Pin action→trigger→line-count (converge=`reactive`, prune=`prune`, inner `set` suppressed, observe-only logs none); atomic contract change | HIGH |
| F5-8 | Resolve AD-37 "jobs publish" vs AD-38 "hub-only/absent→nothing"; pin producer identity source | HIGH |
| F5-9 | Pin intent authorship (runtime never writes/migrates a watched root) + loud post-relocation missing-intent behavior | HIGH |
| F5-10 | Pin symlinked `$XDG_CONFIG_HOME/dotfiles` handling; reconcile watch rule with symlink-refusal policy | MEDIUM |
| F5-11 | Pin per-topic delete/converge-trigger authority; observe-only never deletes | MEDIUM |
| F5-12 | Pin job progress obligation or remove the animation dependency | LOW |

**Gate recommendation:** hold the Phase 5 spine at `final` **only after** F5-1..F5-5 are folded into AD-34/AD-36/AD-37/AD-38/AD-39 and `event-contract.json`; F5-6..F5-9 before story breakdown. The `event-contract.json` is currently a names file, not an interface contract — it must carry the producer path, hydration/versioning rules, and payload-compatibility semantics or it cannot be the "test-time source of truth" AD-34 claims.
