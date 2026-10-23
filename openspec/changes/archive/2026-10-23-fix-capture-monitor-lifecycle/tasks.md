# Tasks: fix-capture-monitor-lifecycle

## 0. Investigation (done before anything was written)

- [x] 0.1 Read the two recorded framings:
      `harden-capture-typecheck-config/design.md` §5 and
      `fix-capture-window-identity/proposal.md` "Non-goals".
- [x] 0.2 Read `@girs/gdk-4.0.d.ts`, `@girs/gio-2.0.d.ts`,
      `@girs/astal-4.0.d.ts`, `/usr/share/gir-1.0/Gdk-4.0.gir`,
      `/usr/share/ags/js/lib/gtk4/app.ts`, `/usr/share/ags/js/lib/app/dbus.ts`.
- [x] 0.3 Probe the live stack: which signals `Gdk.Display` actually has; what
      `get_monitors()` returns and whether it is stable; whether GTK can name the
      focused monitor at all; what `get_window` resolves to across real external
      `ags toggle` calls; whether the D-Bus path can be intercepted.
      → `repro/probes/`. Two brief premises disproved; see design.md §1, §2.2,
      §2.3, §2.5.

## 1. Domain — the decisions, pure

- [x] 1.1 `domain/monitor-registry.ts`: `MonitorDescriptor`, `WindowBinding<T>`,
      `monitorKey` (connector-first so a resolution change does not re-key).
- [x] 1.2 `planSync`: diff-owned-bindings against the full monitor set.
      Idempotent, so duplicate notifications are safe.
      *Caught by its own test:* the first draft walked `monitors` for `create`
      and emitted one entry per colliding key, i.e. two windows for one slot.
      Fixed by walking the deduped map instead.
- [x] 1.3 `orderedForFocus`: focused monitor's window first, then registration
      order. Never reads GTK's list.
- [x] 1.4 `focusKey`: match the compositor's monitor name against the GDK
      connector; null when there is no match, so the fallback is deterministic
      rather than arbitrary.
- [x] 1.5 `isIdentified`: a monitor that reports no connector, no model and
      geometry 0,0,0,0 is not addressed yet — no `create`, and deliberately no
      `destroy` either.
      *Found by measuring, after the first draft shipped:* at the instant
      `items-changed` fires a new monitor reports exactly that, so every monitor
      in one event keyed identically (one window silently dropped) and the key
      changed ~200 ms later (destroy + rebuild). See design.md §1.6.

## 2. Ports

- [x] 2.1 `ports/monitor-topology.ts`: `MonitorEntry` (data + opaque native
      handle), `MonitorTopology` (`list`, `subscribe`). The port doc records why
      `subscribe` takes no arguments.
- [x] 2.2 `ports/monitor-focus.ts`: `MonitorFocus.focusedConnector(): string |
      null`. The whole measured negative result on GTK4 focus APIs is recorded
      here, so the next reader does not retry it.

## 3. Adapters

- [x] 3.1 `adapters/gdk-monitor-topology.ts`: subscribe to `items-changed` on the
      one `Gio.ListModel` `get_monitors()` returns, plus `Monitor::invalidate`.
      Both payloads ignored; the handler re-reads.
      Plus `notify::connector` / `notify::geometry` per monitor, re-hooked as
      monitors appear (WeakSet guard), which is what makes 1.5 land the window
      exactly once.
      The `"items-changed"` connect needs a re-declared signal: `@girs` resolves
      `Gio.ListModel`'s `connect` through the generic `ListModel.Interface<A>`
      helper and drops interface signals. The same error occurs in AGS's own
      `app.ts:240`, where it is one of the 28 tolerated third-party errors.
- [x] 3.2 `adapters/hyprland-monitor-focus.ts`: `AstalHyprland`'s focused
      monitor via a dynamic import whose rejection degrades to "unknown".
      Confined to one adapter so the hotplug half stays compositor-agnostic.
- [x] 3.3 `adapters/monitor-window-set.ts`:
      - `createMonitorWindowSet` — owns the bindings, applies `planSync`,
        builds and destroys. Destroy path is `remove_window` then `destroy()`.
      - `installFocusedWindowLookup` — replaces `App.prototype.get_window`, the
        one call on the launcher's path that is not bound at construction. Falls
        back to AGS's own implementation. Idempotent.

## 4. Composition root

- [x] 4.1 `app.tsx`: the one-shot `for (const monitor of app.get_monitors())`
      loop becomes `createMonitorWindowSet({...})` + `installFocusedWindowLookup`.
      No logic; `buildPorts()` and the single shared `createUiState()` unchanged.

## 5. Provisioning

- [x] 5.1 Six entries in `gui_tools_app_files`.
- [x] 5.2 Six assertions in `verify_gui_tools_app_files` — `test_verify_role`
      caught the omission via its placed-vs-verified coverage lock.
- [x] 5.3 `test_gui_tools_role`'s exact-list count 24 → 30, with the new entries.
- [x] 5.4 `capture-ui.j2` and `style.css` **deliberately untouched** — the whole
      point of the seam is that no operator action is needed.

## 6. Tests

- [x] 6.1 `tests/ts/monitor-registry.test.ts` — 29 tests: `planSync` (add,
      remove, full unplug, replug, no-op under repeated notification, resolution
      change, unnamed monitors, key collision, one-pass swap, unidentified
      monitors — including the two-arriving-in-one-event collision that 1.5
      exists to prevent), `orderedForFocus`
      and `focusKey` (focus honoured per monitor, unknown focus falls back
      deterministically, no mutation of the caller's array), the negative control
      over a model of GTK's measured list order, and the wiring read from source.
- [x] 6.2 `tests/ts/ui-state-ownership.test.ts` — one assertion re-targeted at
      the factory that replaced the loop. Invariant unchanged and the check is
      stronger: it now also fails if `createUiState()` reaches the window set.
      *This test caught the move* rather than being weakened around it.

## 7. Harness

- [x] 7.1 `repro/monitor-lifecycle-harness.tsx` — 8 steps against the real
      `Astal.Window`s and the real App singleton: construct, hotplug-add, focus
      change, duplicate notification, unplug (destroy, not hide), replug,
      unknown-focus fallback, and the real focus adapter against the real monitor
      set.
- [x] 7.1a `repro/real-hotplug.sh` — END TO END on a real second output
      (`hyprctl output create headless`). Window count tracks monitor count
      through add / remove / re-add. Found the connector-timing defect in 1.5.
- [x] 7.1b `repro/launcher-focus.sh` — END TO END for Gap 2 on a real
      two-monitor layout, pre- and post-change. Detector is `hyprctl layers`
      (output + namespace), not pixels; the pixel attempt is kept and labelled
      unsound in 7.5.
- [x] 7.2 `repro/probes/gtk4-api-probe.tsx` — the §1/§2.5 API facts.
- [x] 7.3 `repro/probes/launcher-interception-probe.tsx` — GTK's list order, and
      `toggle_window` vs `get_window` interceptability, driven by real external
      `ags toggle` calls.
- [x] 7.4 `repro/README.md` — how to run each, and what this host cannot do.
- [x] 7.5 `repro/pixel-parity.sh` — kept but labelled SUPERSEDED: the panel is
      translucent over live desktop content, so a whole-screen mean measured
      0.644 (old) vs 0.054 (new) on the same panel, entirely from desktop
      content differing. `launcher-focus.sh` replaced it.

## 8. Verification

- [x] 8.1 `make capture-test` → 144 pass / 0 fail / 0 skipped (115 + 29).
- [x] 8.2 `make capture-typecheck` → 0 errors.
- [x] 8.3 `python3 scripts/capture-hexagonal-gate.py` → PASS, check 6 at
      33 used / 28 styled.
- [x] 8.4 Capture `pytest tests/` → 97.
- [x] 8.5 `uv run --directory src/provisioning pytest tests/unit -q` → 720
      passed.
- [x] 8.6 Harness run: all 8 steps OK; probes reproduce every quoted number.
- [x] 8.7 `repro/real-hotplug.sh`: 3 monitors created -> 3 windows, 1 destroyed,
      count tracks throughout.
- [x] 8.8 `repro/launcher-focus.sh`: post-change opens on the focused monitor
      (eDP-1); pre-change opens on HEADLESS-17 with focus on eDP-1.

## 9. Out of scope (recorded, not done)

- **`hypr-pano` has the identical gap.** `src/gui-tools/hypr-pano/app.tsx:12` is
  the same one-shot `for (const monitor of app.get_monitors())`. It was excluded
  by the brief. The window set takes a topology port and a window factory and
  names no layout, so adopting it there is small — but it is its own change, and
  `hypr-pano`'s launcher has the same name-collision shape and would need the
  same seam.
- **The `fix-capture-window-identity` design doc's ordering claim** (that
  `get_window`'s target moves on map/unmap) does not reproduce on GTK 4.22.5.
  Left untouched rather than rewritten: its assertions all still hold and only
  its stated mechanism is off. design.md §2.2 records the discrepancy.
- **Focus on a virtual output.** `dispatch focusmonitor HEADLESS-N` is a no-op
  (no input device), so every real two-monitor run has focus on `eDP-1`. The
  complementary direction rests on unit tests and the harness.
- **Physical unplug.** Virtual outputs are real events but not real connectors;
  `Gdk.Monitor::invalidate` is not exercised. The dual-hook idempotence rests on
  the `items-changed` runs plus unit tests.
- **Click paths / `btop` behind the panel.** No input injection on this host and
  `btop` needs a TTY. Neither is touched by this change; see `repro/README.md`.