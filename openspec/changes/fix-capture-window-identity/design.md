# Design: fix-capture-window-identity

## The shape of the bug

One `ClassicWindow` per monitor, one name for all of them, and two helpers that
needed "my window" and asked the global registry instead:

```ts
app.get_window(WINDOW_NAME)   // windows.find(...) over GTK's list
```

Three things have to be true for that to be wrong rather than merely redundant,
and all three were measured on this host.

### 1. The name is duplicated, not unique

`app.tsx` has no `index` suffix, no connector, nothing that distinguishes one
window from another:

```ts
for (const monitor of app.get_monitors()) {
  app.add_window(ClassicWindow(monitor, ports, state))
}
```

and `ClassicWindow` hard-codes `name="capture-window"` on every construction.

### 2. `find` is over an order that is not registration order

`App.get_window` is `this.windows.find(...)` (`app.ts:156-158`), and `windows` is
`Gtk.Application.get_windows()`. Two real `ClassicWindow`s registered A then B:

| when | `app.windows` | resolved to |
|---|---|---|
| fresh, nothing mapped | `B,A` | **B** |
| after A shown | `A,B` | **A** |
| after A and B both shown | `B,A` | **B** |
| after A hidden | `B,A` | **B** |
| settled (shell toggles done) | `A,B` | **A** |

`find` returns the first element, so on a fresh instance the answer is the
**last-registered** window; after a map/unmap cycle it flips to the other one.

**Correction to an earlier claim in this change series.** `fix-capture-per-monitor-state/design.md:160-163`
says `ags toggle capture-window` "resolves to the LAST-added window, every
time", and gives the mechanism as `windows.find(...)`. The measured behaviour is
right and the mechanism is wrong, and the difference matters: if it really were
always the last-added, the target would at least be *stable*. It is not. The same
binary, same instance, same command, resolved to B at one moment and to A two
minutes later. Any plan that reasons "the toggle always hits the last monitor, so
the other window is unreachable" holds only for the window's whole lifetime until
its first map.

### 3. Both helpers are per-window actions

`hideCaptureWindow()` is called from `takeScreenshot()`, `startRecording()` and
`onKey(Escape)` — all reached from a widget inside a window.
`syncWindowSize()` is called from `selectMode()`, `openSettings()` and handed to
`RecordingPage`. There is no reading of either in which "some other window" is a
correct answer.

### The reproduction, verbatim

Two real `ClassicWindow`s on this host's single monitor, both made visible, the
capture button pressed on **A**. The pre-fix lookup re-implemented verbatim in
the same process so the pair is comparable:

```
CONTROL (pre-fix code path, run before any window is mapped)
   app.windows = B,A
   app.get_window("capture-window") -> B
   both up: A=true B=true   (pressing the button on A)
   after the old hide: A=true B=false
   -> A hidden: NO  <-- A STILL VISIBLE
   -> B hidden: yes  <-- WRONG WINDOW HIDDEN

FIXED  hideCaptureWindow() — capture pressed on window A, both up
      launcher argv: ["capture-tool","screenshot","--target","region",...]
   after capture on A: A=false B=true
   -> A hidden: yes  CORRECT
   -> B hidden: no   CORRECT

FIXED  syncWindowSize() — settings opened on window A
   before: A=606x594 B=606x594
   after:  A=713x999 B=606x594
   -> A grew: yes  CORRECT
   -> B grew: no   CORRECT
```

Note that the earlier per-monitor-state harness saw the pre-fix lookup resolve to
**A** and therefore could not exhibit the defect; the outcome depends on when in
the window's life you ask, which is exactly the property being fixed.

## The change

```ts
export function ClassicWindow(gdkmonitor, ports, state): Astal.Window {
  let captureWindow: Astal.Window | null = null

  function hideCaptureWindow() {
    if (captureWindow) captureWindow.visible = false
  }

  function syncWindowSize() {
    const window = captureWindow
    const panel = window?.get_child()
    if (!window || !panel) return
    const [, width] = panel.measure(Gtk.Orientation.HORIZONTAL, -1)
    const [, height] = panel.measure(Gtk.Orientation.VERTICAL, width)
    window.set_default_size(width, height)
  }

  return (
    <window ... $={(self) => { captureWindow = self; /* ...unchanged... */ }}>
  )
}
```

Three properties are deliberate:

- **The helpers move inside the factory.** They were module-level functions; a
  module-level `captureWindow` would be shared by every monitor's window. See
  below.
- **The reference comes from `$`, not from a return value.** gnim's
  `jsx.ts:343` calls `$?.(object)` with the constructed instance, after the
  children are appended. The existing handler already relied on this
  (`self.add_controller`, `self.connect("map", …)`), so nothing new is being
  assumed about gnim.
- **The null guard replaces the old null guard.** Both versions early-return in
  the same window of the lifecycle: `selectMode("screenshot")` runs from the
  screenshot tab's `$` handler, which gnim evaluates while building the child
  array — before the `<window>` exists. Previously `get_window` returned
  `undefined`; now `captureWindow` is `null`. Same early-return, same reason.
  `add_window` has not been called at that point either way, so nothing that used
  to work stops working.

### The bug I wrote first

The first version of this change put `let captureWindow: Astal.Window | null =
null` next to `WINDOW_NAME`, at module scope, with the two helpers left
module-level. `app.tsx` builds one window per monitor, so the second construction
overwrote the first window's self-reference and the defect returned verbatim —
measured, not theorised:

```
FIXED  hideCaptureWindow() — capture pressed on window A, BOTH visible   [module-scope version]
   after capture on A: A=true B=false
   -> A hidden: NO <-- still visible
   -> B untouched: NO <-- wrong window hidden
```

Identical to the control. It is the same cardinality mistake
`fix-capture-per-monitor-state` was about, in the opposite direction: there the
per-application state was allocated per window; here the per-window reference was
allocated per module. `tests/ts/window-identity.test.ts` pins the declaration to
*inside* the factory for exactly this reason.

## Blast radius of the name — what a rename would cost

Everything in the repo that depends on the literal `capture-window`
(`rg -n 'capture-window'`, whole tree):

| site | kind | breaks if renamed? |
|---|---|---|
| `ui/classic/ClassicWindow.tsx:97,320` | the definition | — |
| `style.css:29` `window#capture-window` | GTK **id** selector | **yes, silently.** In GTK4 `#foo` matches `Gtk.Widget:name`, not a class. The rule sets `background-color: transparent; color: @color_foreground` on the surface. Drop the match and the window stops being transparent — the first-frame rectangle described in the comment above that rule returns. |
| `cli_tools/templates/capture-ui.j2:18` `WINDOW="capture-window"` | provisioned launcher | **yes, and the keybind dies quietly.** `~/.local/bin/capture-ui` runs `ags toggle "$WINDOW" -i "$INSTANCE"`, which throws `no window registered with name "..."`; the launcher then *falls through* to `ags quit -i capture` and a fresh `ags run` — so the window never appears and `SUPER+PRINT` does nothing. **This file is provisioned; changing it needs a provision run.** |
| `dotfiles/config/hypr/keybindings.lua:42-46` | `exec_cmd("capture-ui")` | no — it calls the launcher, not the window |
| `verify/vars/main.yml:70` | asserts `capture-ui` the FILE exists | no — asserts the path, not the contents |
| `scripts/capture-classic-parity.json` (`used` contains `capture-window`) | gate check 6 | no, but only by luck: the token enters `used` via `class="capture-window"` (line 321), not via `name=`. |
| `openspec/**`, `_bmad-output/**` | prose | no |

So the safe rename is three edits (window name, `style.css` selector,
`capture-ui.j2`) **plus a provision run**, and it is not obvious: miss the
stylesheet and you get a cosmetic regression; miss the launcher and `SUPER+PRINT`
stops working while `ags list` still shows `capture`. Neither fails a test today.

That cost is why this change stops at self-scoping. It removes both defects with
no rename, no stylesheet edit, no provision run.

## The launcher question this leaves open

`ags toggle capture-window -i capture` reaches **one** window, and it is a fixed
one — on a fresh instance the last-registered, i.e. the last monitor
`get_monitors()` yielded. So on a two-monitor host the capture panel opens on the
same monitor every time, regardless of which monitor is focused, and the other
monitor's window is never shown by anything. Two consequences:

1. The defect fixed here is currently **unreachable through the keybind**, because
   only one window is ever visible. It is a latent defect, and it becomes live the
   moment anything else shows a second window.
2. "Open on the focused monitor" is a genuine UX gap and is **not** addressed
   here. It needs per-monitor names (so the launcher can name a target) or an
   `ags request` handler that toggles the focused monitor's window, and either way
   it touches `capture-ui.j2` and therefore **requires a provision run**. That is
   the operator's call.

The same shape exists in `hypr-pano` (`src/gui-tools/hypr-pano/app.tsx:12-13`
loops over monitors, `PanoWindow.tsx:27` hard-codes `WINDOW_NAME`, line 30 does
the same `get_window` lookup, and `hypr-pano-ui.j2` toggles it). Fixing capture
alone leaves the sibling tool with the original defect. Fixing both is a larger
change than this one and should be its own.

## Testing, and what it does NOT prove

`ClassicWindow` is a `.tsx` importing `ags/gtk4` and `gi://GLib`; `node --test`
has no GTK and no display, so it cannot construct one. `tests/ts/window-identity.test.ts`
pins the three reachable things instead:

1. **The lookup semantics, executed.** A model of AGS's `windows.find(...)` over
   an explicitly-set order, driving both the old name-scoped hide and the new
   self-scoped one. The old one is asserted to hide the wrong window at order
   `[b,a]` and to be correct at `[a,b]` — both measured, and the pair is the
   non-determinism stated as a test rather than described in a comment. The new
   one is asserted correct at every order tried.
2. **The wiring, read from the real source** (comment lines stripped): no
   `app.get_window(` survives, `captureWindow = self` is present, and the
   declaration sits **after** `export function ClassicWindow(` — the module-scope
   regression above is the assertion that catches it.
3. **The name contract, read across three files.** The window's `name`, the
   `window#…` selector in `style.css`, and `WINDOW=` in `capture-ui.j2` must all
   agree, and the launcher must still toggle `$WINDOW` on `$INSTANCE`. This is
   the guard against the silent rename described in the blast-radius table.

(1) is a model of AGS's lookup, not of AGS's lookup running; (2) and (3) are
source-shape guards. Both are weaker than a GTK test and are labelled as such in
the file. The end-to-end proof is the harness above, which needs a live AGS
session and is therefore kept out of `tests/` — the same reasoning as
`fix-capture-per-monitor-state/repro/README.md`.

Each assertion was negative-tested by reintroducing the defect it guards:

| reintroduced | test that failed |
|---|---|
| `app.get_window(WINDOW_NAME)` in the helper | `ClassicWindow resolves no window by name` |
| `let captureWindow` hoisted to module scope | `the self-reference is per-CALL, not per-module` |
| window renamed, launcher untouched | `the window, the stylesheet and the provisioned launcher agree on the name` + `the name is still shared by every monitor's window, by design` |
| `captureWindow = self` deleted | `ClassicWindow resolves no window by name` |
| a stray second `let captureWindow…` | `the self-reference is per-CALL, not per-module` |

## Risk

Low. `ClassicWindow`'s signature is unchanged, so no caller changes. On a
one-monitor host — every configuration that exists today — the old lookup and the
new reference resolve to the same object, and the construction-time
`syncWindowSize()` no-op is preserved for the same reason. The multi-monitor case
loses a wrong-window hide and a wrong-window resize and gains nothing that can
misbehave.

Not proven by this change, and stated plainly: nothing here was observed on a
host with two monitors. Every multi-monitor statement above is either (a) a
property of the two-window construction, measured on one monitor, or (b) a
reasoning step about which monitor the launcher's window belongs to, which this
host cannot settle.