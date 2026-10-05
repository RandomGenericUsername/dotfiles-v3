# fix-capture-monitor-lifecycle

Two multi-monitor gaps in the capture GUI, both recorded as deliberately
deferred by earlier changes and both now closed.

| gap | recorded in | what it was |
|---|---|---|
| no monitor hotplug handler | `harden-capture-typecheck-config/design.md` §5.1 | `app.tsx` read `app.get_monitors()` once inside `main()`. A monitor plugged in after login got no window; one unplugged kept its window alive and still reachable by name. |
| the launcher opens the wrong monitor's window | `fix-capture-window-identity/proposal.md` "Non-goals" | every window shares the name `capture-window`, so which one `ags toggle capture-window` reaches is decided purely by list order — and it is never the focused monitor's. |

`hypr-pano` has the identical one-shot `for (const monitor of
app.get_monitors())` at `src/gui-tools/hypr-pano/app.tsx:12` and is **not**
touched here. The window set is written to be reusable (it takes a topology port
and a window factory, and names no layout), so that change is now a small one
rather than a re-design.

## What changes

- **New, pure:** `domain/monitor-registry.ts` — the decisions. `monitorKey`,
  `isIdentified`, `planSync`, `orderedForFocus`, `focusKey`.
- **New ports:** `ports/monitor-topology.ts` (the monitors, and a change
  subscription), `ports/monitor-focus.ts` (which monitor the user is on).
- **New adapters:** `adapters/gdk-monitor-topology.ts` (the hotplug
  subscription), `adapters/hyprland-monitor-focus.ts` (the focus source),
  `adapters/monitor-window-set.ts` (one window per monitor across hotplug, plus
  the launcher lookup).
- **`app.tsx`:** the one-shot loop becomes a `createMonitorWindowSet(...)` call.
  No logic; it builds the adapters and renders.
- **Provisioning:** six new placement entries in `gui_tools_app_files` and six
  new assertions in `verify_gui_tools_app_files`.
- **No change** to `style.css`, to the window name, to `ClassicWindow.tsx`, to
  any CSS class, or to `capture-ui.j2`. The keybind keeps working with **no
  provision run**.

## Two things the brief got wrong

Both were checked against source and against a live session before anything was
written, and both changed the design. Evidence in `design.md` §1 and §2.

1. **There is no `monitor-added` / `monitor-removed` signal on `Gdk.Display`.**
   The recorded version of this claim (`harden-capture-typecheck-config`
   design.md §5.1: "GTK/GdkMonitor carries a `monitor-added`/`monitor-removed`
   signal pair that this does not connect") is false on GTK 4.22. Connecting to
   it raises `No signal 'monitor-added' on object 'GdkWaylandDisplay'`. The real
   delivery is `Gio.ListModel::items-changed` on the model
   `Gdk.Display.get_monitors()` returns.

2. **GTK cannot name the focused monitor at all.** The brief's first suggested
   direction — `display.get_monitor_at_window` /
   `Gdk.Display.get_default_seat().get_focus()` — names four APIs that GTK4
   removed. All four measured `undefined`. The compositor is the only source
   that exists, which is why focus is a port.

A third, smaller correction: `get_window`'s resolved window is **not unstable**
on this stack — see `design.md` §2.2. It is stably wrong, which needs a
different fix than the brief assumed.

## Impact

- `src/gui-tools/capture-tool/{domain,ports,adapters}/` — six new modules.
- `src/gui-tools/capture-tool/app.tsx` — the loop becomes a wiring call.
- `src/provisioning/ansible/roles/gui_tools/vars/main.yml` — six placements.
- `src/provisioning/ansible/roles/verify/vars/main.yml` — six assertions.
- `src/provisioning/tests/unit/test_gui_tools_role.py` — the exact-list count
  24 → 30, with the new entries and the reason.
- `src/gui-tools/capture-tool/tests/ts/monitor-registry.test.ts` — new, 29 tests.
- `src/gui-tools/capture-tool/tests/ts/ui-state-ownership.test.ts` — one
  assertion re-targeted at the factory that replaced the loop. The invariant
  ("the shared state is built outside the per-monitor construction") is
  unchanged and the replacement check is strictly stronger: it also fails if
  `createUiState()` is smuggled into the window set.
- **No provisioning change to `capture-ui.j2`**, no `style.css` change, no CSS
  class added or removed. The launcher and the keybind work untouched.