# Adversarial-Divergence Review — Phase 5 Spine (AD‑33..AD‑44) + Event Contract + Epics

Date: 2026-09-11
Reviewer: fresh adversarial-divergence pass (no prior context)
Inputs read:
- `ARCHITECTURE-SPINE.md` (AD‑33..AD‑44, conventions)
- `.memlog.md` (C1–C6 resolutions)
- `contracts/event-contract.md` / `contracts/event-contract.json`
- `_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase5.md`
- Grounding: `src/runtime/src/runtime/application/{reconcile,prune,derive,check_inputs}.py`,
  `src/runtime/src/runtime/adapters/{desired_state_reader,invalidation}.py`,
  `src/runtime/src/runtime/cli/main.py`,
  `dotfiles/config/ags/bar/widgets/recording.tsx`

Settled (not re-litigated): file-only spine-root triggers; same-UID trust; `Type=dbus`+`BusName`;
converge-on-start with persisted hash backstop; single-sourced trigger enum; spine-only derivation
inputs; machine-enforced contracts.

Method: construct pairs of units that *each* obey every AD and convention to the letter yet
still build incompatibly; and identify situations no unit addresses.

---

## Verdict

**UNSOUND for parallel story execution as written.** The seven Update touch-points each admit at
least one pair of individually-compliant implementations that are mutually incompatible at
integration, and three required mechanisms have no owning unit at all (resident-job control channel,
transitive ownership handoff, backstop-record schema). None of these are AD contradictions; they are
under-specifications that a story-author will resolve differently per story. All are fixable with
small, local spine/contract amendments — but they must be fixed before epics 5‑1/5‑3 are cut, because
the backstop-record and job-registry shapes are load-bearing for 5‑2/5‑4 hydration.

---

## Scenario 1 — Job registry has no cross-restart identity (`job_id` reuse + missing epoch on job signals/GetActiveJobs)

**Unit A (5‑1, hub/job registry).** Implements `BeginJob(kind)→job_id` with a per-`epoch`
sequential counter (`"1","2","3"`), resets it when the epoch bumps, emits `JobsCleared(epoch)` on
start, and relies on that signal to invalidate consumers.
Satisfies AD‑34: “The hub allocates `job_id` and an **epoch**; on restart the epoch bumps and it emits
`JobsCleared`.”

**Unit B (5‑4, capture controller / bar consumer).** Treats `job_id` as the durable correlation key
(it must, because `ReportProgress`/`EndJob` are keyed only by `job_id`), stores active job ids in a
map, and enters a recording session that survives a hub restart.
Satisfies AD‑34 delivery: “consumers compare the `(epoch, seq)` pair” and “Consumers tolerate
`JobsCleared` by re-hydrating.”

**Incompatibility.** `JobStarted`, `JobProgress`, `JobFinished` carry **no `epoch`**
(`event-contract.json` lines 21–23), and `GetActiveJobs` returns `jobs:a{ss}` with **no `epoch`/`seq`**
(line 17). So the mandated discard rule (“discard any signal whose `(epoch, seq)` is not greater than
the hydrated pair”) is **undefined for jobs**. Signals are at-most-once (contract line 51): a consumer
subscribed across a restart that misses `JobsCleared` holds stale job `"1"`, then a new job reuses
`"1"` in the next epoch, and every `JobProgress`/`JobFinished` is attributed to the wrong session.
Unit A and Unit B each satisfy their cited text exactly.

**Minimal resolution.** Make job identity self-authenticating: include `epoch:u` on
`JobStarted`/`JobProgress`/`JobFinished` (additive, non-breaking), and change `GetActiveJobs` to return
`a{s(ss)}` = `job_id → (kind, epoch)` — or require the hub to generate epoch-prefixed ids
(`"<epoch>:<n>"`). Then `epoch` is comparable without relying on an at-most-once clear signal. Add a
drift-test assertion that `JobsCleared` is the *optimization*, not the correctness mechanism.

---

## Scenario 2 — Watch bound vs hash bound diverge (`icon-mappings` depth unspecified; `canonical_hash_dir` is unbounded)

**Unit A (5‑3, watch installation).** Installs explicit directory watches per level to the depths in
AD‑39: `icon-templates` up to 4, csg templates up to 2, and watches the `icon-mappings` **directory at
one level** (it only ever needs `icons.yaml`).
Satisfies AD‑39: “nested directory roots are watched recursively over their **whole bounded tree**
(`icon-templates` up to 4 levels, csg templates up to 2) with a directory watch per level” — note the
spine names a depth for exactly two roots, and `icon-mappings` is listed as a root without a bound.

**Unit B (5‑1/5‑3, converge + persisted backstop).** Computes input hashes with the existing
`canonical_hash_dir` and `hash_file` (`application/derive.py::_hash_path_input`, mirrored in
`adapters/invalidation.py`), which recurse the **entire** tree with no depth cap.
Satisfies AD‑36: “recompute input hashes; if unchanged, do nothing; else converge.”

**Incompatibility.** A file added at depth 3 under `config/color-scheme-generator/templates` (bound 2)
or depth 5 under `icon-templates` (bound 4) is invisible to the watcher, so it never triggers a
reconcile; but it *does* change the hash that `invoke-when-manual`/`regenerate` and any overflow
re-scan compute. The daemon is therefore silent on inputs it hashes as changed. `icon-mappings` is
worse: Unit A watching one level and Unit B watching four levels are both AD‑39-compliant because the
depth is unspecified for that root.

**Minimal resolution.** Define one shared `bounded_walk(root, depth)` used by **both** watch
installation and input hashing, make the per-root depth part of the machine-enforced event/input
contract (AD‑44), specify the depth for every directory in the enumerated allowlist (including
`icon-mappings`), and assert equality in a drift test. Also pin the recursion semantics: “up to N
levels” must mean the same off-by-one on both sides.

---

## Scenario 3 — Converge-on-start ordering: “no record ⇒ converge” vs “unseeded ⇒ no-op” ⇒ restart loop

**Unit A (5‑1, converge-on-start).** Reads C5 literally: “On start it loads the record; if inputs
differ or **no record exists** it converges, then persists on success.” On a fresh machine there is no
record, so it converges.
Satisfies C5 (memlog line 58) and AD‑41.

**Unit B (5‑1, absence/recovery convention).** Reads AD‑36 literally: “An **unseeded** runtime (no
`current.json`) is a benign no-op — never an error, never a restart.” On a fresh machine there is no
`current.json`, so it does nothing.
Satisfies AD‑36 and the consistency convention “Absence & recovery … never crash-loop.”

**Incompatibility.** Both clauses apply to the *same* first start. Unit A invokes
`ReconcileDesktopStateUseCase.run`, which is fail-fast on a missing `current.json`:
`reconcile.py:159` raises `RuntimeError("nothing to reconcile")`. With the mandated unit
(`Restart=always`, AD‑33 — “name loss is a clean stop, so `on-failure` is insufficient”), that
unhandled exit restarts the daemon; the name is released/reacquired, the record still does not exist,
and the loop repeats. Unit B is fine. Both units obey their own text.

**Minimal resolution.** Pin the start ordering in a new AD or an explicit AD‑36 clarification:
(1) load `current.json`; if absent → log benign no-op and **return without evaluating or writing the
record**; (2) else if record absent/differs → converge; (3) write the record **only after a successful
converge**, and treat any converge failure at start as logged non-fatal (no exit, no restart). The
order is the whole safety property; it is currently unstated.

---

## Scenario 4 — Backstop-record location/format is not machine-enforced, and `desired.json` relocation changes its key set mid-epic

**Unit A (5‑1, converge-on-start backstop).** Persists `$state_root/last-converged.json` containing a
single composite hash over the four derivation inputs **plus `state_root/desired.json`** (Phase 4
location, `adapters/desired_state_reader.py:48`).
Satisfies AD‑36: “A **last-converged input-hash record**, persisted under `state_root` (an output
location, never a watched root).”

**Unit B (5‑3, watch/reconcile backstop).** Persists `$state_root/.runtime/backstop.hash` as a
per-input map, keyed on the **relocated** `$XDG_CONFIG_HOME/dotfiles/desired.json`.
Satisfies AD‑39/5‑3: intent at `$XDG_CONFIG_HOME/dotfiles/desired.json`, backstop “lives under
`state_root`.”

**Incompatibility (two parts).**
1. **Format/location.** The backstop record is *not* in AD‑44’s list of machine-enforced contracts
   (AD‑44 binds only “history trigger enum, `current.json`, `meta.json`, the event contract”;
   line 108). Nothing pins its path, schema, version, key set, or atomicity. Two stories can write
   two files, or the same path in two shapes, with no drift test and no doctor detection.
2. **Sequencing.** 5‑1 ships before 5‑3. Unit A’s key set includes the *old* intent location which
   5‑3 then relocates. After relocation, A’s record is a hash of a file at a path the daemon is
   forbidden to watch (`state_root` is excluded, AD‑39). The record can never “match” again and, worse,
   the daemon may converge on every event forever (hash of a now-absent input), or never, depending on
   how absence is encoded — while 5‑3’s record would match. Also, `$XDG_CONFIG_HOME/dotfiles/` is a
   file root watched via its immediate parent (AD‑39); if that parent does not exist at start there is
   no watch, and under `systemd --user` the unit may not carry `XDG_CONFIG_HOME`, so the daemon
   watches `~/.config/dotfiles` while the CLI wrote elsewhere.

**Minimal resolution.** Add the backstop record to AD‑44 with exactly one machine-checkable definition:
pinned path under `state_root`, `schema_version`, exact key set (the four inputs + intent), atomic
write/replace, and “absent ⇒ mismatch”. Require 5‑3’s relocation to bump `schema_version` (invalidating
old records) in the same change. Pin intent-path resolution to an env the systemd unit is guaranteed to
import, and make provisioning create the parent directory before the daemon is enabled.

---

## Scenario 5 — `reactive` vs `regenerate`: two compliant daemons append different history triggers for the same input change

**Unit A (5‑3, “daemon-initiated converge”).** On a watched derivation-input change, calls the
existing pipeline with `ReconcileDesktopStateUseCase.run(trigger="reactive")`.
Satisfies AD‑42: “a daemon-initiated converge appends `trigger="reactive"`.”

**Unit B (5‑3, “input changed ⇒ regenerate stale”).** On the same change, calls
`RegenerateStaleUseCase`, which internally calls `ReconcileDesktopStateUseCase.run(trigger="regenerate")`
(`application/regenerate.py:123`).
Also satisfies AD‑42: `regenerate` is in the single-sourced enum
`seed|set|reconcile|regenerate|doctor|prune|reactive`, and the trigger came from the definition.

**Incompatibility.** The spine never says which use case a *derivation-input* change maps to versus an
*intent* change. Both are “daemon-initiated converges”; one records `reactive`, the other
`regenerate`, so the history stream is not reproducible across two compliant implementations. A second
fault compounds it: AD‑41 says the daemon logs/executes `regenerate/prune` automatically, and AD‑42
says a real prune appends `trigger="prune"`. A single daemon action that regenerates *and* prunes
therefore appends two lines with different triggers — or one, depending on how the story wraps it —
with no rule saying how many lines one action emits.

**Minimal resolution.** Add a decision table to AD‑42: watched-**intent** (`desired.json`) change ⇒
`reconcile`/`reactive`; watched-**derivation-input** change ⇒ `regenerate`/`reactive`; automatic prune
⇒ exactly one additional `prune` line; and state the invariant “one daemon action emits exactly one
`reactive` line plus at most one `prune` line.” Test the mapping in the drift test.

---

## Scenario 6 — Dev override vs spine-only watch and provenance tripwire: both compliant, mutually exclusive behavior

**Unit A (R‑3/R‑4, derivation resolution).** Implements the env-gated repo fallback in
`derive.find_*` (the memlog names `DOTFILES_DEV_INPUTS_ROOT`) and makes production resolve spine-only.
Satisfies AD‑43: “The repo-ancestor fallback becomes an **explicit opt-in dev override** (env-gated).”

**Unit B (5‑3, watch + doctor provenance).** Watches only the pinned spine locations and implements
the provenance tripwire that surfaces *any* repo-sourced input.
Satisfies AD‑39 (“**explicit enumerated allowlist of SPINE locations** … never the result of
`derive.find_*`”) and AD‑43 (“A runtime provenance check surfaces any repo-sourced input”).

**Incompatibility.** With the override enabled, Unit A legitimately reads a repo template, but Unit B
(a) never watches it, so dev edits do not trigger the daemon while a manual/overflow reconcile does;
and (b) its provenance check fires on an input the override explicitly authorized. No AD states whether
the tripwire is suppressed under the override, whether the daemon refuses to start under the override,
or whether the override is CLI-only. The memlog (C1) asserts “dev-in-repo edit path is handled by
bootstrap propagation, not the daemon,” but that is not in the spine — a story reading only the spine
will implement “watch the override root,” which AD‑39 forbids. Additionally, the env var name/semantics
are single-sourced only in the memlog; AD‑44 does not cover it, so R‑3 and a doc/test could diverge on
the name.

**Minimal resolution.** State in AD‑43: the override is **CLI-only**; `daemon run` refuses to start
(loud, non-zero, no restart-loop) when it is set; the provenance tripwire reports
`(source, expected_for_mode)` and only *fails* for unintended repo reads. Add the override env name,
allowed values, and precedence to the AD‑44 machine-enforced definition set.

---

## Scenario 7 — Observe-only automatic prune vs `trigger="prune"` audit line

**Unit A (5‑1, observability).** Implements AD‑41 literally — “every automatic action
(regenerate/prune) is **logged with its trigger**” — by appending the trigger to `history.jsonl` for
the automatic prune path, including in the observe-only default.
Satisfies AD‑41 and the “trigger-logged actions” story in epic 5‑1.

**Unit B (R‑1, prune audit).** Implements R‑1/AD‑42: “A real prune appends one `history.jsonl` line
`trigger="prune"` with counts; **dry-run appends nothing**.” Observe-only means no deletion, therefore
no line.
Satisfies R‑1 and AD‑42.

**Incompatibility.** What “logged with its trigger” means is unstated: daemon structured log vs the
history audit line. In observe-only mode Unit A creates a `prune` history record for a prune that did
not execute — corrupting exactly the audit trail R‑1 exists to protect, and poisoning `inspect history`
and any downstream “when did we last prune” logic. Unit B creates none. Both compliant.

**Minimal resolution.** Pin in AD‑41/AD‑42: “logged with its trigger” means the structured daemon log
for observe-only/dry-run; the `history.jsonl` `trigger="prune"` line is emitted **iff** at least one
entry was actually deleted, in the same commit as R‑1.

---

## Scenario 8 — No unit owns the resident-job control channel, and “transitive ownership” has no mechanism

**No unit addresses X.** AD‑37 states: “ownership is **transitive**: if a wrapper spawns it and would
exit, ownership is handed to the hub” and “a lifetime job … **report[s] via hub methods**
(`BeginJob`/`ReportProgress`/`EndJob`).” The contract exposes only those three methods plus `Emit`;
there is **no method to adopt an existing (non-child) process, no `job_id`-less registration, and no
way for the hub to observe a process it did not spawn or receive its exit code.** Separately, the
existing UI controls are commands: `dotfiles/config/ags/bar/widgets/recording.tsx` shells
`capture-tool pause|resume|stop`, while 5‑4 turns the capture controller into a *resident* job. The
contract has **no request/command channel** (it is emit-only), so nothing defines how the bar
commands a resident job. The memlog records that today the CLI spawns the recorder and exits, so
“no exit event reaches the bar” — which is precisely the transitive-ownership case AD‑37 claims to
solve.

**Incompatibility/gap.** Two units can be built compliantly: Unit A (5‑4) keeps the resident
controller and makes `capture-tool stop` a thin CLI that … has no defined IPC to the controller;
Unit B (5‑4) has the bar call a hub method that does not exist. A third unit (any tool) that spawns a
wrapper and exits cannot hand ownership to the hub at all — the required API is absent. AD‑37’s
transitive-ownership clause is therefore unimplementable with the shipped contract.

**Minimal resolution.** Either (a) delete the transitive-ownership clause and require the
resident, D‑Bus-capable owner to directly hold the child (making the wrapper pattern non-conforming),
or (b) add an explicit mechanism: a hub `AdoptJob(pid, kind)→job_id` backed by `pidfd`/a supervisor
process, with a stated requirement that the hub can wait on non-children. For control, add a defined
command path — either a `control.<job>` topic delivered by the hub, or state explicitly that control
remains a CLI that signals the resident controller over a named mechanism (and contract it). Today
neither the spine nor the contract mentions control.

---

## Additional situations no unit addresses

These are smaller than the eight above but each is a real integration hole.

- **Unknown-topic policy.** AD‑34 says a new topic is additive/non-breaking; AD‑38 says the hub
  schema-validates every `Emit`. To validate a schema the hub must *know* the topic. The spine never
  says whether the topic namespace is closed (reject unknown) or open (accept unvalidated). Unit A and
  Unit B hubs can differ observably on a tool emitting a new topic.
- **`producer` provenance contradicts same-UID trust.** `DomainEvent` carries `producer:s` and
  `Emit(topic,payload)` carries no producer. Under C3 (no per-sender identity), Unit A sets
  `producer` from a caller-supplied payload field; Unit B derives it from the contract’s
  `topic → producer` table. The bar keys UI on `producer`. Pin which it is (hub-derived from topic is
  the only choice consistent with “not per-sender identity”).
- **Shadow emitters / duplicate delivery.** AD‑38 forbids owning an `org.dotfiles.*` *name* but does
  not forbid a tool from emitting a `DomainEvent` signal on `/org/dotfiles/Events` + interface
  `org.dotfiles.Events1` from its own connection. A consumer matching interface+path (the natural D‑Bus
  way) receives both the tool’s signal and the hub’s re-broadcast. Pin that consumers must match on the
  hub’s resolved unique name, and state the contract forbids direct signal emission (the hub cannot
  enforce it; a lint/drift test on the bar proxies can).
- **`IN_Q_OVERFLOW` has no per-root attribution.** AD‑40 says “re-scan of the affected root,” but an
  inotify queue overflow is per-instance, not per-root. A unit that re-scans one guessed root and a
  unit that re-scans all roots both satisfy the text; the former can miss dropped events in other
  roots. Say “on overflow, re-scan the entire watched root set.”
- **New directories get no watches.** AD‑40 covers atomic replace of *files* inside an existing
  directory but not `IN_CREATE`/`IN_MOVED_TO` of a new subdirectory. A newly created nested tree has no
  installed watches until an overflow re-scan, silently losing its changes.
- **Job method idempotency.** No unit defines `EndJob` twice, `ReportProgress` after `EndJob`, or
  `EndJob`/`ReportProgress` for an unknown/expired `job_id`. Under at-most-once and epoch resets these
  are reachable.
- **`capture.state` after a hub restart.** `capture.state` defaults to `idle` when unset; after a hub
  restart the in-memory topic state is gone (`JobsCleared` invalidates it) while a recording may still
  be running. Nothing requires producers to re-`Emit` current domain state, so the bar can show “idle”
  during an active recording. Decide: hub persists topic state (contradicts `JobsCleared` “topic state
  is invalid”), or consumers treat unknown as unknown (not idle) and producers re-Emit on
  `JobsCleared`.

---

## Summary

| # | Focus area | Divergence | Severity |
| - | --- | --- | --- |
| 1 | job registry | `job_id` reuse; no `epoch` on job signals/`GetActiveJobs`; at-most-once `JobsCleared` | High |
| 2 | watched-root recursion | watch depth ≠ hash depth; `icon-mappings` depth unspecified | High |
| 3 | persisted backstop / reactive | “no record ⇒ converge” vs “unseeded ⇒ no-op” ⇒ `Restart=always` loop | High (crash-loop) |
| 4 | persisted backstop | record path/schema/keys not machine-enforced; `desired.json` relocation changes key set | High |
| 5 | `reactive` semantics | input change ⇒ `reactive` or `regenerate`; multi-line history per action | Medium |
| 6 | spine-only vs dev override | override vs watch allowlist vs provenance tripwire; env name unpinned | Medium |
| 7 | `reactive`/R‑1 | observe-only prune appends a phantom `prune` line | Medium |
| 8 | hub-as-sole-emitter / jobs | no control channel; transitive ownership unimplementable | High |

No scenario requires reversing a settled decision; all are localizations of missing detail. The two
that must be resolved before 5‑1 is cut are #3 (restart loop) and #4 (backstop schema), because 5‑3’s
relocation depends on the latter and 5‑2/5‑4 hydration depends on #1’s final shape.
