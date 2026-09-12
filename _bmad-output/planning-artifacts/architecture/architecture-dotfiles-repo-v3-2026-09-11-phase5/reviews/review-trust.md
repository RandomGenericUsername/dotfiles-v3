---
review: trust & security
gate: VALIDATE (ad-hoc lens)
scope: Phase 5 Reactive Runtime — session-bus event hub, caller→topic authorization, daemon blast radius
artifacts:
  - ARCHITECTURE-SPINE.md (AD-33..AD-42; esp. AD-38)
  - .memlog.md
  - contracts/event-contract.md
  - contracts/event-contract.json
  - _bmad-output/planning-artifacts/epics-dotfiles-runtime-phase5.md
  - architecture-dotfiles-repo-v3-2026-09-11/ARCHITECTURE-SPINE.md (AD-30, inherited)
reviewer: trust & security lens
created: 2026-09-11
verdict: FAIL (blocking) — AD-38's caller→topic authorization is not enforceable as specified on a session bus; forged signals are trivially possible; runtime payload validation is absent.
edited_spine: false
---

# Trust & Security Review — Phase 5 Reactive Runtime

## Verdict

**FAIL / NOT READY (blocking).** AD-38 asserts a "trust boundary" and a
"caller→topic authorization mapping (allowed sender identity per topic)" that
the session D-Bus cannot supply. Any process running as the same user can call
`Emit`, can call `GetTopicState`/`GetActiveJobs`, can emit the `DomainEvent`
signal directly to consumers, and can race to own `org.dotfiles.Events`. The
contract names no authentication mechanism, no runtime payload validator, and no
threat model. As written, AD-38 provides false assurance; the hub is a choke
point, not an authorization boundary. The rest of the design (AD-30 floor,
write-behind convention, absence conventions) is sound but does **not** bound
the regeneration/integrity/DoS blast radius.

This is a spec-level failure, not an implementation nit. Do not start Epic 5-1/5-2
until the decisions in "Concrete minimal decisions" are folded into AD-38 (and
the contract).

---

## 1. Threat-model assessment: **absent**

There is no stated threat model anywhere in the spine, memlog, or contract:

- No assets, adversaries, capabilities, or trust boundaries are enumerated.
- The phrase "trust boundary" appears only as AD-38's title; the rule that
  follows never says **who** is untrusted or **why the hub can distinguish
  them**.
- The epics risk table (`epics-dotfiles-runtime-phase5.md:53`) lists
  "Bus-name contention / forged events → AD-38 single owner + caller→topic
  authorization" as if solved. It is not.
- No security NFR, no audit/failure mode, no assumption that the session bus is
  hostile.

Consequence: the authorization claim is untestable and unimplementable, because
the required capability (stable caller identity) is never defined.

**Finding S-00 (High, meta).** No threat model. The design cannot be validated
for security until it states the adversary and the trust boundary. Everything
below is the concrete fallout.

---

## 2. The central question: is caller→topic authorization enforceable?

**No — not by the mechanisms the spine could plausibly mean.** Session-bus facts
(standard `dbus-daemon`, the common default `session.conf` allows all same-user
connections to `send_destination="*"`, `own="*"`, eavesdrop):

| "Sender identity" candidate | Enforceable? | Why |
| --- | --- | --- |
| Well-known name | **No/void** | AD-38 forbids producers from owning `org.dotfiles.*` names (spine:75). A producer has no name to allowlist. |
| Unique connection name (`:1.N`) | **No** | Rotates per connection; any process can obtain one. Not a stable identity. |
| UID/GID | **Vacuous** | All producers and the daemon are the same user. A UID allowlist admits every same-user process. |
| PID → `/proc/<pid>/exe` | **Unsound (defense-in-depth only)** | PID is bus-attested, but a process may `execve` the legitimate producer after connecting (TOCTOU), and PID reuse/`pidfd` handling is racy. An attacker who can run the same binary passes. |
| LinuxSecurityLabel (SELinux/AppArmor) | **Portable? no** | Works only where MAC is present and enforced; not Arch-default, not guaranteed by provisioning. |
| Capability token | **Yes** | The only sound option; see D-4. |

D-Bus **policy XML cannot discriminate by executable**. `<policy>` supports
`user`, `group`, `at_console`, `context`, `send_destination`, `send_interface`,
`send_member`, `own`, and MAC `context`, but on a session bus every process is
the same `user` and there is no "only this binary may call `Emit`" attribute.
Policy can at most deny `own` of the name to *everyone* (which the bus would then
reject for the daemon too). So policy XML is not the answer, and the spine
should not imply it is.

**Finding S-01 (Critical).** AD-38's "caller→topic authorization mapping
(allowed sender identity per topic)" is unenforceable as specified. On a
same-UID session bus there is no stable, unforgeable caller identity to map
from. The requirement as written cannot be implemented; leave it in and the
implementation will either (a) silently equate "identity" with the unique name
(a no-op) or (b) invent a homegrown check that is TOCTOU-vulnerable.

**Finding S-02 (Critical).** Direct signal forgery is not prevented. D-Bus
signals are broadcast; `AddMatch` normally matches on interface/member/path and
need not match on `sender`. Unless every consumer pins
`sender='org.dotfiles.Events'` in its match rule, **any same-user process can
emit a signal on `org.dotfiles.Events1` / `/org/dotfiles/Events` named
`DomainEvent`/`JobStarted`/`JobFinished`**, and the bar (a "thin consumer") will
receive and act on it. Neither the spine nor `event-contract.md:42-44` requires
consumers to authenticate the signal sender. This alone defeats AD-38: the hub
being the sole *name owner* does not stop a third party from emitting a signal
that consumers accept.

**Finding S-03 (High).** `producer` is a display attribute, not authentication,
and the contract does not say so. `DomainEvent` carries `producer: s`
(`event-contract.md:30`, `json:16`) while `Emit` takes only `topic` + `payload`
(`event-contract.md:53-56`). That is the right shape **only if** the hub derives
`producer` from the authenticated caller and never copies it from caller input.
The spine says "producer is hub-validated, never self-asserted" (AD-38) but the
authorization mechanism to do that validation does not exist (S-01). Consumers
must be forbidden from treating `producer` as identity.

---

## 3. Can a same-user untrusted process forge `icme.saved`, `capture.state`, or a job event?

**Yes.**

- Via `Emit`: any same-user process calls
  `org.dotfiles.Events.Emit("icme.saved", {"path": ...})` or
  `Emit("capture.state", {"state": "recording"})`. The hub's authorization, if
  it exists at all, cannot tell the caller from the real ICME/capture
  controller (S-01).
- Via direct signal emission: any same-user process emits
  `DomainEvent(topic="icme.saved", producer="ICME", payload=...)`. Consumers
  accept it unless they match on `sender` (S-02).
- Job events are worse: the introspection XML exposes **no job-lifecycle method**
  (`event-contract.md:48-83`; only `Emit`, `GetActiveJobs`, `GetTopicState`).
  `JobStarted/JobProgress/JobFinished` are declared signals but there is no
  defined, authenticated API by which a job produces them. Either the hub spawns
  jobs itself (then `kind`/`job_id` are hub-internal and the surface is fine but
  undocumented) or there is an omitted method that is equally unauthenticated.
  This is a contract gap and a trust gap.

**Impact if forged:**
- `icme.saved` → if the daemon subscribes to it "to trigger regeneration"
  (epic 5-4:35), a forged event drives reconcile. See §4.
- `capture.state` → the bar indicator is spoofed (UI integrity; recording
  indicator on/off, possibly hiding an active recording).
- job events → progress/exit spoofing, bar animation hijack.

**Finding S-04 (High).** Forged domain events trigger daemon regeneration (via
`icme.saved`) and spoof the bar. No authentication of `Emit`, no sender filter
on consumers, no rate limit.

**Finding S-05 (Medium).** Job lifecycle API is undefined in the contract; the
signal surface cannot be produced through the documented interface, so any
implementation invents an unauthenticated path.

---

## 4. Does AD-30's floor fully bound the blast radius if the daemon is induced to reconcile/prune?

**Partly — for delete volume; no for integrity, availability, or cost.**

What AD-30 actually bounds (`architecture-dotfiles-repo-v3-2026-09-11/ARCHITECTURE-SPINE.md:36-40`):
active + last-N + seed-pinned + undated survive; manual max aggression
`--keep 0 --prune-pinned` still spares active + undated. Good for *cache/history
deletion*.

What it does **not** bound:

1. **Deletion floor is partly attacker-tunable.** `last-N` is a policy value
   that resolves `code default keep=5 < desired-state declaration < CLI flags`.
   `desired.json` lives at `$XDG_CONFIG_HOME/dotfiles/desired.json`
   (spine:81) and is writable by any same-user process. An attacker who writes
   `keep=0` into desired state and then triggers automatic reconcile/prune
   collapses last-N to zero, leaving only active + seed-pinned + undated. The
   "protected floor" for automatic deletion is therefore not a code constant —
   it is intent-controlled. Automatic mode must **clamp** the policy to a
   hardcoded minimum; intent must not be able to weaken the floor.
2. **Regeneration / write amplification / cost.** Triggering reconcile forces
   re-derivation and can invoke the **CSG OCI container** (AD-7/AD-33), rewrite
   `current/`, repoint consumer pointers under the install spine, and reload the
   desktop. Repeated forged events = CPU/IO/container DoS and UI churn. AD-30
   says nothing about this.
3. **Integrity of displayed config.** Reconcile flips consumer pointers
   (`config/ags/colors.css`, `config/gtk-*/colors.css`,
   `config/rofi/colors.rasi`). If the attacker can also influence
   `desired.json`/watched inputs (same user can), the displayed palette /
   wallpaper changes. The daemon is a *confused deputy* for turning
   attacker-writable intent into privileged-ish writes.
4. **Log/audit flooding.** AD-41 logs "every automatic action with its trigger";
   forged events can spam the audit and history (`reactive` trigger).

**Finding S-06 (High).** AD-30 bounds *how much* can be deleted, but the
automatic floor is intent-tunable and it does not bound regeneration cost,
consumer-pointer integrity, or audit flooding. This contradicts the AD-38 claim
"No automatic deletion may be triggered by an untrusted publisher" — the
mechanism to establish "untrusted" does not exist (S-01).

**Finding S-07 (Medium).** No provenance/integrity on `desired.json`. It is
authority for the automatic floor's last-N yet carries no signature/HMAC and no
tightened permissions. Under the same-UID model it is fully attacker-controlled;
this must be acknowledged and the floor clamped (D-6).

---

## 5. Write-behind state file — permissions and race

The convention "a tool's own state file is a write-behind projection … never the
authority; on divergence the event stream wins and doctor repairs" (spine:107,
memlog:50) is correct and the `GetTopicState` hydration path
(`event-contract.md:32-35`) reduces reliance on files. Residual issues:

- **Permissions/ownership unspecified.** No mode is pinned for `state_root`
  (`$XDG_STATE_HOME/dotfiles/`, AD-5) or for any tool state file. Should be
  `0700` directory / `0600` files; otherwise other local users or lax mounts can
  read capture paths / UI state, and group/other-writable files become a
  `doctor`-repair integrity vector and a symlink-attack target.
- **Write race.** No lock across `job ↔ daemon ↔ doctor` writers. AD-31
  serializes only `history.jsonl`. A write-behind file written by the job while
  `doctor` repairs can tear or last-writer-win. Must write atomic
  (`tmp` + `os.replace`) and single-writer, or reuse a lock.
- **Symlink/TOCTOU on tmp creation.** `tmp` + `replace` is only safe with
  `O_NOFOLLOW|O_EXCL` and a trusted parent; not stated.
- **Hub in-memory state race.** The hub is the authority for `GetTopicState`;
  D-Bus method dispatch may be concurrent in the Python client. Two `Emit` calls
  can race the topic-state map, and `GetTopicState` can read a half-applied
  event. Requires single-threaded dispatch or a lock — unstated.

**Finding S-08 (Medium).** State-file permissions unstated; concurrent writers
to the write-behind projection and to hub topic-state are unguarded.

---

## 6. Hub as single point for signals *and* authorization

- **Availability:** acceptable by design (AD-33/AD-19 absence conventions; no
  hub ⇒ no events, consumers show no state). Not a new finding.
- **Authorization concentration risk:** because the hub cannot authenticate
  (S-01), it is a single point where *unauthenticated* requests become trusted
  broadcasts. One hub bug (or its absence) is total.
- **Name hijack / shadow hub:** any same-user process can `RequestName` first
  or queue-ahead. `dbus-daemon` has no "only this unit may own" rule on a
  session bus. AD-38 says "never a shadow hub" but pins no mechanism. Mitigate:
  daemon calls `RequestName(..., DO_NOT_QUEUE)` and treats failure as fatal
  (alert, do not run half-alive); consumers resolve `GetNameOwner` and pin the
  unique name, updating on `NameOwnerChanged`; consumers add
  `sender='org.dotfiles.Events'` to `AddMatch`.
- **No rate limiting / quota:** `Emit` is unbounded in frequency and payload; a
  rogue process can exhaust hub memory via unbounded topic/state retention or
  starve the loop.

**Finding S-09 (High).** Hub name ownership is first-come; no anti-hijack
mechanism is specified, so a same-user process can become (or shadow) the hub.

**Finding S-10 (Medium).** No rate limiting or resource bounds on `Emit` /
`GetTopicState` / retained topic state.

---

## 7. Privilege of the systemd `--user` unit

The unit is a user unit (AD-33:40), so no root escalation is implied, but the
unit is not hardened and its privileges are undeferred:

- No `NoNewPrivileges`, `ProtectSystem`, `ProtectHome`, `PrivateTmp`,
  `RestrictAddressFamilies`, `MemoryMax`, `TasksMax`, `RestartSec` backoff,
  `CapabilityBoundingSet`, `SystemCallFilter` are pinned.
- The daemon runs the **CSG OCI container** (podman/docker) and external
  subprocesses, so it needs a broad environment; the one place it is least
  sandboxed is exactly where attacker-influenced intent is processed.
- `ExecStart` = `dotfiles-runtime daemon run` must be an absolute trusted path;
  `EnvironmentFile`/env import (session target) must not import untrusted vars.
- `desired.json` at `$XDG_CONFIG_HOME` must be read-only for the unit; writes
  only under `$XDG_STATE_HOME/dotfiles`.

**Finding S-11 (Medium).** Unit privilege/hardening is unspecified, and the
daemon is the highest-value target (holds regeneration/deletion authority and
spawns the OCI runtime).

---

## 8. Payloads `a{sv}` — deserialization, type confusion, size

D-Bus variant `a{sv}` is wire-type-safe (no pickle-style RCE), so this is not a
deserialization-RCE finding. It is a **memory / type-confusion / validation**
finding:

- **No runtime schema validation.** The contract says `event-contract.json`
  "carries names **and payload schemas** and is the test-time source of truth"
  (`event-contract.md:96-102`) — but "test-time source of truth" means the drift
  test checks *constants*, **not incoming messages**. Nothing validates a live
  `Emit` payload against the topic schema. `a{sv}` will happily carry unknown
  keys, wrong variant types, or nested variants. AD-38's "rejects a
  non-conforming Emit" has no named validator.
- **Unbounded size.** dbus-daemon's default max message is large (up to
  128 MiB). The hub can be asked to store/return payloads of that size; retained
  topic state has no cap → memory exhaustion. `GetTopicState` is an
  amplification path to every consumer.
- **Unbounded nesting.** A variant may contain another `a{sv}`/array; a hostile
  caller can force deep recursion in the deserializer/serializer.
- **Type confusion at the JSON boundary.** The rule "JSON-compatible
  scalars/containers (`s`,`d`,`i`,`b`,`a{sv}`); no opaque binary"
  (`event-contract.md:110-111`) is a convention; `a{sv}` can still carry `ay`,
  `ao`, `v`, etc. Enum values (`capture.state` ∈ {idle,recording,paused}) and
  numeric ranges (`fraction` ∈ [0,1]) are declared in JSON but not enforced at
  ingest.
- **`producer` self-assertion.** See S-03.

**Finding S-12 (High).** No runtime payload validation, size bound, depth
bound, or topic-state cap. `event-contract.json` is enforced only at test time,
so the hub's "rejects non-conforming Emit" is aspirational.

**Finding S-13 (Medium).** Enum/range validation declared but not enforced at
ingest (`capture.state`, `JobProgress.fraction`).

---

## 9. Blast-radius summary (honest framing)

The daemon runs as the same user as every other process, so a malicious
same-user process can already read/write the same files directly; AD-38 is not
an OS privilege boundary. Its real value is **confused-deputy resistance** —
stopping a process that does *not* have direct filesystem access (a sandboxed
or lower-privilege publisher) from driving the daemon's delete/regenerate
authority. That case is exactly the one the current design fails to secure:
no capability token, no executable identity, no signal-sender filter. The
remaining same-UID "attacker" framing is defense-in-depth, but the spec should
say so rather than claim a trust boundary it cannot enforce.

---

## Findings (tiered)

| ID | Tier | Finding |
| --- | --- | --- |
| S-01 | **Critical** | AD-38 caller→topic authorization is unenforceable on a session bus; no stable caller identity exists (unique name rotates, UID vacuous, PID/exe unsound). Requirement as written cannot be implemented. |
| S-02 | **Critical** | Consumer signal forgery: any same-user process can emit `DomainEvent`/`Job*` on the hub's interface/path; consumers don't pin `sender`. Defeats the single-owner claim. |
| S-04 | **High** | Forged `icme.saved`/`capture.state`/job events are accepted (via `Emit` or direct signal) to drive regeneration and spoof the bar; no authentication/rate limit. |
| S-12 | **High** | No runtime payload validation / size bound / depth bound / topic-state cap; `event-contract.json` is test-time only. `a{sv}` memory / type-confusion / DoS. |
| S-09 | **High** | Hub name ownership is first-come; no anti-hijack mechanism; AD-38 "never a shadow hub" is unbacked. |
| S-06 | **High** | AD-30 bounds delete volume only; automatic floor's last-N is intent-tunable via `desired.json`; regeneration cost, consumer-pointer integrity, and audit flooding are unbounded. |
| S-00 | **High** | No threat model anywhere; authorization claim is untestable. |
| S-03 | **High** | `producer` unauthenticated in effect; contract does not forbid treating it as identity. |
| S-05 | **Medium** | Job-lifecycle API undefined; only `Emit` exists, so job signals have no documented authenticated producer. |
| S-07 | **Medium** | No integrity/permissions on `desired.json`; floor authority is attacker-writable. |
| S-08 | **Medium** | State-file permissions unstated; concurrent write-behind + hub topic-state races unguarded. |
| S-10 | **Medium** | No rate limiting / resource bounds on the hub; memory exhaustion via retained state. |
| S-11 | **Medium** | systemd unit privilege/hardening unspecified; daemon is the highest-value target and spawns OCI runtime. |
| S-13 | **Low/Medium** | Enum (`capture.state`) and range (`fraction`) declared but not enforced at ingest. |
| S-14 | **Low** | No explicit note that `GetTopicState`/`GetActiveJobs` are unauthenticated readers; state may be sensitive (capture paths). |

---

## Concrete minimal decisions (to fold into AD-38 + contract)

These are the cheapest sound set; none requires a new process or store.

- **D-1 (Sender filtering, mandatory).** Consumers MUST `AddMatch` with
  `sender='org.dotfiles.Events'` (interface + path + member), and MUST resolve
  the owner's unique name via `GetNameOwner` and re-resolve on
  `NameOwnerChanged`. Treat any signal not from the current owner's unique name
  as hostile. This is the minimum to make S-02 false.

- **D-2 (State the real trust model).** Add an explicit threat-model section:
  session bus is same-UID; the OS user boundary is the primary boundary; the hub
  guards against confused-deputy use by *sandboxed/lower-privilege* publishers
  and against accidental producers, not against a fully compromised same-user
  process. Describe what the daemon is authorized to do and why each action is
  safe under that model (S-00).

- **D-3 (Hub-validated identity via D-Bus credentials — defense-in-depth).** In
  `Emit`, the hub calls `org.freedesktop.DBus.GetConnectionCredentials` and
  requires `UnixUserID == daemon UID`; optionally compare `ProcessID`'s
  `/proc/<pid>/exe` against a declared producer allowlist using `pidfd` +
  exe inode + start-time, and re-check per call. Label this defense-in-depth,
  not authorization (S-01). Do **not** build the design on it.

- **D-4 (Capability token — the actual authorization).** At session start the
  hub (or the systemd unit) mints a random 256-bit token per producer role
  (`capture`, `icme`, `speedtest`, …), delivered via a `0600` file under
  `$XDG_RUNTIME_DIR` (or the unit `Environment=`, or a portal/socket for
  sandboxed producers). `Emit` gains an explicit `token` argument; the hub
  verifies it constant-time and maps token→allowed topics. Hub sets `producer`
  from the token subject. This is what makes "caller→topic authorization"
  real. Per-role tokens so `capture` cannot emit `icme.saved`.

- **D-5 (Runtime payload validator, not just drift tests).** Validate every
  `Emit` and `GetTopicState` payload against `event-contract.json` at ingest:
  known topic, known keys only, exact variant types, enum membership
  (`capture.state` ∈ {idle,recording,paused}), numeric ranges
  (`fraction` ∈ [0,1]), reject `a{sv}` nesting depth > 4 and unknown variant
  signatures; cap total payload at a small bound (e.g. 64 KiB) and cap retained
  topic-state (LRU, max N topics, total bytes). Add the validator spec to the
  contract (S-12, S-13).

- **D-6 (Clamp the automatic floor; intent is not authority).**
  Automatic reconcile/prune MUST clamp `keep` to a hardcoded minimum
  (code constant) regardless of `desired.json`; intent may only *raise*
  retention, never lower it. Bind `desired.json` to `0700` dir / `0600` file and
  read it read-only. Explicitly state that under the same-UID model
  `desired.json` is not a trust boundary, and that the AD-38 claim "no automatic
  deletion from an untrusted publisher" depends on D-4 (S-06, S-07).

- **D-7 (Name-ownership discipline).** Daemon `RequestName` with
  `DO_NOT_QUEUE`; on `EXISTS`/`IN_QUEUE` treat as fatal and surface it (no
  half-alive hub). Provision the unit early in `graphical-session.target`.
  Document that a same-user pre-emptive owner cannot be prevented by
  `dbus-daemon` policy, only detected (S-09).

- **D-8 (Unit hardening, pinned in provisioning).** `NoNewPrivileges=yes`,
  `ProtectSystem=strict`, `ProtectHome=read-only` (or specific
  `ReadWritePaths=$XDG_STATE_HOME/dotfiles`), `PrivateTmp=yes`,
  `CapabilityBoundingSet=`, `AmbientCapabilities=`, `MemoryMax=`/`TasksMax=`,
  `RestartSec` backoff, absolute trusted `ExecStart`. Account for the OCI
  runtime's needs with the narrowest grants that work (S-11).

- **D-9 (State-file hygiene).** Pin `state_root` `0700`, state files `0600`,
  atomic write via `tmp` created `O_CREAT|O_EXCL|O_NOFOLLOW` in a trusted parent
  then `os.replace`; single writer or a lock shared with `doctor`; hub
  topic-state updates serialized (single-threaded dispatch or a lock) (S-08).

- **D-10 (Hub quota + rate limit).** Bound `Emit` rate per sender and globally;
  bound retained state; on overflow, drop + log (never grow unbounded) (S-10).

- **D-11 (Contract clarity).** Either define the job-lifecycle API (an
  authenticated `RegisterJob`/`ReportJob` via the hub, per D-4) or state that
  the hub itself is the sole lifecycle producer and jobs never emit `Job*`.
  Forbid consumers from treating `DomainEvent.producer` as identity (S-03, S-05).

---

## Options for the spine (do not edit here)

- **Minimum viable:** D-1 + D-5 + D-6 + D-11. This closes forged-signal
  injection, runtime payload abuse, floor collapse, and the contract gap; it
  leaves `Emit` callers unauthenticated but bounded to domain topics that cannot
  cause deletion. Acceptable only if automatic deletion is gated on a
  hub-internal trigger (file-watch), never on a bus event.
- **Recommended:** the above + D-4 (capability token) + D-8/D-9/D-10. This
  makes "caller→topic authorization" a real, testable statement and secures the
  confused-deputy case.
- **Reject:** keeping AD-38 as-is and implementing a homegrown PID/exe check as
  "authorization." It is unsound (S-01) and will read as compliance theater.

---

## Residual risk explicitly accepted (if any)

- Same-UID processes can read the token from `$XDG_RUNTIME_DIR` if they have
  filesystem access; D-4 protects only against publishers that lack that access
  (sandboxed apps). State this plainly.
- A same-user process can still DoS by consuming CPU/disk directly; the hub can
  only bound its own surface.
- `dbus-daemon` policy cannot authorize by executable on the session bus; MAC
  (SELinux/AppArmor) is not assumed.

---

## Open questions

1. Are ICME / capture controller / speed-test jobs ever sandboxed (Flatpak,
   `bwrap`)? If never, D-4's value drops and the whole AD-38 framing should be
   reworded to "producer hygiene," not authorization.
2. Is the daemon ever intended to hold privileges a normal user process does
   not (e.g., a different user, polkit, capabilities)? If not, say so.
3. Who is the adversary the gate believes AD-38 defends against? (This is the
   S-00 question; the answer determines whether the fixes above are all needed.)
