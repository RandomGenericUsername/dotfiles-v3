## Why

`app.tsx` builds one `ClassicWindow` per monitor, and each window allocated its OWN
live state:

```ts
const screenshot: ScreenshotUiState = { ...DEFAULT_SCREENSHOT }   // ClassicWindow.tsx:147
const recording: RecordingUiState = { ...DEFAULT_RECORDING }      // ClassicWindow.tsx:148
```

Every window persists that state to the SAME path
(`$XDG_STATE_HOME/capture-tool/capture-ui.json`, `ClassicWindow.tsx:193` and `:215`).
So with two monitors there are two owners of one logical value writing one file, and
the last writer wins: a selection made on one monitor is silently destroyed by the
other monitor's stale copy.

**Reproduced end to end on this machine**, headlessly, with the real
`glibUiStateStore` and two real `Astal.Window` instances (the harness is
`repro/two-window-harness.tsx`; see design.md §Reproduction). Scripted as "window A
picks Screen and captures; window B picks Window and captures; then window A captures
again":

| step | pre-fix persisted `capture-ui.json` | post-fix |
|---|---|---|
| A captures (Screen) | `target: "screen"` | `target: "screen"` |
| B captures (Window) | `target: "window"` — **A's `screen` is gone** | `target: "window"` |
| A captures again | `--target screen`, file flips back to `screen` — **B's `window` is gone** | `--target window`, file unchanged |

The last row is the user-visible symptom in its purest form: the persisted selection
**flaps** depending on which monitor's window you press capture in, and each capture
discards the other monitor's explicit choice. The screenshot that comes out is not the
one the user last chose.

**Reachability, stated honestly.** The divergence needs two *mapped* windows, and the
shipped launcher reaches only one: `capture-ui.j2` runs `ags toggle capture-window`,
which is `App.get_window("capture-window")` → `windows.find(...)` → the LAST-added
window, every time. Verified live — two toggles, and only that one window ever mapped.
So on a two-monitor machine today the user cannot drive this bug through the keybind;
the defect is a latent second writer, one launcher change away from being live. It is
reported here rather than dismissed because the ownership error is unambiguous, it is
already demonstrated, and the fix removes the second owner rather than reasoning about
when the second owner can be reached.

## Root cause

State ownership, not the persistence. `capture-ui.json` and the precedence chain
(last-used UI state > settings defaults > hardcoded constants) are per-APPLICATION:
there is one file, one settings config, one rule. The state object was per-WINDOW. Any
window that had been mapped earlier than the last writer held a copy that was, by
construction, missing every change the other window had saved since — and `save()`
serialises the whole object, so the stale fields overwrite the fresh ones wholesale.

The `Object.assign` in `applyStateToUi()` is **not** the problem and is **not** a
mitigation for this. It is the mitigation for a different hazard, and it is load-bearing:
the three pages were handed the exact objects the window constructed, so a rebind
(`screenshot = state.screenshot`) would orphan every page's later mutations. Keeping it
in place is why one object can safely be shared by every window.

## What Changes

- `domain/ui-state.ts` gains `createUiState(): UiState` — the pure factory that seeds
  one live state from the first-run constants.
- `ClassicWindow(gdkmonitor, ports, state)` takes the state as a **required** third
  parameter and no longer allocates one. There is no longer any code path by which a
  window can come into existence without being told which state it mutates.
- `app.tsx` builds the state once, before the monitor loop, and passes the same object
  to every window.
- A new test file, `tests/ts/ui-state-ownership.test.ts`, pins the factory's semantics
  (fresh objects, not the constants; a factory, not a singleton), the single-object
  property, the modelled negative control, and the wiring in `app.tsx` /
  `ClassicWindow.tsx`.

## Non-goals

- **Not fixing the duplicate window name.** Both windows are called `capture-window`,
  so `hideCaptureWindow()` and `syncWindowSize()` resolve to one of them (measured:
  `get_window("capture-window")` returned the second window, so a capture from the
  first left it on screen and hid the other instead). That is a real, separate
  multi-monitor defect and renaming the windows would be a behaviour change; this
  change leaves it exactly as it is.
- **Not changing persistence.** Same path, same JSON shape, same
  missing-is-silent / corrupt-is-loud degradation, same save-on-capture points.
- **Not changing the three-tier precedence rule**, the `map`-time reload, or the
  class vocabulary (gate check 6 stays at 33 used / 28 styled).
- **Not making reload-on-show authoritative** — see design.md §Alternatives.

## Impact

- `src/gui-tools/capture-tool/domain/ui-state.ts` — one exported factory.
- `src/gui-tools/capture-tool/ui/classic/ClassicWindow.tsx` — one added parameter, one
  deleted allocation, comments.
- `src/gui-tools/capture-tool/app.tsx` — one call to the factory, one extra argument.
- `src/gui-tools/capture-tool/tests/ts/ui-state-ownership.test.ts` — new test file.
- No new deployed file, so gate check 5 (per-file provisioning registration) is
  unaffected and `src/provisioning/**` is untouched.
- Behaviour change: only the second-writer clobber is removed. `capture-test` goes
  85 → 93 (all green), `capture-typecheck` stays at 0 errors in the tool, the
  hexagonal gate stays PASS.
