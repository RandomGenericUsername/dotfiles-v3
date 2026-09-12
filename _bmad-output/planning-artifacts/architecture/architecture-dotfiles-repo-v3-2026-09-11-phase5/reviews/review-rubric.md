# Rubric-Walker Review — Architecture Spine, Phase 5 Reactive Runtime

- **Reviewer:** rubric walker (bmad-architecture VALIDATE gate)
- **Subject:** `ARCHITECTURE-SPINE.md` (2026-09-11-phase5, status `final`), its `.memlog.md`, companions `contracts/event-contract.md|json`
- **Inputs read:** driving input `epics-dotfiles-runtime-phase5.md`; inherited spines `architecture-dotfiles-repo-v3-2026-08-18` (esp. AD-19), `...-2026-09-07` (+ `delta-phase3-digest-2026-09-10`), `...-2026-09-11`; `shared-data-contract.md`; brownfield code under `src/runtime`, `src/gui-tools`, `dotfiles/config/ags`, `src/provisioning`.
- **Method:** walk each rubric line against the spine, the named companions, and the actual codebase. Read-only — the spine is not edited.
- **Verdict:** **CONDITIONAL REJECT — the reactivity contract (AD-34/37/39/42), the operational envelope (AD-33/41), and the driving input's shell-reactivity capability are not closed; the spine must resolve F1–F6 before epics/stories freeze.**

---

## Rubric checklist result

| Rubric line | Result |
| --- | --- |
| Fixes the real divergence points for the level below and misses none | **NO** — resident-job lifecycle (F3), desired.json writer/ownership (F6), daemon concurrency model (F16), operational env (F1) are unresolved divergence points. |
| Every AD's Rule is enforceable and actually prevents its stated divergence | **PARTIAL** — AD-36's "reacts only to watched roots" contradicts AD-37/epics (F2); AD-42's premise is already false (F5); AD-33 lacks restart backoff (F10); AD-34's shell-side drift test has no harness (F8); AD-38's delete-trust rule misses the filesystem trigger (F9). |
| Nothing under Deferred could let two units diverge | **WEAK** — systemd-unit provisioning mechanics (F1/F6), the Python D-Bus client + daemon multiplexing model (F16), and the `desired.json` writer (F6) are all divergence surfaces left to implementation. |
| Named tech verified-current | **YES** — session D-Bus, Gio/GIR via `gi://` (network.tsx), `systemd --user Type=simple`, uwsm (present in `dotfiles/provisioning/packages.yaml`), inotify non-recursive. Caveat: `IN_Q_OVERFLOW` is named while the library is deferred (F12); no GJS test runner (F8). |
| Ratifies rather than contradicts the brownfield codebase | **PARTIAL** — contradicts the shipped `state_root/desired.json` reader path (F6) and the stale named companion enum (F5); structural seed paths contradict AD-13's nested layout (F11). |
| Covers the driving input's capabilities (`epics-...-phase5.md`) | **NO** — `icme.saved → regeneration` mechanism is not expressible under AD-36 (F2); capture indicator elapsed cannot be reconstructed from the contract (F4); resident-job capability has no owner (F3). |
| No new AD weakens/contradicts an inherited one | **YES** — AD-35 narrows AD-12 explicitly and AD-12 is preserved for the core; the only defects are citations (F15). |
| Every dimension the altitude owns is decided, deferred, or an open question — especially operational/environmental envelope | **NO** — the daemon's session target / environment import (F1), resident-job supervision (F3), hub-restart re-hydration (F7), daemon logging destination, and interactive-shell environment are neither decided nor listed under Deferred. |

---

## Findings

### F1 — CRITICAL — Operational/environmental envelope: the systemd daemon has no wayland/Hyprland/session environment, target, or ordering

- **Evidence:** AD-33 pins only `Type=simple`, `Restart=on-failure`, and `ExecStart=dotfiles-runtime daemon run`; its Stack row says `systemd --user | system-provided (uwsm-managed session)`. `.memlog.md:25` explicitly raised the open question — "decide the unit's session target (graphical-session.target) + env import" — but the finalized spine's Deferred block (lines 173–177) reduces this to "provisioning mechanics" and silently drops the target/env item. The daemon's whole job is to run the existing use cases, which end in `hyprctl reload`, `hyprctl hyprpaper wallpaper`, and an AGS restart — all of which require `HYPRLAND_INSTANCE_SIGNATURE`, `WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR`, and a live `DBUS_SESSION_BUS_ADDRESS` in the unit's environment. A default `systemd --user` unit does **not** inherit those.
- **Why it blocks:** AD-33's stated prevention ("a Hyprland reload killing the reactive loop") is unenforceable if the daemon can start but cannot talk to Hyprland/AGS; and "every dimension the altitude owns … especially the operational/environmental envelope" is not satisfied. `graphical-session.target` + `systemctl --user import-environment`/uwsm ordering is exactly the divergence two implementers will resolve differently.
- **Hole to close:** a rule pinning the unit's session target (and ordering after the compositor/hyprpaper socket is ready, mirroring the existing `autostart.lua` gate) and the environment-import mechanism; or an explicit Deferred entry naming it as an implementation decision with its invariant (the daemon must observe the same `XDG_RUNTIME_DIR`/`WAYLAND_DISPLAY`/bus address as the compositor).

### F2 — CRITICAL — AD-36 forbids the exact reaction the driving input requires (`icme.saved → daemon triggers regeneration`)

- **Evidence:** AD-36(A): "the daemon reacts **only** to the **watched root set** defined by AD-39". AD-39 enumerates **filesystem** roots (four `derive.find_*` inputs + `desired.json`) — no event topic. Meanwhile `epics-dotfiles-runtime-phase5.md:35` requires "ICME emits `icme.saved` on save → daemon triggers regeneration", and AD-37 mandates ICME "publish their **own domain event at the meaningful moment** (on save, not exit)". `event-contract.json` carries `icme.saved` as a first-class topic. Under the spine as written, the hub is allowed to *receive* the event but AD-36 forbids it from being a trigger; the only lawful trigger is ICME's write to the watched `icon-mappings/icons.yaml` (verified: `lib/inputs.ts:102`, `find_icon_mappings`).
- **Why it blocks:** the spine and its driving input name two different trigger mechanisms for one convergence, and a story can obey either. Either the contract event is an orphan (no consumer) or AD-36 is violated. This is a genuine divergence point the spine was supposed to fix.
- **Hole to close:** decide whether the daemon converges on filesystem watch **or** on authorized `DomainEvent` topics, and say it in AD-36; if both, define precedence and the loop-safety/authorization interaction with AD-38.

### F3 — HIGH — Resident lifetime-job lifecycle (capture controller, speed-test job) has no owner, spawner, or supervisor

- **Evidence:** AD-37 introduces "lifetime jobs … the long-lived, D-Bus-capable owner that outlives and holds the observed child" and epics 5-4 requires the capture controller to "become a resident lifetime job (owns recorder)". But no AD decides **who launches and supervises that resident process** — the only supervised process the spine pins is the daemon (AD-33). Today the capture controller is a short-lived CLI (`src/gui-tools/capture-tool/bin/capture-tool`: `emit()` exits; the bar polls `capture-tool status` at `recording.tsx:40`). Moving it to resident changes its launcher, its PATH ownership, and its failure semantics, all currently unspecified.
- **Why it blocks:** "fixes the real divergence points for the level below and misses none" — one story can make the bar spawn it, another can add a second systemd unit, a third can have the hub own it; the three are incompatible on restart and on "who emits when the daemon is absent" (AD-38).
- **Hole to close:** classify where each lifetime job lives (systemd unit / hub child / bar child), who supervises it, and what happens on daemon absence. The same applies to the `speedtest` job (no tool exists yet — `src` has none).

### F4 — HIGH — `capture.state` cannot reconstruct the recording timer; the contract omits the recorded start

- **Evidence:** Consistency Conventions (line 106): continuous display "derives from a monotonic clock plus one recorded start, never from re-reading a state file on a timer". But `event-contract.json:23-27` pins `capture.state` payload as `{ "state": "s" }` only, and `GetTopicState("capture.state")` returns that same payload. The shipped tool records `started_at`/`paused_seconds` and computes `elapsed_seconds` (`capture-tool:269-280`). A bar that hydrates after a bar/hub restart (or misses the `idle→recording` transition) has no start to anchor a monotonic clock to, so it cannot render `MM:SS` without polling — the exact anti-pattern the phase removes.
- **Why it blocks:** the driving capability is "recording indicator … reacts to the capture lifecycle, no polling"; the contract as pinned cannot satisfy it for the hydration path it also mandates.
- **Hole to close:** extend the `capture.state` schema (e.g. `started_at` epoch/monotonic or `elapsed_seconds` at emit) in `event-contract.json`, or pin that the bar starts its clock on receipt and accepts loss of elapsed across its own restart.

### F5 — HIGH — AD-42's enforcement premise is already false: the named history-trigger enum is stale against shipped code

- **Evidence:** AD-42: "No unit may introduce or accept a history trigger value absent from the contract." The contract AD-42 names is `shared-data-contract.md`, whose history line is `"trigger": "seed|set|reconcile|force"` (line 45). Shipped code uses six values: `regenerate` (`application/regenerate.py:123`), `doctor` (`application/doctor.py:308`), plus the four — enforced by `reconcile.py:68` and duplicated in `inspect.py:71,493`. So two trigger values already exist in production absent from the contract. (AD-30 also specifies a `prune` trigger, which the shared contract never lists and the validator does not accept.)
- **Why it blocks:** AD-42 is billed as a shared-contract gate, but its reference document is not verified-current, so the gate cannot be enforced. It also undercuts "named tech verified-current" / "ratifies the brownfield codebase".
- **Hole to close:** reconcile `shared-data-contract.md`'s trigger enum with code (and the pending `reactive` value) as an explicit spine companion update, and state where the enum actually lives (the validator sets are duplicated in two modules today).

### F6 — HIGH — The relocated `desired.json` has no owner/writer, no migration, and a docstring that contradicts the loop-safety rule

- **Evidence:** AD-39 pins the intent document at `$XDG_CONFIG_HOME/dotfiles/desired.json` and AD-36 says "state_root is pure output, and intent moves out of it". But no AD assigns the writer/owner of that path, and:
  - the shipped reader reads `state_root/desired.json` (`adapters/desired_state_reader.py:31,48`); the Phase 4 implementation artifact states the reader sits beside `current.json`/`history.jsonl` (runtime-owned state dir, AD-5);
  - the Phase 4 story explicitly defers writing — "`desired.json` WRITING from any command (still nothing provisions intent files — user authors them)" (`p4-3-2-planner-wiring.md:48`) — while `apply_wallpaper.py:17`'s docstring claims the use case "updates desired state and delegates". If that is ever realized, the runtime writes a **watched root**, directly violating AD-36(A) ("the runtime never writes a watched root") and re-introducing the feedback loop the spine exists to prevent.
  - no statement covers migration of an existing `state_root/desired.json` or the default `XDG_CONFIG_HOME`.
- **Why it blocks:** this is an unresolved divergence point on a file the daemon watches for its entire trigger surface.
- **Hole to close:** name the intent-file writer, its ownership zone, and the migration/back-compat rule; correct or remove the apply-use-case claim; and explicitly state that if any runtime command writes intent, AD-36's disjointness rule is amended rather than silently broken.

### F7 — MEDIUM — Hub restart is not recoverable by consumers: no re-hydration trigger

- **Evidence:** `event-contract.md:32-35` mandates "hydrates once via `GetTopicState`/`GetActiveJobs`, then tracks signals — it never polls". AD-33 gives the hub `Restart=on-failure`. On a hub restart the in-memory domain state (AD-36's backstop is "held in memory") is gone; a consumer that hydrated before the restart has no signal telling it to re-hydrate, so it shows stale/absent state until the next unrelated event. The absence conventions (line 111) say participants tolerate each other's absence, but say nothing about **re-hydration after the hub returns**.
- **Why it matters:** this is an unhandled recovery path the "Absence & recovery" dimension claims to own.
- **Hole to close:** require consumers to watch `NameOwnerChanged` on `org.dotfiles.Events` and re-hydrate on re-own; or make the hub re-emit current topic state on startup.

### F8 — MEDIUM — AD-34's per-language drift test is unenforceable on the shell side

- **Evidence:** AD-34 / the Contract-enforcement convention require "each language bakes constants and a drift test asserts both". The Python side has pytest. The GJS/AGS bar (`dotfiles/config/ags/`) has **no** `package.json`, no test runner, and no test files (verified). ICME has a `tests/` dir with `.mjs` files, but the bar world AD-34 binds has no harness.
- **Why it matters:** AD-34's Rule ("the JSON … is the test-time source of truth") cannot be enforced for half the contract as the repo stands; two shell implementations can drift with no gate.
- **Hole to close:** name the shell-side test mechanism/runner, or defer it explicitly with the invariant that the bar's constants must be generated/asserted against `event-contract.json`.

### F9 — MEDIUM — AD-38's delete trust boundary gates D-Bus publishers but not the filesystem trigger

- **Evidence:** AD-38: "No automatic deletion may be triggered by an untrusted publisher." But the daemon's actual trigger is a watched-root filesystem event (AD-36/39/40), and any local process can write a derivation input or `desired.json`. The only deletion bound on that path is the AD-30 floor plus "observe-only first". The rule's "publisher" language addresses the wrong threat surface for automatic deletion.
- **Hole to close:** state the trust model for the filesystem trigger (local-user-only assumption is acceptable, but must be explicit) and keep the AD-38 rule scoped to the bus.

### F10 — MEDIUM — AD-33's `Restart=on-failure` has no backoff, contradicting the crash-loop convention

- **Evidence:** AD-33 pins `Restart=on-failure` only; `.memlog.md:21` records "+ backoff", but the spine dropped it. The consistency convention (line 111–112) says "no participant crash-loops" and "logged and retried with backoff". `systemd`'s default start-limit eventually stops it, but the Rule as written does not ensure backoff and does not name `RestartSec`/`StartLimitIntervalSec`.
- **Hole to close:** pin the backoff parameters or cite systemd defaults explicitly.

### F11 — MEDIUM — Structural seed file paths contradict AD-13's nested layout

- **Evidence:** `ARCHITECTURE-SPINE.md:163-166` writes `src/runtime/ports/event_bus.py` and `src/runtime/adapters/dbus_event_bus.py`, but the same block writes `src/runtime/src/runtime/daemon/`. The as-built layout is the nested hexagon `src/runtime/src/runtime/{domain,ports,adapters,application,cli}` (AD-13). The first two paths are wrong and internally inconsistent with the third.
- **Hole to close:** correct the seed to the nested paths; ideally state the daemon's placement relative to the existing layers (is it `adapters/daemon/`, `application/daemon/`, or a sibling?).

### F12 — LOW — `IN_Q_OVERFLOW` is inotify-specific while the mechanism is deferred

- **Evidence:** AD-40 pins overflow recovery on `IN_Q_OVERFLOW`; the Stack defers the "File-event source (inotify)" library. If the eventual library does not surface the same constant, the AD names a mechanism it has not chosen. Acceptable if "inotify" is the committed mechanism, but then the Stack should not call it deferred.

### F13 — LOW — AD-39 says "icon-mappings file", but `find_icon_mappings` can return a directory

- **Evidence:** `derive.find_icon_mappings` returns `install_spine/"icon-mappings"` when it is a directory of YAML files (`derive.py:200-205`) or the `icons.yaml` file. AD-39's enumerated set says "icon-mappings file". Also `find_icon_templates` has a legacy second location. The watch configuration must be derived from the resolved path, not a hard-coded shape — worth stating.

### F14 — LOW — The caller→topic authorization mapping is "pinned" but is not a named artifact

- **Evidence:** AD-38 says the hub "pins a caller→topic authorization mapping (allowed sender identity per topic)"; `event-contract.json`'s `topics[].producer` is a display name (`ICME`, `capture controller`), not a D-Bus sender identity. The mapping has no home in the companions. This is internal to one hub, so low risk, but "pinned" implies an artifact.

### F15 — LOW — AD-36 mis-cites AD-11, and the watch-depth rule is under-specified for dev-mode roots

- **Evidence:** AD-36(B) ends "The runtime never writes a watched root (AD-11 restated)". AD-11 governs runtime writes under the **install spine** post-seed; it says nothing about watch disjointness (and the watched `desired.json` is not under the install spine). Separately, AD-39's "no watches above a root's immediate parent" is stated in terms of `<install>/config`, but `find_*` can resolve to repo-ancestor paths in a dev checkout (`derive.py:73-91`), so the depth rule's real bounds are unstated.

### F16 — MEDIUM — The daemon's concurrency model is deferred to implementation with no invariant

- **Evidence:** Deferred line 173 defers "Concrete Python D-Bus client library and inotify library" and says "prefer a GLib/sync client over an asyncio-first one", but AD-35/34 never state how `daemon run` multiplexes three concurrent sources — inotify events, D-Bus method calls (`Emit`/`GetTopicState`/`GetActiveJobs`), and a synchronous reconcile that must not block the hub's signal serving. Two implementers can pick a GLib main loop vs an asyncio bridge and produce differently-behaving daemons while both claim AD-35's "core synchronous, edges choreographed".
- **Hole to close:** pin the daemon's run-loop model (e.g. GLib `MainLoop` with reconcile on a worker/idle callback) or state the invariant it must preserve (D-Bus responsiveness during a reconcile).

---

## Deferred-block audit

| Deferred item | Can two units diverge? | Note |
| --- | --- | --- |
| Python D-Bus client + inotify library | Yes (medium) | Sync constraint stated, but daemon multiplexing model unstated (F16); `IN_Q_OVERFLOW` presumes inotify (F12). |
| User-systemd-unit provisioning mechanics | Yes (high) | Session target + env import dropped from spine (F1); `cli_tools` role owns install, no role writes `~/.config/systemd/user/`; bootstrap-vs-role duplication risk. |
| Pinned-entry lifecycle | Low | Carried from Phase 4; AD-30 floor protects. |
| ICME events beyond regeneration | Yes (low/med) | Interacts with F2 (event vs filesystem trigger). |
| Phase 6 items | No | Correctly out of scope. |

---

## Capability coverage (driving input)

| Epic capability | Spine coverage | Gap |
| --- | --- | --- |
| 5-1 daemon foundation, unit provisioning, hub, status, observe-only, kill switch, trigger logs, delete audit | AD-33/38/41 + Deferred | Unit env/target (F1); logging destination unnamed. |
| 5-2 contract + port/adapter + bar consumer + drift tests | AD-34 | Shell-side test harness missing (F8); caller auth mapping unartifacted (F14). |
| 5-3 enumerated roots, inotify/coalesce/overflow, loop safety, relocate desired.json, reactive trigger | AD-36/39/40/42 | desired.json writer/ownership/migration (F6); stale trigger enum (F5). |
| 5-4 capture controller resident job; bar indicator; speed-test job; ICME `icme.saved` | AD-37 | Resident-job lifecycle owner (F3); elapsed reconstruction (F4); `icme.saved` trigger not expressible under AD-36 (F2). |
