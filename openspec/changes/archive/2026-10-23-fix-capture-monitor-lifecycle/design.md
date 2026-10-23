# Design: fix-capture-monitor-lifecycle

Everything below that says "measured" was measured on this host — GTK 4.22.5,
ags 3.1.2, Hyprland, one monitor (`eDP-1`) — by the probes in `repro/probes/`,
whose output is quoted. Nothing here is from memory.

---

## §1 What actually delivers monitor hotplug

### 1.1 `Gdk.Display` has no add/remove signal. The recorded claim is false.

`openspec/changes/harden-capture-typecheck-config/design.md` §5.1 records:

> `GTK/GdkMonitor carries a `monitor-added`/`monitor-removed` signal pair that
> this does not connect.`

That is wrong, and the brief for this change repeated it. `repro/probes/gtk4-api-probe.tsx`
connects to a live display and prints:

```
GDK backend display: wayland-1

=== 1. THE HOTPLUG SIGNAL ===
  connect("monitor-added") -> Error: No signal 'monitor-added' on object 'GdkWaylandDisplay'
  connect("monitor-removed") -> Error: No signal 'monitor-removed' on object 'GdkWaylandDisplay'
  connect("seat-added") -> CONNECTED
  connect("closed") -> CONNECTED
  connect("opened") -> CONNECTED
```

The same fact from the introspection data, `Gdk.Display`'s complete signal set:

```python
>>> re.findall(r'<glib:signal name="([^"]+)"', Gdk_Display_block)
['closed', 'opened', 'seat-added', 'seat-removed', 'setting-changed']
```

`device-added` / `device-removed` and `tool-added` / `tool-removed` do exist on
`Gdk.Display` — and they are the closest thing to a plausible confusion here.
They are about input devices and drawing tools, not monitors, and a naive
"connect to `*-added`/`*-removed`" would wire up a handler that never fires for
a display change.

### 1.2 The real delivery is `Gio.ListModel::items-changed`

GDK replaced GTK3's per-monitor signals with a model, and documents how to
watch it — `src/gui-tools/capture-tool/@girs/gdk-4.0.d.ts:18037-18046`, verbatim:

```ts
/**
 * Gets the list of monitors associated with this display.
 *
 * Subsequent calls to this function will always return the
 * same list for the same display.
 *
 * You can listen to the GListModel::items-changed signal on
 * this list to monitor changes to the monitor of this display.
 * @returns a {@link Gio.ListModel} of {@link Gdk.Monitor}
 */
get_monitors(): Gio.ListModel;
```

Two consequences the implementation depends on, both confirmed at runtime:

* "Subsequent calls … will always return the same list" — measured:
  `a second get_monitors() is the SAME object: true`. So connecting once at
  startup is sufficient; connecting to a fresh list each time would connect to
  an object nothing emits from. The adapter holds one reference.
* the returned object is a `Gio_ListStore` (measured), i.e. a real
  `Gio.ListModel`.

AGS independently relies on exactly this, in its own `App` constructor
(`/usr/share/ags/js/lib/gtk4/app.ts:240-242`):

```ts
this.#display.get_monitors().connect("items-changed", () => {
    this.notify("monitors")
})
```

**Deliberately not used:** AGS's `notify("monitors")` re-emission. It is AGS'
convenience, not GDK's contract; subscribing to the documented
`items-changed` means this tool depends on one fewer third-party behaviour, at
the cost of one extra line.

### 1.3 The payload is a hint, so the handler re-reads and diffs

```ts
"items-changed": (position: number, removed: number, added: number) => void;
// (@girs/gio-2.0.d.ts:27902 — "At `position`, `removed` items were removed and
//  `added` items were added in their place", and "If `removed != added`, the
//  positions of all later items in the model change")
```

That describes a **range**, not a set of additions. And `Gdk.Monitor` has its own,
narrower signal (`@girs/gdk-4.0.d.ts`, GIR `gdkmonitor.c:332`):

```
Emitted when the output represented by `monitor` gets disconnected.
```

So one physical unplug can arrive as two notifications, and one notification
can describe several changes. Applying either payload incrementally is therefore
wrong by construction. `planSync` **diffs the owned bindings against the full
monitor list** instead, which makes the handler idempotent: a second identical
notification produces an empty plan. That is what lets the adapter wire up
*both* signals with no coordination between them.

The unit test `an unchanged monitor set is a NO-OP (this is what makes hotplug
idempotent)` runs the same reconcile five times and asserts nothing is created
or destroyed.

### 1.4 Can it fire before there is a main loop?

Yes, and it does not matter. `main()` is invoked from inside the GApplication
run — `App.start()` → `runAsync()` → `vfunc_command_line` → `createRoot(...)` →
`this.#main()` (`app.ts:279-297`) — so the main loop is already running when
`main()` executes and the subscription is installed. A display that changes
between `Gtk.init()` (module load, `app.ts:13`) and `main()` is already
reflected in `get_monitors()`, because the handler re-reads the list rather than
trusting an event it might have missed.

There is one ordering requirement, and the adapter handles it by construction:
`subscribe()` is called **before** the first `reconcile()`. A change arriving in
that window is therefore caught. The reverse order would drop it.

The window's `visible={false}` is unrelated — that is a widget property, and the
window simply never presents until a toggle asks it to.

### 1.5 The lifecycle for a window that must be REMOVED

`remove_window()` **then** `destroy()`, in that order, and the test
`a removed monitor's window is unregistered AND destroyed, in that order` pins
the ordering by source position.

* `remove_window` first: a destroyed window still sitting in the application's
  window list is one `ags toggle` can still resolve by name, so the launcher
  would act on a dead object.
* `destroy()` second, and not `visible = false`: hiding only unmaps. The
  `Gtk.Widget`, its subtree, its `Gtk.EventController` and its layer-shell
  surface all stay alive. Only `destroy()` releases them — which is what "must be
  destroyed, not leaked" means.

Measured (`monitor-lifecycle-harness.tsx`, STEP 5):

```
STEP 5: UNPLUG the second monitor -> its window must be DESTROYED, not hidden
    capture: destroyed the window for a monitor that went away
  windows named capture-window: 2 -> 1
  the removed window is gone from the app's list: true
  get_window resolves to window A (the survivor)
```

And on the **real** compositor, driving the shipped app
(`repro/real-hotplug.sh`, `hyprctl output create/remove`):

```
==> CREATE a virtual output
    monitors now:            2
    windows opened (log):    2
==> REMOVE it
    monitors now:            1
    windows opened (log):    2
    windows destroyed (log): 1
==> CREATE a different virtual output
    monitors now:            2
    windows opened (log):    3
    windows destroyed (log): 1

app log:
capture: opened a window for monitor eDP-1
capture: window lookup now prefers the focused monitor's window
capture: opened a window for monitor HEADLESS-11
capture: destroyed the window for a monitor that went away
capture: opened a window for monitor HEADLESS-12
```

Three monitors created across the run, three windows, one destroyed on the
removal — the window count tracks the monitor count exactly.

### 1.6 A new monitor has no identity when the notification fires

This is the one defect the implementation had on its first pass, and the only
reason the change touched the topology adapter beyond subscribing.
`repro/probes/connector-timing-probe.tsx`, against a real virtual output:

```
=== baseline ===
     connector="eDP-1" model="0x153C" KEY=connector:eDP-1
>>> items-changed #1
  IMMEDIATELY inside the handler:
     connector="eDP-1" model="0x153C" KEY=connector:eDP-1
     connector=null model="" KEY=geometry:0,0,0,0
  on the NEXT IDLE (after GTK settles):
     connector="eDP-1" model="0x153C" KEY=connector:eDP-1
     connector=null model="" KEY=geometry:0,0,0,0
   notify::connector fired: null -> "HEADLESS-10"
  200ms later:
     connector="eDP-1" model="0x153C" KEY=connector:eDP-1
     connector="HEADLESS-10" model="" KEY=connector:HEADLESS-10
```

At the instant the notification fires, a newly appeared monitor reports
`connector = null`, `model = ""`, `manufacturer = ""` and geometry `0,0,0,0` —
**every monitor appearing in the same event keys identically**. So the first
draft, which keyed on whatever was available, would:

* build one window and silently drop the second monitor when two appeared
  together (the second looked like a key collision); and
* destroy and rebuild that window ~200 ms later, when the real connector landed
  and the key changed under it.

Deferring the reconcile does **not** help — the connector is still null on the
next idle.

The fix has two halves, and both are tested:

* `isIdentified(monitor)` — a monitor with nothing to key it by is not addressed
  yet. It produces no `create` and, importantly, no `destroy` either, so nothing
  is torn down on its account; the window is built **once**, when the identity
  arrives.
* the topology adapter subscribes to `notify::connector` (and
  `notify::geometry`) on every monitor it sees, re-hooking as monitors appear
  (a `WeakSet` guard, so hooking is idempotent and does not retain a removed
  monitor). That notification is what causes the window to be built.

Confirmed by re-running `real-hotplug.sh` after the fix — the log reads
`opened a window for monitor HEADLESS-11` with a real connector, one build each,
no rebuild.

**Its name must not collide** — the concern from the brief dissolves here. Every
window deliberately shares the name `capture-window`, so removing one changes no
name and cannot collide with another. A unique per-monitor name would be the
thing that could collide, and that option is rejected in §4.1.

---

## §2 Gap 2: which window the launcher reaches

### 2.1 The launcher, and why it is not ours to change

`~/.local/bin/capture-ui`, from
`src/provisioning/ansible/roles/cli_tools/templates/capture-ui.j2`:

```sh
if timeout 8 ags toggle "$WINDOW" -i "$INSTANCE" 2>/dev/null; then
```

and `tests/ts/window-identity.test.ts` asserts that line **verbatim**:

```ts
assert.match(
  launcher,
  /ags toggle "\$WINDOW" -i "\$INSTANCE"/,
  "capture-ui.j2 no longer toggles $WINDOW on $INSTANCE",
)
```

So changing the launcher to something that can express "the focused monitor"
means editing that test — weakening an existing assertion. That, plus a provision
run on every host, is why the direction "route the launcher through the
composition root via `ags request`" is rejected in §4.3.

### 2.2 The resolved window is stable, not unstable — and stably wrong

The brief says `get_window` is unstable because "GTK reorders its window list on
map/unmap", and that it measured "B, then A, then B". **That does not reproduce
on this stack.** `repro/probes/launcher-interception-probe.tsx`:

```
=== Q1: GTK's window-list order, and whether get_window EVER moves ===
  added A, B, C -> app.windows: C,B,A
  get_window('capture-window') -> C
  baseline                           order=C,B,A  get_window->C
  after present+show A               order=C,B,A  get_window->C
  after present+show B               order=C,B,A  get_window->C
  after present+show C               order=C,B,A  get_window->C
  after hiding A and B               order=C,B,A  get_window->C
  after destroy C                    order=B,A  get_window->B
  after re-adding C                  order=C,B,A  get_window->C
```

The order is the **reverse of registration** and it does not move on
`present()`, on `visible = true`, on `visible = false`, or on a destroy/re-add.
So there is no ordering instability to restore, and any fix premised on
"stabilise the order" would fix nothing.

The real defect is worse in the way that matters: because every window shares
the name and `get_window` is a `find`, the launcher opens **the last monitor
added, forever**. On a two-monitor host the panel appears on the same screen
every single time and is never on the focused one. GTK's order is also
meaningless as a proxy for focus — it is an artefact of `gtk_application_add_window`
prepending.

`tests/ts/window-identity.test.ts` is left untouched. Its *conclusion* (a name
lookup cannot mean "this window" when duplicates exist) is correct; only its
stated mechanism is off, and its assertions all still hold.

### 2.3 The D-Bus path cannot be intercepted at `toggle_window`

AGS binds the method in its **constructor**, before `main()` runs
(`/usr/share/ags/js/lib/gtk4/app.ts:231-232`):

```ts
this.#dbusService = new AppDBus({
    toggleWindow: this.toggle_window.bind(this),
    ...
})
```

`bind` captures the prototype function's value at that moment, so reassigning
`app.toggle_window` or `App.prototype.toggle_window` afterwards puts a new
function somewhere the D-Bus service is not pointing. Measured with overrides on
**both** the prototype and the instance, then three real external
`ags toggle capture-window` calls:

```
SUMMARY: prototype-toggle hits=0  instance-toggle hits=0
         A=false B=true C=false at the end
  (hits 0 + a window toggled => the D-Bus path bypasses the toggle overrides)
```

Zero hits on both, and a window toggled anyway. Intercepting the toggle is not
available.

### 2.4 What IS available: `get_window`, called through `this`

```ts
get_window(name) {                      // app.ts:156-158
    return this.windows.find((w) => w.name === name)
}
toggle_window(name) {                   // app.ts:164-168
    const win = this.get_window(name)
    ...
}
```

`get_window` was **never bound**. `toggle_window` reaches it as
`this.get_window(name)` — a property lookup performed at call time. So replacing
it *is* on the path the D-Bus call takes. Measured: overrides on both, three
external toggles, and the override on `get_window` moved the resolved window
with the domain's focused monitor every time.

And since every window shares the name, "which window a name lookup reaches" is
decided **entirely** by which candidate comes first. That is the lever, and it is
a list this tool owns.

`installFocusedWindowLookup` therefore:

* filters `windowSet.ordered()` by the requested name (so it never claims a
  window it did not build);
* returns the first — the focused monitor's, else the first in registration
  order;
* **falls back to AGS's own implementation** when no owned window answers, so
  `ags toggle` on any other window keeps working exactly as today;
* is idempotent, so it cannot stack overrides.

Measured end-to-end on the shipped code (`monitor-lifecycle-harness.tsx`, STEP
3 and 6):

```
STEP 3: FOCUS moves to the second monitor; the launcher must now reach it
  app.get_window('capture-window') now resolves to window B
  every window still shares the name: capture-window

STEP 6: REPLUG -> a fresh window is built and is reachable again
  with focus on HDMI-2 the launcher reaches: B
```

`app.windows` itself is **not** touched — it keeps returning GTK's own list
(verified in the Q1/Q3 probes), so nothing that reads it for the truth is misled.

### 2.5 Where "focused" comes from, given that GTK cannot say

The brief's first direction was to derive it from Gdk via
`display.get_monitor_at_window` or `get_default_seat().get_focus()`. Measured:

```
=== 3. CAN GTK NAME THE FOCUSED MONITOR? (no) ===
  Gdk.Seat.get_focus: undefined
  Gdk.Device.get_position: undefined
  Gdk.Display.get_monitor_at_window: undefined
  Gdk.Display.get_monitor_at_point: undefined
  Gdk.Display.get_n_monitors: undefined
  Gdk.Display.get_monitor_at_surface: function
  Gdk.Device.get_surface_at_position: function
  get_surface_at_position() -> [null,0,0]
```

Confirmed against the GIR: `Gdk.Seat`'s complete method list is
`get_capabilities, get_devices, get_display, get_keyboard, get_pointer,
get_tools` — no `get_focus`. GTK4 removed global focus tracking and global
pointer position.

The last row is the near-miss worth recording. `Gdk.Device.get_surface_at_position()`
does exist and its `win_x`/`win_y` are root-window coordinates, which *would*
have given a compositor-agnostic answer via `get_monitor_at_surface`. It returns
`(NULL, 0, 0)` whenever the pointer is over another client's surface — "Returns
NULL if the surface tree under @device is not known to GDK (for example, belongs
to another application)" (`gdkdevice.c:527`), which on a compositor is the normal
case. Cross-checked against `hyprctl -j cursorpos` while the pointer was at
`(884, 1016)`: GDK said `(0, 0)`. Unusable, and worse, silently wrong.

So the answer has to come from the compositor. `AstalHyprland`, measured:

```
Hyprland service loaded: true
get_monitors(): [{"id":0,"name":"eDP-1","focused":true}]
get_focused_monitor(): {"id":0,"name":"eDP-1"}
Gdk connector agrees with hyprland name: eDP-1
```

Both sides publish the same string, which is what `focusKey` matches on.
`AstalHyprland` over `hyprctl` because it is in-process (no spawn and no parse
on a keystroke) and pushes `notify::focused-monitor` (no poll interval to get
wrong) — and because the capture **backend** already defines "focused monitor"
this exact way (`bin/capture-tool:203-205`, `resolve_target`, `hyprctl -j
monitors` → `item.get("focused")`). The panel and the capture now agree: press
SUPER+PRINT on the focused monitor, and `--target screen` grabs that same
monitor.

The import is dynamic and its rejection is swallowed, because
`AstalHyprland` is not present on every Wayland host and a failing *static*
import would take the app down at startup. On a host with no focus source,
`focusedConnector()` returns null and the lookup falls back to registration
order — deterministic, not arbitrary.

### 2.6 The whole thing, end to end, on a real two-monitor layout

`repro/launcher-focus.sh`. This host has one physical monitor, but Hyprland can
create virtual outputs (`hyprctl output create headless`), so a genuine
two-monitor layout exists for the length of the run. The second monitor is
created **before** the app starts, so the app really does have one window per
monitor and the only open question is which one the launcher reaches.

The detector is not pixels. The first attempt was
(`repro/pixel-parity.sh`, kept for the record) and it is unsound: the panel is a
translucent layer-shell surface over live desktop content, so a whole-screen
brightness mean is dominated by whatever is behind it — measured, same script,
same panel, **0.644** for the pre-change build's `eDP-1` against **0.054** for
the post-change build's, a 12× "difference" that is entirely the desktop having
changed between runs. Instead the probe reads `hyprctl layers`, which reports
every layer surface with its **output** and its **namespace**, and
`ClassicWindow` sets `namespace="capture"` on the panel. That is a direct,
content-independent answer.

Same script, same host, focus on `eDP-1`, three real `ags toggle
capture-window` calls each:

```
######## OLD BUILD ########                          ######## NEW BUILD ########
monitors: eDP-1 HEADLESS-17                         monitors: eDP-1 HEADLESS-18

round 1: focused=eDP-1                               round 1: focused=eDP-1
   panel after toggle ON : [HEADLESS-17]                panel after toggle ON : [eDP-1]
   panel after toggle OFF: [<none>]                     panel after toggle OFF: [<none>]
   => does NOT match the focused monitor (eDP-1)        => MATCHES the focused monitor

round 2: focused=eDP-1                               round 2: focused=eDP-1
   panel after toggle ON : [HEADLESS-17]                panel after toggle ON : [eDP-1]
   => does NOT match the focused monitor (eDP-1)        => MATCHES the focused monitor

round 3: focused=eDP-1                               round 3: focused=eDP-1
   panel after toggle ON : [HEADLESS-17]                panel after toggle ON : [eDP-1]
   => does NOT match the focused monitor (eDP-1)        => MATCHES the focused monitor

app log:                                             app log:
  (none)                                             capture: opened a window for monitor eDP-1
                                                     capture: opened a window for monitor HEADLESS-18
                                                     capture: window lookup now prefers the focused monitor's window
```

The pre-change build opens the panel on `HEADLESS-17` — the window it added
last — while the user is on `eDP-1`. The post-change build opens it on `eDP-1`.
The old build's empty log is the same fact as §2.2 from the other side: it
reports nothing because it has no window set to report from.

One direction is not covered by this and is argued elsewhere: focus on the
*second* monitor → panel opens there. `hyprctl dispatch focusmonitor
HEADLESS-N` is a no-op, because a headless output has no input device, so every
run above has focus on `eDP-1`. That direction rests on the `orderedForFocus`
unit tests and `monitor-lifecycle-harness.tsx` STEP 3 / STEP 6.

---

## §3 The shape

```
domain/monitor-registry.ts      PURE. monitorKey, isIdentified, planSync,
                                orderedForFocus, focusKey.
ports/monitor-topology.ts       read the monitors; be told when they change.
ports/monitor-focus.ts          which monitor is the user on. (null is a normal answer.)
adapters/gdk-monitor-topology   items-changed + Monitor::invalidate + notify::connector.
adapters/hyprland-monitor-focus AstalHyprland's focused monitor, or null.
adapters/monitor-window-set      owns the bindings; applies plans; replaces get_window.
app.tsx                         constructs the four and renders. No logic.
```

The hexagon is what makes this change testable at all: `planSync` and
`orderedForFocus` are the entire decision content of both bugs, and they are
pure *because* the adapters hold the `Gdk.Monitor` and the `Astal.Window` while
the domain sees plain data. `node --test` executes them for real; the GTK
surface is four small files whose behaviour is pinned by source inspection and
demonstrated by `repro/`.

`app.tsx`'s own contract is preserved — "NO LOGIC BELOW THIS POINT beyond
'construct the dependencies, then render'". The one-shot loop moved into the
window set, which is where it has to live for a subscription to be able to add
and remove windows.

### Why a registry rather than an index or a name suffix

The brief suggested "tag each window with a stable per-monitor handle in a
domain-owned registry rather than through its GTK `name`". That is what this
does. `WindowBinding<T>` is generic, so the domain never names a `Gtk.Window` —
the registry holds opaque handles and the adapters do the casting. The
registration order lives in an **array**, not a `Map`, because
`orderedForFocus(null)` promises *registration* order and that has to be the
definition rather than an accident of iteration.

---

## §4 Rejected options

### 4.1 Unique per-monitor window names — rejected, and it was already rejected

`name={connector}` or `capture-window-${connector}` would make every lookup
unambiguous and needs no registry.

Rejected: `style.css:29` selects the surface with

```css
window#capture-window
```

which is a GTK **id** selector, which matches the widget **name**, not a class.
Renaming drops `background-color: transparent; color: @color_foreground` onto
nothing and revives a documented first-frame rectangle. It also breaks
`ags toggle capture-window` in `capture-ui.j2`, which needs a provision run.
`fix-capture-window-identity` already rejected this; this change rejects it
again, and
`tests/ts/monitor-registry.test.ts#no adapter renames a window to make it
addressable` pins that it stays rejected.

### 4.2 Derive focus from Gdk — rejected, the APIs do not exist

See §2.5. `get_monitor_at_window`, `get_monitor_at_point`, `get_focus`,
`Device.get_position` all measured `undefined`; `get_surface_at_position`
returns `(NULL, 0, 0)`.

### 4.3 Route the launcher through the composition root (`ags request`) — rejected

`ags request` does reach `app.start({requestHandler})`, which would put the
decision in the composition root where it belongs. Rejected for two reasons, both
decisive:

1. `tests/ts/window-identity.test.ts` pins the launcher's
   `ags toggle "$WINDOW" -i "$INSTANCE"` line exactly. Changing the launcher means
   editing that assertion.
2. `~/.local/bin/capture-ui` is provisioned state. A host that has not re-run
   provisioning keeps the old launcher and keeps the old behaviour — a fix that
   only applies after an operator action. The seam in §2.4 fixes it for every
   existing host at once, with no provision run. This is the same property
   `fix-capture-window-identity` bought and the reason it was worth doing.

It is recorded here as the better *design* and the wrong *deployment*: the
registry in `monitor-window-set.ts` is exactly the thing such a request handler
would consult, so switching the launcher to `ags request` later is a one-line
change with the decision already in place.

### 4.4 Reorder GTK's window list by removing and re-adding the focused window — rejected

No patching, public API only: on a focus change, `remove_window(w)` +
`add_window(w)` moves a window to the head of GTK's list (measured — the
destroy/re-add case above). Tempting, because it needs no override at all.

Rejected because it mutates real application state to achieve a lookup
preference. Every focus change would emit `window-removed` + `window-added` to
anything listening — including AGS's own `window-added` handler
(`app.ts:244-252`), which tears down and re-creates the per-window bookkeeping.
And `app.windows` would then report focus order rather than GTK's truth, which
is the same conflation §2.4's override avoids.

### 4.5 Override the `windows` accessor instead of `get_window` — rejected

Also works (measured). It makes `get_window` correct by construction, without
reimplementing its filter. Rejected as the **broader** monkey-patch: it changes
what every future consumer of `app.windows` sees, including code that wants
GTK's truth. Overriding `get_window` changes the meaning of exactly one
operation — the one whose meaning is wrong — and leaves `app.windows` reporting
what GTK actually holds.

### 4.6 Toggle every monitor's window instead of one — rejected

Compositor-agnostic and needs no focus source at all: press SUPER+PRINT, the
panel opens on every screen. Rejected because it changes the visible behaviour
on multi-monitor hosts in a way nobody asked for, and the ask was specifically
for the **focused** monitor's window. Recorded because it is the right answer if
"which monitor is focused" ever proves unavailable on a target host.

### 4.7 Trust the `items-changed` payload — rejected

Applying `(position, removed, added)` incrementally is the obvious
implementation and it is wrong: the counts describe a range, one event can cover
several changes, and `Monitor::invalidate` can arrive for the same unplug. See
§1.3. Diffing costs one list walk and buys idempotence.

---

## §5 Verification

- `make capture-test` → 144 pass / 0 fail (115 + 29 new).
- `make capture-typecheck` → 0 errors in `src/gui-tools/capture-tool`.
- `python3 scripts/capture-hexagonal-gate.py` → PASS, check 6 at 33 used / 28
  styled (unchanged — nothing was added to or removed from `ui/`, which is what
  check 6 measures).
- Capture `pytest tests/` → 97; `uv run --directory src/provisioning pytest
  tests/unit -q` → 720 passed.
- Runtime, real compositor: `repro/real-hotplug.sh` — window count tracks
  monitor count through add / remove / re-add (§1.5).
- Runtime, real two-monitor layout: `repro/launcher-focus.sh` — the panel opens
  on the focused monitor, and on the wrong one before the change (§2.6).
- `repro/monitor-lifecycle-harness.tsx`, 8 steps, all OK; `repro/probes/` for the
  API facts quoted above.

### What could not be verified on this host

- **Focus on the second monitor.** A Hyprland virtual output has no input
  device, so `dispatch focusmonitor HEADLESS-N` is a no-op and focus stays on
  `eDP-1`. The defect and the fix are both demonstrated *with* focus on `eDP-1`
  (§2.6), but the complementary direction rests on unit tests and the harness.
- **Physical unplug.** Virtual outputs are real compositor events but not real
  connectors; a physical unplug additionally fires `Gdk.Monitor::invalidate`,
  so the dual-hook idempotence is argued from the `items-changed` runs plus
  unit tests rather than from an unplug.
- **Click paths and `btop` behind the panel.** No `ydotool`/`wtype`/`xdotool`,
  and `btop` refuses to start without a TTY this shell cannot provide. Neither
  is touched by this change; the translucency interaction is moot anyway since
  `style.css` and every class are untouched, which check 6 records mechanically.

## §6 Risk

**The override is the real risk.** It depends on `App.get_window` being reached
through `this` at call time. If a future AGS changed `get_window` to call
`this.get_windows()` directly, the override would silently stop mattering and the
behaviour would fall back to exactly today's bug — wrong monitor, not a crash.
That is the good failure direction, and it is why the fallback inside the
override defers to AGS's implementation rather than returning undefined.

**The compositor dependency is new for the GUI.** `AstalHyprland` is a new GI
import in `adapters/hyprland-monitor-focus.ts`. It is confined to one adapter,
loaded dynamically, and its absence degrades to registration order. The hotplug
half of this change is unaffected — it is GDK, and works under any compositor.