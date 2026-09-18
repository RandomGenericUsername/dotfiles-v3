# Design: add-gtk4-event-reload

## 1. Framing: why an event-driven restart, not hot reload

| Consumer | Code ours? | Mechanism | Restart? |
|---|---|---|---|
| ICME | yes (AGS/GJS) | subscribes `wallpaper.state`, `app.apply_css` live | no |
| wallpaper-selector | yes (AGS/GJS) | subscribes `wallpaper.state` for progress/LIVE | no |
| AGS bar | yes (AGS/GJS) | restarted by `AgsReloader` (no in-process reload hook) | yes, in chain |
| `hyprmod`, `power-options-gtk` | **no** (AUR binaries) | GTK4 parses CSS once at startup | **yes — only possible** |

GTK4/libadwaita offers no runtime CSS reload channel for arbitrary apps; the
portal `color-scheme` signal only flips light/dark. Therefore the change keeps
a restart for the two third-party apps and moves *when/who* to the hub-consumer
model. Any future fork of either app could adopt the ICME `apply_css` pattern
and be removed from `TARGET_APPS`.

## 2. Contract change

`wallpaper.state` payload becomes:

```jsonc
{ "state": "applying|visible|done|error", "wallpaper_hash": "s", "trigger": "set|regenerate|reconcile|reactive" }
```

- `trigger` is **optional/additive** — existing consumers ignore unknown keys
  and the embedded schema is `additionalProperties: True`
  (`emit_validation.py:165-173`). Contract versioning rule
  (`contracts/event-contract.json` `versioning.non_breaking`) keeps it on
  `org.dotfiles.Events1`.
- Update sites (all must land together, task group 1):
  - `contracts/event-contract.json` (+ `.xml`, `.md`) `topics["wallpaper.state"]`
  - embedded schema + required list decision in `emit_validation.py`
  - publisher `_publish_wallpaper_state` (`main.py:446`)
  - publisher call sites: wallpaper set (`trigger="set"`), icons regenerate
    (`trigger="regenerate"`), standalone reconcile (`trigger="reconcile"`),
    daemon reactive converge (`trigger="reactive"`)
  - GJS pinned literals: `wallpaper-selector/lib/event-bus-core.ts` and
    `icon-color-mapping-editor/lib/event-bus-core.ts` (payload types) and their
    `tests/event-contract-drift.mjs`
- `trigger` is added to the schema as an optional `enum` property, so old
  publishers remain schema-valid during rollout and tests can assert it.

## 3. Subscriber binding (`gtk4_app_subscriber.py`)

Mirrors `BarSubscriber` (`bar_subscriber.py`) — same jeepney blocking
transport, same machine-verified protocol:

1. register match rules (`DomainEvent`, `JobsCleared`, `NameOwnerChanged`) on
   the hub's object path;
2. `GetTopicState("wallpaper.state")` hydration → baseline `(epoch, seq)`;
3. drop any signal whose `(epoch, seq)` is not lexicographically greater;
4. `JobsCleared`/name-owner change → re-hydrate, never replay;
5. structural validation (64 KiB, depth 8) before dispatch.

Dispatch rule (the whole point of `trigger`):

```
on DomainEvent("wallpaper.state", payload):
    if payload.state != "done": return
    if payload.trigger == "regenerate": log + return   # icons-only; adw CSS unchanged
    restart_allowlisted_apps()                          # set | reconcile | reactive
```

Contract constants are read from `contracts/event-contract.json` at import time
(never from `runtime.domain`/`runtime.ports`), exactly as `bar_subscriber.py`
does — consumer and hub depend on the contract, not on each other.

## 4. Hosting: daemon background thread

`dotfiles-runtime daemon run` (`main.py:2074`) already owns `org.dotfiles.Events`
and is the always-on `dotfiles-runtime-daemon.service`. The subscriber's
blocking read loop runs in a daemon thread started there (its own
`open_dbus_connection`), so the CLI publisher and the subscriber are different
processes — the true consumer model, not a self-loop shortcut.

- **Degraded mode:** daemon stopped → no subscriber → no auto-restart. This is
  accepted and surfaced in docs; `dotfiles-runtime gtk4 restart` is the manual
  recovery path.
- **Reactive converge coverage:** the daemon publishes `wallpaper.state done`
  with `trigger="reactive"` after its converge (additive publish), so the
  subscriber reacts to daemon-driven palette changes too. Without this, a
  reactive reconcile that regenerates the palette would be silent.

## 5. Interaction with `wallpaper-set-visible-first`

That change (active) specifies: "`done` arrives only after all consumers
reloaded" (`specs/visible-first-swap/spec.md`). With GTK4 restarts moved out of
the chain, that clause is amended in spirit: **`done` signals the synchronous
reload chain (Hyprland, AGS, Hyprpaper, terminal, kitty) is complete;
event-driven consumers act on `done` afterwards.** ICME already behaves this
way (its `apply_css` runs on `done`), so this is a clarification, not a new
class of behavior. This change's spec states the amended guarantee explicitly;
`proposal.md` calls it out so reviewers see the overlap. No edit to the
visible-first change folder is made (it is not ours to mutate).

Ordering safety: `done` is published after the swap and after
`current/colors.adw.css` is repointed, so a subscriber-triggered restart always
reads the new palette. A restart landing milliseconds after `done` is
invisible to GUI progress indicators (they refresh on the same event).

## 6. Restart safety contract

- **Allowlist only.** `TARGET_APPS = {"power-options-gtk", "hyprmod"}`
  (`gtk4_app_reloader.py:38`). Never wildcard-discover GTK4 apps; an app with
  genuine unsaved state (editor) can never be swept in.
- **Per-target rationale (recorded in the module docstring):**
  - `power-options-gtk` — frontend for the power-options daemon; changes apply
    to the daemon immediately, no pending buffer; reopening re-reads state.
  - `hyprmod` — writes Hyprland config and applies via `hyprctl`; state is on
    disk; reopening re-reads it. Only a half-typed field in an open dialog can
    be lost — identical to the user closing the window.
- **Graceful first.** SIGTERM is the same shutdown path as clicking the window
  close control; SIGKILL is only an escalation after the grace window.
- **Race-free handoff (new).** After SIGTERM, poll `os.kill(pid, 0)` until
  `ProcessLookupError` (budget ≈ 2 s, reusing the existing poll constants);
  on timeout SIGKILL and poll again; only then `Popen` the relaunch. This
  guarantees the old single-instance owner released its bus name.
- **Skip list** (`skip_apps`) stays the documented per-app opt-out.
- **Vacuous success** when no target is running (unchanged).

## 7. Rewiring the chain

- Remove `Gtk4AppReloader()` from `_build_reloaders` (`main.py:402-407`); update
  the docstring's pinned consumer order and the composition tests
  (`tests/unit/test_cli_reconcile.py:168-180`, `test_cli_wallpaper_set.py:366-414`).
- `gtk4_app_reloader.py` keeps `_discover_gtk4_apps`, `TARGET_APPS`, and the
  hardened `_restart`; `Gtk4AppReloader` may remain as a thin callable used by
  the subscriber and the escape-hatch command (single primitive, two callers).
- New CLI: `dotfiles-runtime gtk4 restart` → discover + restart, exit non-zero
  on any failure; no hub dependency.

## 8. Testing & verification

- **Unit:** `test_gtk4_app_subscriber.py` mirrors `test_bar_subscriber.py`
  (hydration baseline, epoch/seq discard, `JobsCleared` re-hydration,
  validation, trigger gate: `regenerate` skipped, `set/reconcile/reactive`
  restart). Hardened `_restart` tests: wait-before-relaunch ordering,
  SIGKILL escalation, still-alive-after-both → `False`.
- **Contract:** emit-validation tests accept `trigger` (and stay valid when it
  is absent); both GJS drift tests green.
- **Integration:** daemon starts subscriber thread; stop/start re-hydrates;
  `wallpaper set` with fake apps → restart invoked once; icons regenerate →
  not invoked.
- **Regression:** full `src/runtime` suite green
  (`uv run --directory src/runtime pytest -q`).
- **Manual proof (requires user, E2E):** install from the worktree
  (`uv tool install --force --no-cache <worktree>/src/runtime`), restart the
  daemon, then with `power-options-gtk` + `hyprmod` open: (a) change wallpaper →
  both close/reopen with the new palette; (b) press the contrast toggle → no
  restart; (c) stop the daemon → manual `dotfiles-runtime gtk4 restart` works;
  (d) no apps open → no-op.
