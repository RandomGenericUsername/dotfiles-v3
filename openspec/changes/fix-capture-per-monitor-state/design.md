# Design: fix-capture-per-monitor-state

## The ownership question, stated once

There is exactly one of each of these, and none of them is per-monitor:

| thing | cardinality | where |
|---|---|---|
| `$XDG_STATE_HOME/capture-tool/capture-ui.json` | 1 | `adapters/glib-ui-state-store.ts:43` |
| `$XDG_CONFIG_HOME/capture-tool/config.json` | 1 | `adapters/glib-settings-store.ts` |
| the precedence chain (last-used > settings > constants) | 1 | `domain/ui-state.ts:configDefaults` + `mergeUiState` |
| `ClassicWindow` instances | N (one per monitor) | `app.tsx:39-41` |

The state object was the odd one out: it was allocated at cardinality N. So N objects
each claimed to be "the" last-used selections, and each `save()` wrote the whole
object. Any window whose copy predated the most recent save contributed stale fields
over fresh ones. Nothing detected this — the write succeeds, the read succeeds, and
the value that survives is simply whichever window saved last.

The fix moves the object to cardinality 1 and hands the same reference to every window.
Divergence is then not "prevented" or "detected"; it is unrepresentable.

## The change

```ts
// domain/ui-state.ts
export function createUiState(): UiState {
  return {
    screenshot: { ...DEFAULT_SCREENSHOT },
    recording: { ...DEFAULT_RECORDING },
  }
}

// ui/classic/ClassicWindow.tsx
export function ClassicWindow(
  gdkmonitor: Gdk.Monitor,
  ports: CapturePorts,
  state: UiState,
): Astal.Window {
  const { screenshot, recording } = state   // in place, never rebound

// app.tsx
const state = createUiState()
for (const monitor of app.get_monitors()) {
  app.add_window(ClassicWindow(monitor, ports, state))
}
```

Three properties of this shape are deliberate:

- **The state is a required parameter, not an optional one with a default.** A default
  would let a future call site keep the old bug by accident; a required parameter means
  adding a window anywhere forces the author to decide which state it mutates.
- **`createUiState()` is a factory, not a memoised singleton, and not a module-level
  constant.** `buildPorts()` right above it is a factory for exactly the same reason
  (`app.tsx:14-22`): the sharing is the composition root's decision, made once, in one
  visible place, and swap-able by a test or a second entry point. A hidden module-level
  cache would make every window share by accident — invisible at the call site, and
  impossible to give a test its own state.
- **It lives in `domain/`, so no new file and no provisioning change.** Gate check 5
  requires every deployed file to be registered per-file in `gui_tools_app_files`; adding
  a module would have meant editing `src/provisioning/**`, which is out of scope for this
  worktree. `domain/ui-state.ts` is already registered and already owns
  `DEFAULT_SCREENSHOT` / `DEFAULT_RECORDING`.

## Why `Object.assign` stays

The comment at `ClassicWindow.tsx:143-148` records a real hazard: the three pages hold
the exact objects they were constructed with, so `screenshot = state.screenshot` inside
`applyStateToUi()` would leave every page mutating an object the window had already
replaced — silent, and invisible until a setting stopped sticking. `Object.assign`
keeps identity stable across the map-time reload, which is the same property that makes
one shared object safe for N windows. The mitigation and the fix reinforce each other;
neither replaces the other.

## Alternatives considered

**(a) A shared store — make `uiStateStore` own the live state and hand it out.**
Rejected: it changes a port contract whose whole point is that it is a *file*
(`UiStateStore.load/save`, "missing is silent, corrupt is loud"), and it would push the
live object behind the port boundary so the pages could no longer be handed a plain
object they mutate. It also duplicates the factory idea inside an adapter that is
supposed to know nothing about liveness. Strictly more machinery for the same
cardinality-1 outcome.

**(b) Per-monitor state files.** Rejected: it makes the persisted selections
per-monitor, which contradicts the documented precedence chain (one last-used value for
the app, the footer literally says "Remembers your last choices"), changes the on-disk
contract and the missing/corrupt degradation for N files, and would make the value flap
*by design* when the user moves a window between monitors. It would also require
`settingsStore`/`configDefaults` to be consulted per file — a behaviour change well
beyond this bug.

**(c) Make reload-on-show authoritative — drop each window's copy and re-read on every
`map`, saving from the freshly loaded value.** Rejected: it is already half-implemented
(the `map` handler reloads), and it is *not* the defect. A stale copy is only dangerous
because it is written back; but two windows mapped at once would still each hold their
own loaded snapshot, and `Object.assign` into per-window objects is precisely what
preserves the identity the pages depend on. It reduces the window but does not close the
window.

**(d) Shared injected object (chosen).** One object, one owner set of mutations, no port
or on-disk change, no view change, identity preserved.

### Honest limitation of (d)

With one shared object and two windows mapped simultaneously, the *objects* converge
immediately but the *CSS highlight* of a window that is not being interacted with can
lag: `applyStateToUi()` also re-selects button groups, and each window only re-runs
that on its own `map`. So a window that was left mapped shows the previous selection
highlight while the shared state has moved on.

This is the right way round. What matters is what a capture *does*: `takeScreenshot()`
reads `screenshot.target` from the shared object, so it captures the current truth, and
the value written to disk is the truth. Pre-fix, the same situation produced a persisted
value that was wrong. Verified in the harness — step 7 below. The highlight re-syncs on
that window's next `map`, which is the pre-existing behaviour for any change made while
a window was hidden.

## Reproduction

This host has one monitor (`hyprctl monitors` lists `eDP-1` only), so the divergence was
reproduced by constructing the two-window instance programmatically, headlessly, against
the REAL `glibUiStateStore` — no stubbed persistence, no faked selection state:

```
openspec/changes/fix-capture-per-monitor-state/repro/two-window-harness.tsx
```

Copy the tool plus the harness into a scratch dir, point `XDG_STATE_HOME`/`XDG_CONFIG_HOME`
at throwaway paths, and run `ags run -d <dir>`. The harness builds
`ClassicWindow(monitor, ports)` twice (pre-fix) or `ClassicWindow(monitor, ports, state)`
twice with one state (post-fix), then scripts: show A, show B, A picks Screen and
captures, re-show A, B picks Window and captures, re-show A, A captures.

Decisive rows, real output:

```
STEP 3: on window A pick Screen, then capture
   launcher argv: ["capture-tool","screenshot","--target","screen",...]
   state file after A capture: {"screenshot":{"target":"screen",...}}
STEP 5: on window B pick Window, then capture
   state file after B capture: {"screenshot":{"target":"window",...}}     <- A's screen gone
STEP 7: press capture on window A
   launcher argv: ["capture-tool","screenshot","--target","screen",...]   <- pre-fix
   state file after A capture: {"screenshot":{"target":"screen",...}}     <- B's window gone

   ...same script, post-fix, STEP 7:
   launcher argv: ["capture-tool","screenshot","--target","window",...]   <- current truth
   state file after A capture: {"screenshot":{"target":"window",...}}     <- nothing flips
```

### Reachability of the pre-fix clobber, measured

The pre-fix defect is a **latent** second writer, not a live keybind bug, and the reason
is the duplicate window name rather than anything about the state:

- `capture-ui.j2` (the provisioned launcher) runs `ags toggle capture-window`.
- `ags`' `App.toggle_window(name)` is `this.windows.find((w) => w.name === name)`
  (`/usr/share/ags/js/lib/gtk4/app.ts:156-168`) — the LAST-added window, every time.
- Live check with two windows constructed: `ags toggle capture-window` twice produced
  `map B`, `B.visible = true`, `B.visible = false` — window A never mapped, so it never
  reloaded, never mutated and never saved.

So a two-monitor user cannot reach the clobber through the shipped keybind today. Two
things make the fix still the right call: the second writer is real and demonstrable,
and the duplicate name is exactly the kind of thing that gets fixed next (per-monitor
show on the focused monitor), at which point this becomes a live data-loss bug with no
further code change required to trigger it. Fixing the name is a behaviour change and is
explicitly out of scope here.

## Testing, and what it does NOT prove

`ClassicWindow` is a `.tsx` importing `ags/gtk4` and `gi://GLib`. `node --test` has no
GTK and no display, so a test cannot construct one, and a test that claims to is the
"test that proves nothing" this change is supposed to avoid. What is reachable, and what
`tests/ts/ui-state-ownership.test.ts` therefore pins:

1. **The real factory, executed** — seeds the defaults; hands out objects that are not
   the `DEFAULT_*` constants (mutating a state cannot corrupt the first-run defaults);
   two calls return two independent object graphs (the sharing is the composition root's
   decision, not a hidden singleton).
2. **The invariant, on identity** — two windows given one state mutate one object, and
   the second save cannot resurrect a stale value.
3. **The negative control** — the same test file models the OLD shape (a per-window
   `{ ...DEFAULT_SCREENSHOT }`) and asserts it DOES diverge and DOES lose the other
   window's selection. The bug is executable in the suite, not just described.
4. **The wiring, read from the real sources** (comment lines stripped, so a rationale
   that names `createUiState()` cannot satisfy the assertion): `ClassicWindow.tsx`
   allocates no state and declares `state: UiState`; `app.tsx` calls `createUiState()`
   exactly once, outside the monitor loop, and passes it at the single `ClassicWindow`
   call site.

(4) is a source-shape guard, not an execution of the window, and is weaker than a GTK
test would be. It is still the assertion that fails first if a per-window copy is
re-introduced, which is the entire failure mode. The end-to-end proof is the harness
above; it is kept in the change directory rather than in `tests/` because it needs a
live AGS session and would be a lie as a CI test.

## Risk

Low. The change is one allocation moved and one parameter added. The single-window case
— every configuration that exists today, since only one window is ever reachable — is
behaviourally identical: one window, one state, the same mutations, the same saves at
the same two call sites, the same reload on `map`. The multi-window case loses a
data-loss path and gains, at worst, a highlight that re-syncs on the window's next map.
