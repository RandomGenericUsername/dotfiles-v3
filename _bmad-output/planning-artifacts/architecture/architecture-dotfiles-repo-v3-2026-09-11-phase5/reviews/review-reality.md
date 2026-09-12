# Reality-Check Review — Phase 5 Reactive Runtime Spine

**Reviewer:** Reality-check reviewer (VALIDATE gate; no spine edits)
**Date:** 2026-09-11
**Scope:** `ARCHITECTURE-SPINE.md` (AD-33..AD-42 + AD-12 delta), `.memlog.md`,
`contracts/event-contract.md|json` (repo-root `contracts/`, not the spine dir).
**Mandate:** verify every committed decision is *reality-checked / web-verified*
rather than asserted: D-Bus codegen availability; session-bus semantics
(single-owner well-known names, proxy signal delivery, caller identity/authorization);
systemd `--user` on Wayland/uwsm (env availability, `Restart` semantics,
user-unit provisioning without a live session); inotify behavior (non-recursive,
atomic-replace via rename, `IN_Q_OVERFLOW`, watch limits); Python sync D-Bus
libraries; GJS/Gio `DBusProxy` signal binding + name-owner tracking; and the
absence/recovery claim attributed to AD-19. Repo truth checked where cheap
(uwsm in `arch.yml`; watched roots as deployed; `desired.json`; trigger enums).
**Method:** read spine + memlog + contract; inspected
`src/runtime/src/runtime/adapters/{derive,hashing,desired_state_reader,env}.py`,
`application/{reconcile,inspect}.py`, `cli/main.py`,
`src/gui-tools/capture-tool/bin/capture-tool`,
`dotfiles/config/ags/bar/widgets/{recording,network}.tsx`,
`src/provisioning/ansible/group_vars/arch.yml`, the parent Phase-2 spine, the
`shared-data-contract.md`, and the deployed install spine `~/.local/share/dotfiles`;
web-verified systemd.service(5), systemd `Type=dbus`/`BusName`, uwsm(1),
inotify(7), the D-Bus bus API, `GDBusProxy` docs, GJS GVariant guide, and codegen
tooling. Local presence of `gdbus-codegen` checked (`absent`).

---

## Verdict

**PASS WITH FINDINGS — 1 CRITICAL, 4 HIGH, 5 MEDIUM, 4 LOW.**

The spine's *technology* claims are largely reality-checked and correct: the
codegen rationale was explicitly self-corrected in the memlog; session-bus
single-owner semantics, `GDBusProxy` `g-signal`/`g-name-owner`, inotify
non-recursion + `IN_Q_OVERFLOW` + watch limits, and the existence of the four
derivation inputs are all confirmed. But several *decisions built on those
facts* are asserted rather than validated, and three are contradicted by the
actual repo: (1) `Restart=on-failure` + `Type=simple` does **not** provide the
supervision AD-33 claims; (2) the icon-templates directory root is nested, so
the non-recursive watch strategy loses events; (3) AD-19 is misattributed as
the source of absence/recovery (it says the opposite). The most important
correction is to stop treating the absent/recovery requirement and the watch
set as "inherited/verified" when they are new, unvalidated Phase-5 content.

Anchoring note: the companion contract already received a contract-robustness
review (`review-contract.md` H3/H4/H6) and a trust review (`review-trust.md`).
Where this review independently reaches the same gap it is marked
`[overlaps review-contract/trust]`; the findings below are the reality-check
evidence and repo/web verification, not a re-litigation.

---

## 1. Checked items — confirmed real (web- or repo-verified)

### 1.1 D-Bus codegen availability — memlog correction is accurate
- The spine punts to "No codegen" (spine:108) and the memlog *corrects itself*
  (memlog:44): "the absolute claim 'no D-Bus codegen exists for Python' is
  false (python-sdbus ships a generator; …)". Verified: `python-sdbus`'s PyPI
  page lists "Jinja2 for code generator"; a third-party `gen-dbus` exists on
  PyPI; `gdbus-codegen` is C/DocBook/reStructuredText only (man page) and is
  **absent on this machine** (`which gdbus-codegen` → not found). The
  corrected rationale — "a generator would couple the contract to an unchosen
  client library; for four signals, hand-written constants + one drift test is
  cheaper to own" — is sound. **PASS.** (The specific package name
  `dbus-python-client-gen` in memlog:44 was not independently confirmed and is
  immaterial to the decision.)

### 1.2 Session D-Bus semantics
- **Well-known name single owner (AD-38).** Confirmed by the D-Bus name API:
  registrations are arbitrated; `GetNameOwner` returns the current owner;
  extra requests are queued/rejected unless `ALLOW_REPLACEMENT`/
  `REPLACE_EXISTING` are used. So "exactly one process owns `org.dotfiles.Events`"
  is enforceable by the bus — **with the caveat in C1** that the daemon must
  assert ownership explicitly or the unit can report running without owning it.
- **Signal delivery via `GDBusProxy` (AD-34/AD-38).** Confirmed: `g-signal` is
  emitted "when a signal from the remote object and interface that proxy is for,
  has been received" (Gio docs); `g-name-owner` is "the unique name that owns
  `g-name` or NULL"; `notify::g-name-owner` tracks owner changes. Proxy
  construction subscribes match rules unless `DO_NOT_CONNECT_SIGNALS`, so the
  bar can bind the hub and tolerate its absence. **PASS**, with the `a{sv}`
  unpack caveat (M3).
- **Caller identity/authorization mechanisms exist (AD-38).** Confirmed:
  `org.freedesktop.DBus.GetConnectionCredentials(bus_name)` and
  `GetConnectionUnixProcessID(bus_name)` are available to a session-bus service,
  keyed on the caller's unique name. The *mechanism* exists; the *identity
  basis* is not defined (H4).

### 1.3 systemd `--user` on Wayland/uwsm
- **uwsm is installed as intended.** `group_vars/arch.yml:16` → `uwsm: uwsm`
  ("wraps the Hyprland session in a systemd user unit"). Confirmed uwsm's job:
  it launches the compositor via `wayland-session@.target` (bound to
  `graphical-session.target`) and its env preloader exports the session delta
  (incl. `WAYLAND_DISPLAY`, and it checks `DBUS_SESSION_BUS_ADDRESS`) to the
  systemd and D-Bus activation environments. So session-bus env *can* be
  available to a `graphical-session.target`-hooked user unit. **PASS for env**,
  but the spine defers the target/env binding (M4b).
- **User-unit provisioning without a live session.** Confirmed no role writes
  `~/.config/systemd/user/` (none exists on this machine; only system-level
  `display_manager`/`packages` roles touch systemd). `systemctl --user enable`
  needs a running user manager; the alternative (symlink into
  `<target>.wants/`) is valid per systemctl(1)/systemd.unit(5). **Deferred and
  honestly flagged** (spine:174). PASS-as-deferred.

### 1.4 inotify
- Non-recursive ("to monitor subdirectories …, additional watches must be
  created"), `IN_Q_OVERFLOW` (events dropped, overflow always generated, rescan
  required), and the `/proc/sys/fs/inotify/{max_queued_events,max_user_instances,max_user_watches}`
  limits are exactly as the spine states. Watching the **immediate parent**
  filtered to a filename is the correct atomic-replace-safe approach (watching
  the file itself breaks on inode replacement). **PASS for the stated
  mechanism** — but the directory-root case is wrong (H1).

### 1.5 Python sync D-Bus libraries
- Real and plural: `dbus-python` (main-loop-agnostic, sync), `pydbus`/`dasbus`
  (GLib), `python-sdbus` (blocking + asyncio), `dbus-next`/`dbus-fast`
  (asyncio-first). The deferred constraint "prefer a GLib/sync client over an
  asyncio-first one" is reasonable and satisfied by the ecosystem. **PASS-as-deferred.**

### 1.6 Repo grounding claims
- `recording.tsx:40` really does poll `capture-tool status` every 500 ms via
  `GLib.timeout_add`; `capture-tool` is a short-lived Python CLI that spawns the
  recorder and exits; `network.tsx` really uses Astal `createBinding`/`notify::`
  (event-driven). The memlog's anti-pattern/pass-pattern grounding (memlog:29)
  is **accurate**.
- The four AD-39 derivation inputs exist in the deployed spine
  (`~/.local/share/dotfiles/`): `icon-templates/`, `icon-mappings/icons.yaml`,
  `config/color-scheme-generator/templates/`, `config/weg/effects.yaml`. **PASS.**
- `state_root` = `$XDG_STATE_HOME/dotfiles` (`cli/main.py:77-85`); no
  `desired.json` exists there and none exists at
  `$XDG_CONFIG_HOME/dotfiles/` (see M2).

---

## 2. Findings (tiered)

### C1 — CRITICAL — AD-33's supervision cannot prevent the failure it exists to prevent

**Where:** spine:40 (`Type=simple`, `Restart=on-failure`), memlog:21/24,
inherited table spine:32, epics risk line.

**Reality:** `Restart=on-failure` restarts only on non-zero exit / unclean
signal / timeout / watchdog — **not on a clean exit (status 0)**. A daemon that
loses the session bus, or otherwise performs an orderly shutdown, exits 0 and
is **not** restarted. Worse, service restart is subject to
`StartLimitIntervalSec`/`StartLimitBurst` (default 5 starts / 10 s); after
enough failures systemd stops retrying and the unit lands in `failed` — a
*silently dead watcher*, which is the exact thing AD-33 says it "prevents."
Separately, `Type=simple` marks the unit started the instant `ExecStart` forks,
*before* `org.dotfiles.Events` is acquired. If the name is squatted or
`RequestName` fails, systemd still reports `active (running)` while the hub
does not exist, and consumers see "no state" with no signal that the daemon is
broken. Neither the memlog nor the spine specifies `RequestName` flags or a
non-zero exit on acquisition failure.

**Concrete fix:** (a) adopt `Type=dbus` + `BusName=org.dotfiles.Events` so
unit state tracks name ownership (systemd will not consider it started until
the name is acquired, and will terminate it when the name is released). Verify
on the target: `Type=dbus` is documented for the *user bus* in a user instance
(systemd/systemd#892 flags the session-bus asymmetry), and on uwsm/session-
bus systems `DBUS_SESSION_BUS_ADDRESS` commonly resolves to the same user bus —
if `Type=dbus` does not track the session bus in testing, fall back to (b).
(b) Keep `Type=simple` but use `Restart=always` (not `on-failure`),
`RestartSec=` (e.g. 2s), and `StartLimitIntervalSec=0` (or an explicitly tuned
window), and have the daemon `RequestName(..., DO_NOT_QUEUE)` and exit non-zero
if it does not become primary owner — so the failure is visible and recoverable
rather than a 0-exit stop. (c) Add `After=graphical-session.target` and
`WantedBy=graphical-session.target`; do **not** add `PartOf=`/`BindsTo=` to the
compositor unit (that would re-introduce the Hyprland-reload death AD-33 is
trying to avoid). This is an AD-33 rewrite, not an implementation detail.

---

### H1 — HIGH — The non-recursive watch strategy loses changes in the nested `icon-templates` root

**Where:** spine:81 (AD-39 "a directory root is watched directly … never a
recursive/ancestor watch") and spine:87 (AD-40 "inotify is not recursive, so
each root directory is watched explicitly").

**Reality:** `find_icon_templates` returns a **directory tree**, not a flat
directory: the deployed root contains e.g.
`icon-templates/status-bar/thunderbird/default/icon.svg` and
`icon-templates/wlogout/shutdown/…` (2–3 levels deep; repo mirror
`dotfiles/assets/icon-templates/…` is the same). `canonical_hash_dir`
(`hashing.py:113`) hashes **recursively** (`rglob`). A single non-recursive
watch on `icon-templates/` yields events only for direct children of that root;
modifying `status-bar/<tool>/<variant>/*.svg` generates an event on the deep
directory's watch (if any), never on the root watch. "Each root directory is
watched explicitly" is therefore false in effect, and the AD-36 hash backstop
never runs because **no event fires**. This is a correctness hole for the
stated trigger (provisioning updates / template edits must converge).

**Concrete fix:** for a directory root, at daemon start recursively enumerate
subdirectories and add one watch per directory (and add/remove watches on
`IN_CREATE`/`IN_DELETE|IN_MOVED_FROM` of directories), or declare only truly
flat directories as directory roots. Add an acceptance test that mutates a
depth-2 file under `icon-templates/` and asserts one reconcile; and a startup
log of the exact watch list. Update AD-39/AD-40 to say "directory roots are
watched recursively by explicit per-directory watches" (the *ban* should be on
ancestor/parent-dir watches, not on watching subdirectories of the root).

---

### H2 — HIGH — AD-19 is misattributed as the source of "presence, absence, and recovery"

**Where:** spine:32 (`AD-19 operational envelope | Phase 2 spine | Daemon/watcher
presence, absence, and recovery behavior`), memlog:50 ("Inherited AD-19
operational envelope binds (absence/recovery when systemd/bus/inotify
missing)"), epics risk line ("Env absence … → AD-19 operational envelope +
absence conventions").

**Reality:** the actual Phase-2 AD-19
(`architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md:144-148`) is
about install/update operations: CLI is Typer, installed by provisioning's
`cli_tools` role, PATH + container engine, "Operations are CLI commands …,
synchronous, **no daemon in Phase 2** … Phase 5 introduces the daemon + watchers
+ concurrency." It contains **no** absence/recovery rule for daemon, watcher,
bus, inotify, or systemd; it explicitly defers all of that to Phase 5. The
absence/recovery requirement in this spine is *new* content (AD-38's "if the
daemon is absent they publish nothing"; the Consistency row "Absence &
recovery"; AD-33's optionality). Citing AD-19 as an inherited binding is a
factual mismatch that hides the fact that no one has designed absence/recovery
yet.

**Concrete fix:** remove AD-19 from the "inherited" row and state explicitly
that presence/absence/recovery is a **new Phase-5 invariant** (give it its own
AD or fold it into AD-33/AD-38). Then actually design it: enumerate each
participant's behavior when the bus/daemon/inotify/systemd user manager is
missing, and test it. Correct `memlog:50` and the epics risk line. (This matters
because the *only* place "absence is a no-op" is enforced today is a convention
row with no owner; see M1.)

---

### H3 — HIGH — AD-42's "no trigger absent from the contract" is already false; the shared-data-contract is not the source of truth

**Where:** spine:99 (AD-42) and spine:109 ("No unit may introduce or accept a
history trigger value absent from the contract").

**Reality:** `shared-data-contract.md:45` pins
`"trigger": "seed|set|reconcile|force"`. The runtime already enforces **six**
values — `_VALID_TRIGGERS = {"seed","set","reconcile","force","regenerate","doctor"}`
(`reconcile.py:68`) — and `inspect.py:493` hard-codes the same six in a
separate string, with `seeder.py:816` a third copy in a docstring. So the
invariant AD-42 relies on is *already violated by shipped code*, and there are
three independent hard-coded enums plus a contract that must be updated in
lockstep by `reactive`. There is no drift test today.

**Concrete fix:** before adding `reactive`, establish the single source of
truth AD-42 assumes: either (a) update `shared-data-contract.md` to the full
six-value enum now and add one drift test that asserts
`reconcile._VALID_TRIGGERS`, the `inspect.py` list, and `seeder.py`'s docstring
all equal the contract (hand-written constants + drift test, rung-2 style), or
(b) generate all four from one file. AD-42 must name **both** code sites
(`reconcile.py` enforcement and `inspect.py` validation), not just "the shared
data contract + the inspect validator". As written, a story can ship `reactive`
in `reconcile.py`/`inspect.py` while the contract still says four values and no
test fails.

---

### H4 — HIGH — AD-38's "caller→topic authorization" has no stable identity basis on a session bus

**Where:** spine:75 ("pins a caller→topic authorization mapping (allowed sender
identity per topic)"), contract md:42-44, contract json has no identity map.
`[overlaps review-contract H6 / review-trust §2]`

**Reality:** the *mechanism* to see a caller exists
(`GetConnectionCredentials`/`GetConnectionUnixProcessID`), but "sender
identity" as written is unusable: D-Bus **unique names are per-connection and
never reused**, so they cannot be pinned in advance; PIDs change across
restarts; and every process on a user session bus shares the same UID, so
`GetConnectionUnixUser` distinguishes nothing. A same-UID process can call
`Emit` claiming any topic unless the hub checks something stable about the
caller. The memlog's NEW-1 tightening ("the hub pins a caller-to-topic
authorization mapping") is therefore an assertion, not a designed control.

**Concrete fix:** define the identity basis explicitly and state the threat
model. Viable options, in order: (a) the hub **spawns the resident jobs** and
authorizes by the child's `GetConnectionCredentials` → `ProcessID` matched
against the hub's own child table (robust against name churn, easy to
invalidate on exit); (b) authorize by executable path derived from the peer's
PID under `/proc/<pid>/exe` (same-UID only, document that it is not a security
boundary against a hostile same-user process); (c) hub-issued per-job cookie
passed to the child and echoed on `Emit` (bind to the unique-name/PID tuple at
issue time). Whichever is chosen must be encoded in the contract (the JSON
currently carries no authorization map) and tested with a deliberate
non-conforming `Emit`. Without this, "producer is hub-validated, never
self-asserted" is empty.

---

### M1 — MEDIUM — Absence/recovery is a convention row with no mechanism; hub state is memory-only

**Where:** spine:111 ("Absence & recovery … no participant crash-loops"),
contract md:32-35 (`GetTopicState`/`GetActiveJobs` hydration), AD-36 backstop
"held in memory" (spine:58).

**Reality:** with the C1 supervision fixed, systemd bounds daemon restarts; but
the hub's domain state is in-memory, and resident jobs (capture controller,
speed test) are the source of truth for liveness. A hub restart mid-recording
loses `GetTopicState("capture.state")`; the bar shows nothing although a
recorder runs, and nothing re-announces because the contract gives jobs no
reconnect/`NameOwnerChanged` re-announce path (the contract review already
flags hydration races/replay). AD-19 does not cover this (H2).

**Concrete fix:** specify a recovery path in the contract: on hub name
acquisition, query/receive every live job's registration; have resident jobs
watch `org.freedesktop.DBus` `NameOwnerChanged` for the hub and re-emit their
current domain state when it reappears. For the hub's own restart, either
persist a minimal topic projection under `state_root` (already permitted:
"if the AD-36 backstop is ever persisted, it lives under `state_root`") or
reconstruct from running children at startup. Add tests for "hub restarted
mid-job" and "bar connects after events fired".

---

### M2 — MEDIUM — "Enumerated allowlist" is actually dynamic `find_*` resolution; shape can be a directory

**Where:** spine:81 (AD-39 "explicit enumerated allowlist"),
`derive.py:64/94/129/178`.

**Reality:** the watched set is not enumerated in the spine or the daemon; it
is whatever `derive.find_*` returns at runtime, and those functions check the
**install spine first, then walk repo ancestors** for a dev checkout
(`derive.py:73-90` etc.). So the actual watch targets differ between a deployed
machine (`~/.local/share/dotfiles/...`) and a dev checkout
(`src/cli-tools/...`), and can silently change when the install spine appears
or disappears. Additionally `find_icon_mappings` can return a **directory**
(`install_spine/icon-mappings`, `derive.py:200-205`) rather than the
`icons.yaml` file, which breaks AD-39's "file root watched via its immediate
parent filtered to the exact filename."

**Concrete fix:** resolve the roots once at daemon start, freeze and log the
concrete list, and assert at startup that none is an ancestor of `state_root`
or of any runtime output (AD-36 disjointness). Handle both file- and
directory-shaped icon-mappings (normalize: if the resolver returns a dir,
resolve to the specific YAML file or treat it as a directory root with the H1
recursion rule). Consider explicitly excluding repo-ancestor candidates at
runtime (dev mode opt-in) so the watch set is genuinely an allowlist.

---

### M3 — MEDIUM — `a{sv}` payloads need GJS `recursiveUnpack()`, not `deepUnpack()`; the contract doesn't say so

**Where:** contract md:30/79 (`payload: a{sv}`), json:16/26.

**Reality:** GJS's `deepUnpack()` "will unpack a variant and its children, but
**only up to one level**" (GNOME JS guide); only `recursiveUnpack()` (GJS ≥
1.64) unpacks all descendants. For `a{sv}`, the inner `v` values remain
`GLib.Variant` under `deepUnpack()`, so a naive bar consumer reads Variant
objects instead of strings/doubles. Also `recursiveUnpack()` loses type info
(all numbers become `Number`), which matters for `speedtest.finished` doubles
and `JobProgress.fraction`.

**Concrete fix:** document the exact GJS unpack rule in `event-contract.md`
("bar consumers use `recursiveUnpack()` for `a{sv}` payloads") and add a
bar-side test that decodes a `capture.state` and a `speedtest.finished` payload
end to end. Optionally prefer flat, typed signals over `a{sv}` for the two
hot payloads to avoid the Variant ambiguity entirely.

---

### M4 — MEDIUM — Two session/systemd reality gaps the spine defers rather than binds

(a) **`desired.json` relocation has no writer and the reader still points at
`state_root`.** AD-39 pins the intent document at
`$XDG_CONFIG_HOME/dotfiles/desired.json` and AD-36 says "intent moves out of
[state_root]," but `desired_state_reader.py:31/42/48` reads
`state_root/desired.json`, and a repo-wide search finds **no writer** for
`desired.json` at all (only the reader + tests; the `apply_wallpaper` docstring
claims it "updates desired state" but no adapter writes it). No
`~/.config/dotfiles/` exists. So the watched intent root is inert and the
"relocation" is asserted, not planned as a concrete change. **Fix:** make the
writer + path change an explicit Phase-5 task with a migration for an existing
`state_root/desired.json`, and don't list the intent root as a live trigger
until the writer exists (otherwise AD-36's backstop will never see intent
changes).

(b) **systemd unit env/target binding is a deferred question, not a decision.**
The unit must be hooked to `graphical-session.target` and rely on uwsm's env
preloader for `DBUS_SESSION_BUS_ADDRESS`; a unit started at login before uwsm
finalizes (or under `default.target`) can come up without the session-bus
address and die at C1's first failure. **Fix:** bind `After=graphical-session.target`
+ `WantedBy=graphical-session.target` in AD-33 (not merely "decide later"),
and add a startup precondition that fails loudly (non-zero) when
`DBUS_SESSION_BUS_ADDRESS` is absent rather than exiting 0.

---

### M5 — MEDIUM — `capture.state` payload cannot reconstruct the elapsed timer the convention mandates

**Where:** contract md:93 (`capture.state` = `{ "state": s }`), contract json:23-27
(enum `idle|recording|paused`), spine:106 ("continuous display … derives from a
monotonic clock plus one recorded start"). `[overlaps review-contract H3]`

**Reality:** the convention requires an *elapsed* timer for the recording
indicator (the current `recording.tsx` renders one), but the contract's
`capture.state` domain event carries only `state`, and `GetTopicState("capture.state")`
is pinned to the same `{state}` schema. There is no `started_at`/monotonic
start anywhere in the contract, so a bar that stops polling cannot compute
elapsed. The payload is also missing the `error` state the tool actually emits
(`capture-tool` returns `{"state": "error", ...}`; `recording.tsx` flattens it
to idle), so failures are unrepresentable.

**Fix:** extend the `capture.state` schema (and enum) to carry the recorded
start (e.g. `{ "state": s, "started_monotonic_ms": x }`) or a dedicated
`capture.started` topic with the start, and add `error` (with a reason) to the
enum. Keep elapsed rendering as a timer over that one recorded start, per the
convention.

---

### L1 — LOW — The codegen reality-check exists only in the memlog

The corrected rationale lives at `memlog:44`; the spine keeps the bald "No
codegen" (spine:108) with no citation. **Fix:** add one line to AD-34's
consistency row noting the decision is "hand-written constants + drift test
*despite* third-party generators existing, because a generator couples the
contract to an unchosen client library."

### L2 — LOW — Companion path in the spine's frontmatter is ambiguous

The spine's `companions` / `contracts/event-contract.*` resolve next to the
spine dir (which has no `contracts/`), but the files live at the **repo-root**
`contracts/` (confirmed). **Fix:** anchor the reference (`../../../contracts/…`)
or state "repo-root `contracts/`".

### L3 — LOW — Spine omits the hydration methods the contract exposes

`event-contract.md/json` define `GetActiveJobs` and `GetTopicState`, but
AD-34/AD-38 (spine:46/75) never mention them; the hub's read surface is only in
the memlog (NEW-2). **Fix:** reference them in AD-34 so the spine and the
contract cannot drift.

### L4 — LOW — `Type=simple` + `Restart=on-failure` is also what AD-33's own stated purpose ("no crash-loop") leans on

Even with C1 fixed, "no participant crash-loops" (spine:111) is only true
because systemd's start rate limit eventually gives up — i.e. by *failing*, not
by scheduling. State the intended bound (`StartLimitBurst`/`IntervalSec`, or
`RestartSec` backoff) explicitly, and state the equivalent bound for the
non-systemd jobs/tools (which have none today).

---

## 3. Findings summary

| ID | Tier | Claim | Reality | Fix |
| --- | --- | --- | --- | --- |
| C1 | CRITICAL | AD-33 `Type=simple`+`Restart=on-failure` prevents a silently dead watcher | Clean exit not restarted; StartLimit → `failed`; name ownership untracked | `Type=dbus`+`BusName=` (verify) or `Restart=always`+`StartLimitIntervalSec=0`+`RequestName` DO_NOT_QUEUE fail-loud; hook `graphical-session.target` |
| H1 | HIGH | Non-recursive watch of a directory root is sufficient | `icon-templates` is nested; `canonical_hash_dir` is recursive → missed events | Add explicit per-subdirectory watches (bounded recursion) + depth-2 test |
| H2 | HIGH | AD-19 governs presence/absence/recovery | AD-19 defers daemons to Phase 5; no absence rule | Move to a new Phase-5 AD; design + test absence; fix memlog/epics |
| H3 | HIGH | Contract is the trigger enum source of truth | Contract has 4 values; code enforces 6 (in 3 places) | Sync contract + drift test across `reconcile.py`/`inspect.py`/`seeder.py` before adding `reactive` |
| H4 | HIGH | Caller→topic authorization by "sender identity" | No stable identity on a same-UID session bus | Define basis (hub-spawned PID table / exe / cookie); encode in JSON; test |
| M1 | MEDIUM | Absence/recovery + hub hydration | In-memory hub state lost on restart; no re-announce path | Persist/reconstruct topic state or `NameOwnerChanged` re-announce; test hub restart mid-job |
| M2 | MEDIUM | "Enumerated allowlist" | Dynamic `find_*` (spine-then-repo-ancestors); icon-mappings can be a dir | Freeze+log roots; disjointness assertion; normalize file/dir |
| M3 | MEDIUM | `a{sv}` payload handling | GJS `deepUnpack()` is one level; needs `recursiveUnpack()` | Document + test unpack rule |
| M4 | MEDIUM | `desired.json` relocated; unit env/target ready | No writer; reader still `state_root`; no `~/.config/dotfiles`; target deferred | Add writer + migration; bind `graphical-session.target`+fail-loud env check |
| M5 | MEDIUM | `capture.state` supports the timer convention | Payload has only `state`; no start, no `error` | Add start + `error` to schema/enum |
| L1-L4 | LOW | Codegen note, companion path, hydration methods, crash-loop wording | As above | As above |

---

## 4. Net assessment

- **Reality-checked and sound:** codegen availability (self-corrected),
  session-bus single-owner + `GDBusProxy` signal/name-owner mechanics, inotify
  overflow/limits/non-recursion, existence of Python sync clients, uwsm
  installed, the four derivation inputs, the poll anti-pattern grounding, and
  the deferral of the D-Bus/inotify library choice.
- **Asserted, not checked (must fix before implementation):** AD-33
  supervision, AD-19 attribution, AD-42 enum locking, AD-38 identity basis,
  the directory-root watch, the "enumerated" watch set, `desired.json`
  relocation, `capture.state` timer support.
- **Gate call:** cannot be called "ready" while C1 and H1 stand, because both
  defeat the daemon's two stated guarantees (recover from death; react to the
  declared roots). H2–H4 are cheap doc/decision corrections but must land in
  the spine (not only in a story) since other work binds them.
