## 0. Anti-drift preamble (read before editing)

- Files in scope: `src/gui-tools/capture-tool/ui/classic/ClassicWindow.tsx`,
  `src/gui-tools/capture-tool/tests/ts/window-identity.test.ts` (new),
  and this change directory.
- NO new deployed file → gate check 5 (`gui_tools_app_files` per-file
  registration) untouched; `src/provisioning/**` is NOT edited. **This is a hard
  constraint of the change**, not an accident: editing `capture-ui.j2` would
  require a provision run to reach the operator's machine.
- Invariants that hold: `ClassicWindow`'s three-parameter signature unchanged;
  `WINDOW_NAME` and `name="capture-window"` unchanged; `style.css` unchanged;
  the class vocabulary unchanged (gate check 6 stays 33 used / 28 styled);
  `app.tsx` unchanged; persistence path, JSON shape and degradation rules
  unchanged.
- Do NOT weaken the hexagonal gate or any test.
- If a step forces a file outside this list, STOP and report.

## 1. Establish intent before changing anything

- [x] 1.1 Read the window's own construction: `gdkmonitor={gdkmonitor}` plus
      `halign/valign={Gtk.Align.CENTER}` and `anchor=NONE`. Consistent with
      "centre the panel on the monitor this window was built for", but a
      per-monitor window is not the only design that centres a panel — a single
      window on the focused monitor centres identically. The alignment supports
      per-monitor windows; it does not establish them.
- [x] 1.2 Read the project plan (`docs/Hyprland Screenshot & Screen Recording
      Tool — Full Project Plan.md`). §48 "Visual Behavior" says the UI should
      "float above the desktop" and "be centered or positioned according to the
      desired shell behavior" — one panel, positioned. §47 Phase 9 lists exactly
      one `CaptureWindow`. The plan's every mention of "multiple monitors"
      (lines 1536, 1564, 2016, 2184) is about **capture geometry**, never about
      the panel appearing once per monitor. **No statement in the plan about
      per-monitor UI.**
- [x] 1.3 Read `add-capture-ui-restyle/` and `add-capture-settings/` specs and
      `spikes/capture-tool-ui/`: the only hits for "monitor" are the `monitor`
      icon variant for the Screen target tile. `spikes/capture-tool-ui/` has no
      multi-monitor mockup at all. **No evidence there either.**
- [x] 1.4 `git log -p` on the construction. The loop arrives whole in
      `0f21f212` ("feat: add AGS capture tool UI and recording flow"), the
      FIRST commit that introduces the capture UI — and in the same hunk it
      introduces `name="capture-window"` **and** `app.get_window("capture-window")`
      as a module-level helper. The per-monitor loop is not a later decision
      layered onto a single window; it is how the window was born. No commit
      message, openspec entry, or comment states a rationale. The message of
      `0f21f212` is two lines and says nothing about monitors.
- [x] 1.5 **Verdict: the evidence does not settle intent.** There is no artifact
      anywhere in the repo that says one-window-per-monitor is deliberate, and
      none that says it is accidental. The only positive evidence is structural:
      the loop was written simultaneously with the name and the lookup, and the
      identical pattern was then copied to `hypr-pano`
      (`src/gui-tools/hypr-pano/app.tsx:12-13`, `ui/PanoWindow.tsx:27,30`),
      which suggests a house pattern rather than a considered decision about
      this tool. Reported as absent, not guessed at.

## 2. Measure on this host

- [x] 2.1 Established the host has ONE monitor (`hyprctl monitors` → `eDP-1`
      only), so no live two-monitor run is possible. Recorded, not glossed.
- [x] 2.2 Built the two-window harness from the real tree
      (`openspec/changes/fix-capture-per-monitor-state/repro/` pattern): two real
      `ClassicWindow`s on this host's monitor, only `launcher` and `backendProbe`
      stubbed, `XDG_STATE_HOME`/`XDG_CONFIG_HOME` pointed at scratch dirs.
- [x] 2.3 Measured the name lookup: `app.windows` is `B,A` on a fresh instance
      (both windows never mapped) and `A,B` after window A had mapped and
      unmapped; `get_window("capture-window")` follows it, because `find` returns
      the first element. **This corrects
      `fix-capture-per-monitor-state/design.md:160-163`**, which claims the
      target is always the last-added window; the target is not stable.
- [x] 2.4 Reproduced the reported symptom with both windows visible and the
      capture button pressed on A: `A=true B=false` afterwards — A stayed
      visible, B was hidden. Confirmed, not taken on trust.
- [x] 2.5 Confirmed `syncWindowSize()` is affected the same way: with the lookup
      resolving to the other window, the view switch on A resized A in one
      ordering and left it at the old height in another, because which window it
      hit depended on map history.
- [x] 2.6 Grepped the whole repo for `capture-window`: three live consumers
      (`ClassicWindow.tsx`, `style.css:29`, `capture-ui.j2:18`) plus
      `keybindings.lua` (calls `capture-ui`, name-agnostic), `verify/vars/main.yml`
      (asserts the launcher FILE exists, not its contents) and gate check 6's
      parity baseline (carries `capture-window` via the CSS class, not the name).
      **Nothing else.**
- [x] 2.7 Ran the shipped launcher command against a two-window instance:
      `ags toggle capture-window -i capture-wid4` mapped **one** window (B), and
      the other never mapped. So the keybind shows exactly one panel, and the
      defect fixed here is not reachable through it today.

## 3. The fix

- [x] 3.1 `ClassicWindow.tsx`: declare `let captureWindow: Astal.Window | null =
      null` **inside the factory**, with `hideCaptureWindow()` and
      `syncWindowSize()` moved inside with it, and both rewritten against that
      reference.
- [x] 3.2 Assign `captureWindow = self` in the `<window>` `$` handler, whose
      comment records why gnim runs it late enough for the construction-time
      `syncWindowSize()` call to no-op exactly as before.
- [x] 3.3 Drop `import app from "ags/gtk4/app"` — the view no longer touches the
      global registry.
- [x] 3.4 Keep `WINDOW_NAME` and `name="capture-window"`, with a comment
      recording the two out-of-process consumers and that the name is no longer an
      internal identifier.
- [x] 3.5 **Caught and fixed a defect in the fix**: the first attempt declared
      `captureWindow` at module scope. Measured result was identical to the
      pre-fix control (`A=true B=false`) — the second construction overwrites the
      first window's reference. Moved into the closure and re-measured:
      `A=false B=true`. Recorded in design.md §"The bug I wrote first".

## 4. Tests

- [x] 4.1 `tests/ts/window-identity.test.ts`: AGS lookup semantics executed
      against a controlled order — the old name-scoped hide hides the wrong
      window at order `[b,a]` and is correct at `[a,b]` (both measured), the new
      self-scoped hide is correct at every order tried.
- [x] 4.2 Source-shape guards: no `app.get_window(`, no AGS app import,
      `captureWindow = self` present, declaration **after**
      `export function ClassicWindow(` and appearing exactly once.
- [x] 4.3 Cross-file name contract: window `name`, `style.css`'s
      `window#capture-window`, and `capture-ui.j2`'s `WINDOW=` must agree; the
      launcher must still toggle `$WINDOW` on `$INSTANCE`.
- [x] 4.4 Negative-tested every new assertion by reintroducing what it guards:
      name lookup reintroduced → 1 failure; module-scope declaration → 1
      failure; rename missing the launcher → 2 failures; `captureWindow = self`
      deleted → 1 failure; stray second declaration → 1 failure. All restored
      afterwards, and the restored file was diffed against the
      harness-verified copy before running the final gates.

## 5. Gates

- [x] 5.1 `python3 scripts/capture-hexagonal-gate.py` → PASS, check 6 exactly
      `33 used / 28 styled`.
- [x] 5.2 `make capture-typecheck` → 0 errors.
- [x] 5.3 `make capture-test` → 111 pass (was 103; +8 new).
- [x] 5.4 capture `pytest tests/` → 97 passed, unchanged.
- [x] 5.5 `uv run --directory src/provisioning pytest tests/unit -q` → the same 4
      pre-existing failures; nothing under `src/provisioning/**` was touched.

## 6. Deliberately NOT done

- [ ] 6.1 Per-monitor unique window names. Needs `style.css` **and**
      `capture-ui.j2`, and `capture-ui.j2` is provisioned — needs a provision run.
      Costs a stylesheet regression if missed (the window stops being
      transparent) and a dead `SUPER+PRINT` if missed. **Operator's decision.**
- [ ] 6.2 "Open the panel on the focused monitor." Same provisioning
      dependency; a real gap, recorded in proposal.md Non-goals.
- [ ] 6.3 Monitor hotplug. `app.tsx` reads `get_monitors()` once in `main()` and
      registers no monitor-changed handler, so a monitor attached after login
      gets no window. Pre-existing, orthogonal, unaddressed here.
- [ ] 6.4 The same defect in `hypr-pano` (`PanoWindow.tsx:30` does the identical
      name-scoped `get_window`; `hypr-pano-ui.j2` toggles it). Leaving capture
      fixed and its sibling not is a known inconsistency, deliberately not
      bundled into this change.