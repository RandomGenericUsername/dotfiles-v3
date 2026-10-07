# Tasks: refactor-capture-tool-hexagonal

Workstreams map 1:1 to orchestrated agents (A1–A8). **Do not start a workstream
before its dependencies are merged into the working tree.**

Each task states its acceptance as a *command output*, not an opinion. The
invariants that hold across every task:

- `pytest src/gui-tools/capture-tool/tests/` → **94 passed** (never fewer)
- `pytest src/provisioning/tests/unit/test_gui_tools_role.py test_verify_role.py` → **93 passed, 1 pre-existing failure** (`test_settings_parse_gate_tasks_exist_and_are_check_gated`, unrelated to capture — must not be fixed here, must not get worse)
- `python3 scripts/capture-hexagonal-gate.py` → violation count strictly decreasing from a measured baseline of **24**, reaching **0** at A8
- `git diff --stat src/gui-tools/capture-tool/style.css types.ts` → **empty**
- Every load-bearing GTK comment (design.md §4) present at its new home, verbatim

The gate is expected to be RED for most of this change. That is the point — it
bites before it bites you. Do not "fix" it by weakening a check.

---

## A1 — Gate hardening, parity baseline, and dead-scaffolding removal

*depends on: nothing*

- [ ] 1.1 Fix the gate's file walk in check 5 to exclude `.pytest_cache/`,
      `__pycache__/` and any dot-prefixed directory. (Live finding: a bare `pytest`
      run created `.pytest_cache/` in the tool dir and check 5 flagged it.)
- [ ] 1.2 Tighten check 3: the single request→argv translator must live in
      `domain/`. A translator in `ui/` now fails with the reason spelled out.
- [ ] 1.3 Record the parity baseline: `python3 scripts/capture-hexagonal-gate.py
      --update-parity` → `scripts/capture-classic-parity.json`. **Commit it.** From
      here the class vocabulary is frozen.
- [ ] 1.4 Delete the six stubs: `controllers/{Capture,Screenshot,Recording}Controller.ts`,
      `controllers/TargetResolver.ts`, `ui/ScreenshotView.tsx`, `ui/RecordingView.tsx`.
- [ ] 1.5 Remove their 6 placement entries from `gui_tools/vars/main.yml:83–88`.
- [ ] 1.6 Remove their 6 assertions from `verify/vars/main.yml:493–498`. **The
      verify role actively asserts these files exist** — skipping this leaves the
      role failing against a correct tree.
- [ ] 1.7 Remove the pinned file list from
      `provisioning/tests/unit/test_gui_tools_role.py:232–241`.
- [ ] 1.8 Remove the fixtures + presence assertion from
      `provisioning/tests/unit/test_verify_role.py:2311–2317`.
- [ ] 1.9 Add `make capture-hexagonal-gate` to the `Makefile` and include it in
      the `gates` target. **Do not touch `.github/workflows/gates.yml`** — CI is
      out of scope (see design.md §7.1).
- [ ] 1.10 Delete `src/gui-tools/capture-tool/README.md`'s "Planned layout" and
      "Primary architecture" sections — they describe the structure this change
      replaces, and §25 of the project plan described a layout that was never
      built. Replace with a pointer to `design.md`.

**Acceptance:** gate reports **17** violations (from 24: the 6 scaffold violations and
the missing-baseline violation are resolved); capture tests 94; provisioning tests
93+1-pre-existing; `style.css`/`types.ts` untouched.

---

## A2 — Typecheck baseline (local, developer-run)

*depends on: nothing (parallel with A1)*

There is no working CI for this (design.md §7.1), so this gate is developer-run on
a machine that has the desktop stack installed. That is also the only place it is
useful: it is the check that catches a wrong signature *while refactoring*, which
`ags bundle` provably cannot.

- [ ] 2.1 Add a `tsconfig.json` at the capture tool root with the four verified
      settings from design.md §1.2: `skipLibCheck: true`, an `include` that covers
      `@girs/index.d.ts` (without it every `gi://` import is unresolved and JSX
      handler params degrade to implicit `any`, producing ~101 spurious errors),
      `lib: ["ES2022","DOM"]` (gnim uses `String.replaceAll`), and
      `jsxImportSource: "ags/gtk4"`.
- [ ] 2.2 Generate the types once: `ags types -d src/gui-tools/capture-tool -u`.
      Confirm it produces `@girs/`, `env.d.ts`, and `node_modules/{ags,gnim}`
      symlinks into `/usr/share/ags/js`.
- [ ] 2.3 **Gitignore the generated artifacts**: `src/gui-tools/capture-tool/@girs/`,
      `.../node_modules/`, and the generated `tsconfig.json`/`env.d.ts`. They are
      49 MB of machine-specific definitions rebuilt from the installed GTK/Astal;
      they must never be committed, and `node_modules` must never be deployed.
      Commit only a hand-written `tsconfig.capture.json` that the generated one
      extends, so the four settings above are reviewable in the diff.
- [ ] 2.4 Fix the 2 pre-existing errors so the bar is zero:
      `app.tsx:12` — annotate `CaptureWindow`'s return type (it currently infers
      `Object`, which `add_window` rejects); `CaptureWindow.tsx:1013` — replace
      `anchor={0}` with the `Astal.WindowAnchor` enum member. Both are cosmetic
      and pre-existing; neither changes behaviour.
- [ ] 2.5 Add `make capture-types` (runs `ags types`; skips if `@girs/` already
      exists) and `make capture-typecheck` (depends on `capture-types`, runs
      `tsc --noEmit`, and **filters output to `src/gui-tools/capture-tool/`** so
      the 28 errors inside the ags runtime/gnim do not fail the check).
- [ ] 2.6 Add `capture-typecheck` to the `gates` target so one command runs
      everything. Document in the Makefile that `capture-typecheck` requires the
      desktop stack (`ags` + astal installed) and takes ~30s once `@girs/` is
      generated; re-running `capture-types` takes ~2–4 min and needs network.

**Acceptance:** `make capture-typecheck` exits 0 with **zero** errors in our files.

---

## A3 — Domain extraction

*depends on: A2*

- [ ] 3.1 `domain/settings.ts`: `Config*` unions, `CaptureSettings`,
      `DEFAULT_SETTINGS`, allowed-value tuples, `configOneOf`/`configBool`/
      `configString`, `defaultSettings()`, `mergeSettings()`, `validateSettings()`.
      Move with comments verbatim.
- [ ] 3.2 `domain/ui-state.ts`: state interfaces, `DEFAULT_SCREENSHOT`/
      `DEFAULT_RECORDING`, `oneOf`, option tuples, `audioToUi()`, `configDefaults()`,
      and `loadUiState`'s **merge half** only.
- [ ] 3.3 `expandDir()`: inject `(getenv, home)` rather than calling `GLib`
      (design.md §7.2). Pure string manipulation stays in domain.
- [ ] 3.4 `GIF_SIZE_ARG`, `isGif()`, `durationSelection()` → `domain/ui-state.ts`.
- [ ] 3.5 Delete the moved code from `CaptureWindow.tsx`; import it instead.
      **No call-site behaviour change.**
- [ ] 3.6 Register every new file in `gui_tools_app_files`.

**Acceptance:** gate's check 1 green for `domain/`; capture tests 94; typecheck 0.

---

## A4 — Unit tests for the extracted domain

*depends on: A3*

The pure logic is what a move can silently break. It has no direct coverage today.

- [ ] 4.1 Stand up a TS test runner for the capture tool. Keep it minimal and
      offline; `node:test` + `tsx` (or equivalent) avoids a bundler dependency.
- [ ] 4.2 `mergeSettings()`: missing file semantics, corrupt JSON, partial object,
      unknown enum value → fallback, wrong type per field, nested `screenshot`/
      `recording` absent.
- [ ] 4.3 `validateSettings()`: empty dirs, empty pattern, `/` in pattern,
      `\0` in pattern, each valid case.
- [ ] 4.4 `configDefaults()`: the precedence rule (settings → hardcoded) per field.
- [ ] 4.5 `loadUiState` merge: last-used overrides base; out-of-range values fall
      back; `customDuration` clamps to `[5, 3600]` and rounds.
- [ ] 4.6 `audioToUi()`: `mic` → `microphone`, passthrough for `none`/`system`.
- [ ] 4.7 `GIF_SIZE_ARG`: `original`/`75%`/`50%` → `original`/`75`/`50`.

**Acceptance:** these pass, and would fail if `mergeSettings`/`GIF_SIZE_ARG` were
altered — assert that by temporarily breaking one and confirming red.

---

## A5 — Ports and adapters

*depends on: A3*

- [ ] 5.1 `ports/settings-store.ts` — `load()`/`save()`.
- [ ] 5.2 `ports/ui-state-store.ts` — `load()`/`save()`.
- [ ] 5.3 `ports/capture-launcher.ts` — `launch(argv)`.
- [ ] 5.4 `ports/backend-probe.ts` — `backend(): Promise<string>`.
- [ ] 5.5 `adapters/glib-settings-store.ts` — owns `GLib.file_test`,
      `file_get_contents`, `file_set_contents`, `mkdir_with_parents`, and the
      missing-is-silent / corrupt-is-loud degradation. **Comments move with it.**
- [ ] 5.6 `adapters/glib-ui-state-store.ts` — same, for `capture-ui.json`.
- [ ] 5.7 `adapters/exec-capture-launcher.ts` — owns `execAsync` and the 150ms
      `setTimeout` after hiding the window.
- [ ] 5.8 `adapters/exec-backend-probe.ts` — owns `execAsync(["capture-tool","backend"])`
      and its JSON parse with `?? "none"` fallback.
- [ ] 5.9 `CaptureWindow` receives these through parameters. It must no longer
      import `execAsync` or call `GLib.file_*`.

**Acceptance:** gate checks 1 and 2 green; capture tests 94; typecheck 0.

---

## A6 — The request→argv translator

*depends on: A3*

- [ ] 6.1 `domain/capture-request.ts` — `ScreenshotRequest` / `RecordingRequest`.
- [ ] 6.2 `domain/cli-args.ts` — the **single** pure request→argv translator,
      covering screenshot argv (`:554`) and recording argv (`:576`), including
      `--size` for GIF, `--audio` mic conversion (`:575`), and the conditional
      `--cursor` from settings.
- [ ] 6.3 `takeScreenshot()` / `startRecording()` become: build argv via
      `cli-args`, then hand it to the `CaptureLauncher` port.
- [ ] 6.4 Assert the exact argv in A4's tests — including `75` (not `75%`) and
      `mic` (not `microphone`). These are the drift traps this seam exists to kill.

**Acceptance:** gate check 3 green; argv identical to pre-refactor for every
combination; capture tests 94.

---

## A7 — Shared builder kit

*depends on: A2*

- [ ] 7.1 `ui/shared/rows.ts` — `settingsLabel`, `settingsItem`, `settingsGroup`,
      `pathRow`, `toggleRow`, `pillRow`. Move the `Gtk.Switch` rationale comment
      (`:763`) with `toggleRow` — it explains why a hand-rolled knob is wrong.
- [ ] 7.2 `ui/shared/groups.ts` — `select`, `applyGroup`, `clearChildren`.
- [ ] 7.3 `ui/shared/icons.ts` — `captureIcon`, `withIcon`, `IconVariant`. Move
      the `Gtk.Image`/`set_pixel_size` comment (`:217`) — it is a hard-won
      measurement bug.
- [ ] 7.4 Register all three in `gui_tools_app_files`.

**Acceptance:** gate check 6 green (no class token changed); capture tests 94.

---

## A8 — Classic view and composition root

*depends on: A5, A6, A7*

- [ ] 8.1 `ui/classic/ClassicWindow.tsx` — the window shell: `centerbox` +
      `capture-panel`, the mode switch, the capture-phase key controller, the
      `map` handler, and `syncWindowSize()`. **Move the `syncWindowSize` comment
      (`:409–431`) and the `centerbox` comment (`:1034–1040`) verbatim.** These
      are the two most expensive findings in the file.
- [ ] 8.2 `ui/classic/ScreenshotPage.tsx` — the screenshot view as it is.
- [ ] 8.3 `ui/classic/RecordingPage.tsx` — the recording view, including the
      GIF-conditional rows and `applyGifMode()`.
- [ ] 8.4 `ui/classic/SettingsPage.tsx` — the three settings groups.
- [ ] 8.5 `app.tsx` — becomes a composition root: construct adapters, inject into
      the view. No logic.
- [ ] 8.6 Delete `ui/CaptureWindow.tsx` and remove its placement entry.
- [ ] 8.7 Full `make gates` + the two provisioning suites green.

**Acceptance:** **`python3 scripts/capture-hexagonal-gate.py` exits 0**;
`make capture-typecheck` zero errors; capture tests 94; provisioning 93+1-pre-existing;
`git diff` on `style.css` and `types.ts` empty; class vocabulary byte-identical to
`scripts/capture-classic-parity.json`.

---

## A9 — Live verification on a real session (human-in-the-loop, not automatable)

*depends on: A8*

The gate proves structure and vocabulary. It cannot prove the panel still looks
right. Before this change is called done:

- [ ] 9.1 Provision on a live machine and confirm `ags run -d ~/.config/ags-capture`
      re-bundles with no error (a type error is invisible; a module error is not).
- [ ] 9.2 Screenshot both mode views and the settings page; compare against
      `spikes/capture-tool-ui/{screenshot,recording,settings}.html`.
- [ ] 9.3 Exercise: target tiles, GIF-conditional rows, custom-duration spin,
      Enter/Escape hierarchy, the inline path editor in settings, and a real
      screenshot + recording round-trip.
- [ ] 9.4 Confirm `~/.config/capture-tool/config.json` and
      `~/.local/state/capture-tool/capture-ui.json` round-trip identically —
      these are the two files whose format is a backend contract
      (`bin/capture-tool` reads the config on every invocation).

**Acceptance:** operator confirms the panel is visually and behaviourally
indistinguishable from before the change.