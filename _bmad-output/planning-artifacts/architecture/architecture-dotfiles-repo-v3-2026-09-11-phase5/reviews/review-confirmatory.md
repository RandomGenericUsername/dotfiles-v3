# Confirmatory Re-check — Adversarial-Divergence Review

- **Reviewer:** adversarial-divergence (bmad-architecture reviewer gate, confirmation pass)
- **Subject:** `ARCHITECTURE-SPINE.md` (Phase 5, `status: final`, AD-33..AD-44), `.memlog.md`, `contracts/event-contract.md`, `contracts/event-contract.json`
- **Date:** 2026-09-11
- **Constraint:** reviewer does not edit the spine or contract. Findings only.
- **Scope:** confirm the six validate-gate holes (C1–C6) and the AD-43/AD-44 folds are closed, then construct up to **two** new divergences the updated text still permits between two AD-conformant Phase 5 units.

**Verdict:** **CONDITIONAL.** C1–C6, AD-43 and AD-44 are **CLOSED** with direct spine/contract evidence. The update introduced two new under-specifications (ND-1 epoch-scoped identity; ND-2 bounded recursion / nested atomic-replace) that still admit two conformant units building incompatible wire/disk behaviour. Neither is CRITICAL alone; both are fixable by the tightening lines below.

---

## 1. Per-hole verification

| Hole | Verdict | Evidence | Note |
| --- | --- | --- | --- |
| **C1** — AD-36 no longer contradicts AD-37/42; triggers = watched SPINE roots only; `icme.saved` is a UI event | **CLOSED** | AD-36 (`SPINE:57`): "reacts **only** to the watched root set (AD-39)"; AD-39 (`SPINE:80`) watches `<install>/icon-mappings` (ICME save target), excludes consumer pointers + `state_root`; AD-37 (`SPINE:66,68`): ICME emits domain event, "a UI indicator … driven by that tool's domain events only"; AD-42 (`SPINE:98`) only adds `trigger="reactive"`, never a topic trigger; `.memlog.md:54` records "no daemon topic triggers." | `icme.saved` remains a contract topic (`event-contract.md:62`) with no daemon subscriber — consistent, not contradictory. |
| **C2** — Job* signals have a producer path; `job_id` + epoch + `JobsCleared` | **CLOSED** | AD-34 (`SPINE:45`): hub is "broker + job registry and the sole emitter," exposes `BeginJob(kind)→job_id`, `ReportProgress`, `EndJob`, `GetActiveJobs`, `GetTopicState`; hub "allocates `job_id` and an **epoch**; on restart the epoch bumps and it emits `JobsCleared`." AD-37 (`SPINE:65`): "report via hub methods … the **hub** emits the lifecycle signals." Contract md `:30–44`, json `:11–25` match signature-for-signature. | Producer ambiguity F5-1 resolved: jobs call methods, hub emits. |
| **C3** — AD-38 no longer claims per-sender identity auth; sole owner + structural validation + same-UID trust | **CLOSED** | AD-38 (`SPINE:74`): exactly one owner; session bus is a "trusted same-user domain"; "hub enforces **structural validation** — schema, size, and depth caps, and rate … **not** per-sender identity"; threat model documented. Contract md `:72–76` and json `:31–34` state identity = none, structural = schema/size/depth/rate. | Earlier `NEW-1` caller→topic authorization is correctly gone; reverted to same-UID posture. |
| **C4** — AD-33 supervision stack + RequestName fail-fast + never exit 0 before owning | **CLOSED** | AD-33 (`SPINE:39`): `Type=dbus` + `BusName=org.dotfiles.Events`, `Restart=always`, `RestartSec`, tuned `StartLimitIntervalSec/Burst`, `Requires=/After=dbus.socket`, `WantedBy=/After=graphical-session.target`; `RequestName(DO_NOT_QUEUE)`, "fails fast non-zero on contention," "**never exits 0 before owning the name**," releases on SIGTERM. `.memlog.md:57` matches. | BusName versionless vs interface versioned stated (`SPINE:39,116`; contract `:15–23`). |
| **C5** — converge-on-start gated by persisted last-converged hash under `state_root`; unseeded = no-op | **CLOSED** | AD-36 (`SPINE:57`): "**last-converged input-hash record**, persisted under `state_root` … on any event and **on start** … else converge and persist"; unseeded "is a benign no-op … never an error, never a restart; the daemon never seeds." AD-39 (`SPINE:80`): backstop "lives under `state_root`." | Durable (upgrades the old in-memory `.memlog.md:46`). Minor wording hedge: AD-39 says "**If** … persisted" vs AD-36's definitive "persisted" — same location, no behavioural split. |
| **C6** — trigger enum single-sourced + prune line + reactive | **CLOSED (spec)** | AD-42 (`SPINE:98`): enum **single-sourced** `seed | set | reconcile | regenerate | doctor | prune | reactive`; prune appends **exactly one** `trigger="prune"` with counts (dry-run nothing); daemon converge appends `trigger="reactive"`; new values ship with validator + shared-data-contract. AD-44 (`SPINE:110`) enforces one machine-checkable definition + drift test. | Dead value `force` dropped (`.memlog.md:59–61`). Residual is execution risk only: the actual `prune` history line and enum change are scheduled as a remediation story (`.memlog.md:61`), not yet in code. Spec hole is closed. |
| **AD-43** — spine-only inputs + verify content + provenance | **CLOSED** | `SPINE:104`: production resolves inputs from install spine only; repo fallback is env-gated dev override; missing input = loud typed failure; `verify` asserts **content** (icons.yaml + siblings, non-empty dirs, effects.yaml); runtime provenance check surfaces repo-sourced input. | — |
| **AD-44** — machine-enforced contracts | **CLOSED** | `SPINE:110`: exactly one machine-checkable definition per shared contract (trigger enum, `current.json`, `meta.json`, event contract); prose descriptive; drift test fails on disagreement. Contract md `:8–10` + json both declare it. | — |

**All prior holes CLOSED. No STILL-OPEN.**

---

## 2. New divergences still permitted

### ND-1 — HIGH — Epoch-scoped identity is unspecified: `seq` reset, `_seq` type, and `job_id` reuse

**Units:** 5-1 hub (`org.dotfiles.Events` owner) vs 5-2 bar consumer hydrating `GetTopicState`/`GetActiveJobs`.

**Exact text both satisfy**
- `event-contract.md:52–54`: "`seq` is a per-topic monotonic counter (u) incremented by the hub; the hub carries an `epoch` (u) that bumps on restart, at which point it emits `JobsCleared`."
- `event-contract.md:50–51`: "discard any signal whose `seq` ≤ the hydrated `_seq`."
- `event-contract.md:34`: `GetTopicState` returns `state:a{sv}` "(includes `_seq`)" — the `_seq` value is a **variant**, type unpinned.
- `event-contract.md:33`: `GetActiveJobs` → `a{ss}` (`job_id`→kind), **no epoch**.
- `event-contract.json:24–30`: `JobsCleared:[epoch:u]`; ordering "per-topic monotonic seq (u); hub epoch (u) bumps on restart."
- `SPINE:119`: per-topic monotonic `seq`; subscribe-before-read, hydrate.

**Divergence**
1. **`seq` reset on epoch bump.** Unit A's hub resets each topic's `seq` to 0 on restart (new epoch); Unit B's hub keeps `seq` globally monotonic across epochs. Both satisfy "per-topic monotonic" because the contract never scopes monotonicity to an epoch. Consumer C, after `JobsCleared`, hydrates `_seq=500` from a pre-restart topic (hydration crossed the restart) and then drops every post-restart `DomainEvent` with `seq ≤ 500` — a permanent blank bar against A. No `epoch` is returned by hydration, so C cannot tell which regime it is in.
2. **`_seq` variant type.** Because the value rides inside `a{sv}`, A may encode it `u` and B `x` (or `s`). The comparison `seq ≤ _seq` across mismatched scalar types is undefined (and `u` wraps at 2³²). `DomainEvent.seq` is fixed `u`, but the hydrated side is not.
3. **`job_id` reuse across epochs.** A may reset its `job_id` counter per epoch (`job-1` after every restart); B uses globally monotonic ids. A consumer holding `JobStarted(job-1, epoch N)` then receives `JobProgress(job-1)` from epoch N+1 and attributes progress to the wrong job. Nothing in AD-34/AD-37 or the contract forbids reuse, and `GetActiveJobs` carries no epoch to disambiguate.
4. **Never-emitted topic.** The contract does not pin `GetTopicState` for a topic never emitted (`{}` vs `{_seq:0}` vs error). A consumer using the drop rule has no seed threshold on the first event; A and B may drop or accept it.

**Tightening (pick one per item)**
- Return `epoch` from `GetTopicState`/`GetActiveJobs` (or add `GetEpoch`); state that `seq` and `job_id` are **epoch-scoped and reset to 0 on bump** (or explicitly never reset — choose), and require `_seq` be typed `u`.
- Pin never-emitted/absent topic → `{_seq: 0}` with the producer re-announcing on connect.

---

### ND-2 — HIGH — "Bounded recursion" and nested atomic-replace are unpinned in the watched-root model

**Units:** 5-3 watched-root daemon (AD-39/AD-40) vs a provisioning/verifier unit asserting watch completeness (AD-43 verify), or two daemon builds.

**Exact text both satisfy**
- `SPINE:80`: "**No watches above a root's immediate parent**; a file root is watched via its immediate parent filtered to the exact filename (atomic-replace safe); nested directory roots are watched with **bounded recursion**."
- `SPINE:86`: "Because inotify is non-recursive, **bounded recursion is implemented explicitly**"; "**re-establish a file watch after an atomic replace**."
- `SPINE:86`: "on **`IN_Q_OVERFLOW`** perform a **full re-scan of the roots**."
- `SPINE:80`: watched roots include `<install>/config/color-scheme-generator/templates`, `<install>/icon-templates`, `<install>/icon-mappings` (directories), `<install>/config/weg/effects.yaml` (file).

**Divergence**
1. **Recursion bound is unquantified.** "Bounded recursion" admits depth 1 (immediate children) in Unit A and full-subtree in Unit B; both are AD-conformant. A file replaced inside a subdirectory (e.g. `templates/sub/x.css`) fires in B and is missed in A. The same split recurs on `IN_Q_OVERFLOW`: "full re-scan of the roots" resolves to immediate children in A and subtree in B, so one converges and the other reports no change.
2. **Nested atomic-replace is uncovered.** The re-establish obligation names only "a file watch." For a file that is *not* an enumerated file root but lives inside a recursive directory root, rename-over replacement (`IN_MOVED_TO` into a subtree, or a subdirectory swapped in) is not addressed: A relying on directory-level `IN_MOVED_TO` recovers; B holding a per-inode watch on the pre-replace file silently misses the change (or double-delivers).
3. **Clause tension.** "No watches above a root's immediate parent" reads as a recursion prohibition immediately before "nested directory roots are watched with bounded recursion" — an implementer can legitimately cite either sentence for opposite watch graphs.

**Tightening**
- Pin a numeric recursion depth per root (and assert the file-root case is parent-filtered, directory-root case is recursive to depth N).
- State that replacement of any watched entry at any depth is recovered via the parent directory's `IN_MOVED_TO/IN_CREATE` (re-establish only applies to direct file watches), and that `IN_Q_OVERFLOW` re-scan covers the same depth as the watch graph.

---

## 3. Contract-semantics checklist

| Semantics | Result | Citation |
| --- | --- | --- |
| seq/epoch | **DIVERGENCE (ND-1)** — reset scope, `_seq` type, `job_id` reuse unpinned | md `:34,50–54`; json `:24–30` |
| hydrate-before-read | **PARTIAL** — subscribe-then-read + drop `≤ _seq` is pinned (`md:49–51`); pre-hydration signal buffering, single-connection ordering, and never-emitted reply are not (folded into ND-1.4) | md `:46–56` |
| additive-vs-breaking | **UNDERSPECIFIED (minor)** — rule enumerates **fields** only; adding a new **method/signal** or a new **topic** is neither declared additive nor breaking, so one unit keeps `…Events1` and another bumps `…Events2` | AD-34 `SPINE:45`; md `:22–23`; json `:7–10` |
| BusName versionless vs interface versioned | **CONSISTENT for v1; v2 coexistence unpinned** — no rule for whether `Events2` shares bus name/object path or moves them (breaks introspection-based binding) | AD-33 `SPINE:39`; `SPINE:116`; md `:15–23`; json `:3–10` |
| watched-root recursion/atomic-replace | **DIVERGENCE (ND-2)** — depth bound and nested replace uncovered | `SPINE:80,86` |

---

## 4. Residual notes (not blockers)

- C5 wording: AD-39 (`SPINE:80`) says the backstop "**if** persisted" while AD-36 (`SPINE:57`) says it **is** persisted; harmonize to remove the hedge.
- C6 execution debt: AD-42/AD-44 are correct in spec, but the actual `prune` history append and enum update are still a scheduled remediation story (`.memlog.md:61`); a daemon shipped before it violates AD-42's premise.
- AD-38 keeps a `producer:s` member on `DomainEvent` (`md:43`) while validation is explicitly non-identity (`md:72–76`); the field is advisory/self-asserted. Acceptable under same-UID trust, but the drift test must not assert it as authoritative.
- AD-34 (`SPINE:45`) says a newly-required field is breaking; `a{sv}` payloads cannot express "required," so "required" is enforced only by the hub's per-topic schema (`md:58–64`), not by the D-Bus signature — consistent, but worth stating.

## 5. Verdict

**CONDITIONAL — proceed only after ND-1 and ND-2 are tightened.** Prior CRITICAL/HIGH holes C1–C6 plus AD-43/AD-44 are genuinely closed with citable text; the remaining risk is confined to epoch-scoped delivery identity and the watch-graph depth/atomic-replace contract.
