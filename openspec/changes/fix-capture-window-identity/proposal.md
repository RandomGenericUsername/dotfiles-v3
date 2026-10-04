## Why

`ClassicWindow` resolved "my own window" by name:

```ts
const WINDOW_NAME = "capture-window"

function hideCaptureWindow() {
  const window = app.get_window(WINDOW_NAME)   // <-- whichever duplicate comes first
  if (window) window.visible = false
}
```

`app.tsx` builds one `ClassicWindow` per monitor and **every one of them is named `capture-window`**, so the lookup cannot mean "this window". AGS resolves a name with

```ts
get_window(name: string) { return this.windows.find((w) => w.name === name) }
// /usr/share/ags/js/lib/gtk4/app.ts:156-158
```

— a **first match over `Gtk.Application.get_windows()`**, which is *not* registration order and is re-ordered as windows are mapped and unmapped. Measured live on this host, two real `ClassicWindow`s on one monitor:

| when | `app.windows` | `get_window("capture-window")` resolved to |
|---|---|---|
| fresh instance, nothing mapped | `B,A` | **B** — the window nobody pressed |
| after A had mapped and unmapped | `A,B` | **A** |

So which window "the capture window" is depends on map history, not on which one
the user is looking at.

**The reported symptom is confirmed.** Both windows visible, capture pressed on
window A, pre-fix code running against the same two windows:

```
   app.windows = B,A
   app.get_window("capture-window") -> B
   both up: A=true B=true   (pressing the button on A)
   after the old hide: A=true B=false
   -> A hidden: NO  <-- A STILL VISIBLE
   -> B hidden: yes  <-- WRONG WINDOW HIDDEN
```

A visible capture panel left on screen during a region capture is the same
first-frame rectangle the `style.css` comment at lines 22-28 was written to
avoid, and the panel the user is still looking at is not the one that hid.

`hideCaptureWindow()` and `syncWindowSize()` are the only two affected call
sites, and both are per-window actions reached from a widget *inside* a window —
neither has any reason to consult a global registry. This change removes that
consultation.

## What Changes

- `ClassicWindow` captures **its own** `Astal.Window` from the `<window>` `$`
  handler (gnim passes the constructed instance) and `hideCaptureWindow()` /
  `syncWindowSize()` use that reference.
- The `ags/gtk4/app` import is removed from `ui/classic/ClassicWindow.tsx` —
  the view no longer touches the global window registry at all.
- `WINDOW_NAME` and `name="capture-window"` are **kept**, with a comment
  recording that the shared name is now load-bearing for exactly two
  out-of-process consumers and must not be treated as an internal identifier.

## Non-goals

- **Not renaming the window per monitor.** The literal `capture-window` is
  consumed by `style.css:29` (`window#capture-window` — a GTK **id** selector,
  which matches the widget NAME, not the class) and by
  `src/provisioning/ansible/roles/cli_tools/templates/capture-ui.j2:18`, which
  is provisioned to `~/.local/bin/capture-ui` — the binary the `SUPER+PRINT`
  keybind runs. Renaming means a stylesheet change **and a provision run**, which
  is the operator's decision, not this change's. See design.md §Blast radius.
- **Not making the keybind open the focused monitor's window.** That is a real
  and separate gap (`ags toggle capture-window` reaches one fixed window, so on
  a multi-monitor host the panel opens on the same monitor every time). Fixing it
  requires the launcher change above. Recorded in design.md, not done here.
- **Not touching monitor hotplug.** `app.tsx` reads `app.get_monitors()` once in
  `main()` and registers no monitor-changed handler, so a monitor attached after
  login gets no window at all. Pre-existing, orthogonal, and out of scope.
- **Not changing the window's appearance or any CSS class token.** Gate check 6
  stays at 33 used / 28 styled.

## Impact

- `src/gui-tools/capture-tool/ui/classic/ClassicWindow.tsx` — two closures, one
  assignment, one dropped import. No signature change; `ClassicWindow`'s three
  parameters are untouched, so `app.tsx` and every existing caller are unaffected.
- `src/gui-tools/capture-tool/tests/ts/window-identity.test.ts` — new.
- **No provisioning change.** `src/provisioning/**` is untouched, so
  `~/.local/bin/capture-ui` and the deployed keybind keep working with no
  provision run. That is the point: this fix is the one that needs no operator
  action.

### Behaviour on a one-monitor host (i.e. every host that exists today)

Unchanged, and deliberately so. One window, one name, `get_window` and the
self-reference resolve to the same object. The construction-time
`syncWindowSize()` call — issued from the screenshot tab's `$` handler, which
gnim runs while constructing the child array, before the window exists — still
early-returns, for the same reason it always did (`captureWindow` is null where
`get_window` used to return `undefined`).