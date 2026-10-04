# Design: refactor-capture-tool-hexagonal

Behavior-preserving restructure of the capture GUI into hexagonal layers, ratified
against `openspec/specs/oci-strict-hexagonal-layering/spec.md` (the repo's existing
enforced convention, which this change extends to a second module).

Everything in "Measured baseline" and "Seam inventory" was verified on this branch
against the live toolchain, not inferred from reading code.

---

## 1. Measured baseline

The acceptance floor for every task in this change.

| Probe | Result |
|---|---|
| `pytest src/gui-tools/capture-tool/tests/` | **94 passed** |
| `pytest tests/unit/test_gui_tools_role.py tests/unit/test_verify_role.py` | **93 passed, 1 failed** — `test_settings_parse_gate_tasks_exist_and_are_check_gated`, a pre-existing Hyprland-IPC assertion **unrelated to capture**. Must not be fixed here; must not get worse. |
| `scripts/capture-hexagonal-gate.py` | **24 violations** — 14 adapter-ownership, 6 dead-scaffold, 3 layering, 1 missing parity baseline |
| `tsc --noEmit` over the capture tool | **2 errors in our files**, 28 in `/usr/share/ags/js/**` (third-party) |

### 1.1 AGS does not type check — verified

```
const bad: number = "this is a string, not a number"
function alsoBad(a: string): void { return 42 }
```
`ags bundle` → **exit 0**, emits `var bad = "this is a string"` and
`function alsoBad() { return 42 }`. Annotations are stripped, not checked.

A missing module **is** caught (`Could not resolve "./nonexistent"`, exit 1). So
file moves are safe-ish; type and signature changes are invisible until runtime.

### 1.2 A typecheck gate is nevertheless feasible — verified end to end

`ags types -d <dir> -u` generates `@girs/` (168 `.d.ts` files), an `env.d.ts`, a
`tsconfig.json`, and symlinks `node_modules/{ags,gnim}` into `/usr/share/ags/js`.

Four adjustments are required, each verified necessary:

| Setting | Why |
|---|---|
| `"skipLibCheck": true` | 47 errors from duplicate GTK3/GTK4 identifiers inside the generated `@girs` declarations |
| `"include": [..., "@girs/index.d.ts"]` | `@girs` *declares* the `gi://GLib?version=2.0` modules; without it, `gi://` imports are unresolved and the JSX handler params degrade to implicit `any` (101 spurious errors) |
| `"lib": ["ES2022", "DOM"]` | gnim uses `String.replaceAll` |
| filter to our files | 28 errors remain in the ags runtime itself; tolerate by location, exactly as `wifi-mock-parity.py` uses its `ALLOWLIST`/`KNOWN_GAPS` |

With these, our code is **2 errors from clean**:

- `app.tsx:12` — `add_window(CaptureWindow(monitor))`: `CaptureWindow` returns `Object`, not `Window`. Fixed by an explicit return type annotation.
- `CaptureWindow.tsx:1013` — `anchor={0}`: `anchor` is the `Astal.WindowAnchor` enum; the numeric literal is not assignable. Works at runtime; fixed by using the enum member.

**Both are pre-existing and cosmetic.** They are fixed in task 2 precisely so the
gate has a zero-error bar to hold the refactor to.

**Cost of the generated types:** 168 files, **49 MB** — or 17 files / 12.5 MB for
just the transitive closure the capture tool needs (the `@girs` files chain through
`/// <reference>`, so a subset cannot be taken). They are descriptions of the GTK and
Astal libraries *installed on the machine that ran the command*, rebuilt from
scratch whenever a library version bumps. Committed, they would be 12.5–49 MB of
generated machine-specific definitions in a dotfiles repo. They are gitignored and
regenerated on demand instead.

**Cost per run:** generation takes ~2–4 minutes and needs network (it pulls
`ts-for-gir` via npx). Typechecking itself is seconds. Hence `make capture-types`
skips generation when `@girs/` already exists — the definitions only change when the
system's libraries do, which is rare.

---

## 2. Target structure

```
src/gui-tools/capture-tool/
├── app.tsx                  # composition root ONLY: build adapters → inject into ports
├── style.css                # UNCHANGED
├── types.ts                 # UNCHANGED
├── domain/                  # pure. no ags/*, no gi://*, no execAsync.
│   ├── settings.ts          # CaptureSettings, defaults, mergeSettings, validateSettings
│   ├── ui-state.ts          # ScreenshotUiState, RecordingUiState, defaults, merge
│   ├── capture-request.ts   # ScreenshotRequest | RecordingRequest value objects
│   └── cli-args.ts          # ★ the engine-reuse seam: request → string[]
├── ports/                   # interfaces only. no concrete class, no I/O.
│   ├── settings-store.ts
│   ├── ui-state-store.ts
│   ├── capture-launcher.ts
│   └── backend-probe.ts
├── adapters/                # all I/O lives here.
│   ├── glib-settings-store.ts
│   ├── glib-ui-state-store.ts
│   ├── exec-capture-launcher.ts
│   └── exec-backend-probe.ts
└── ui/
    ├── shared/              # layout-agnostic builder kit, reused by any future layout
    │   ├── rows.ts          # settingsLabel/Item/Group, pathRow, toggleRow, pillRow
    │   ├── groups.ts        # select, applyGroup, clearChildren
    │   └── icons.ts         # captureIcon, withIcon
    └── classic/             # today's view. no logic moves out of behaviour.
        ├── ClassicWindow.tsx
        ├── ScreenshotPage.tsx
        ├── RecordingPage.tsx
        └── SettingsPage.tsx
```

### 2.1 Conformance to `oci-strict-hexagonal-layering`

| OCI rule | Capture-tool expression |
|---|---|
| adapters MAY import adapters; MUST NOT import factory | `adapters/` never imports `app.tsx` |
| domain stdlib allowlist / banned list | TS equivalent: `domain/` imports nothing from `ags/*` or `gi://*` (checked by gate) |
| no FS-method calls in domain | `domain/` calls no `GLib.file_*` / `mkdir_with_parents` |
| ports are ABCs or typed aggregates only | `ports/` declares only `interface`/abstract types; a concrete class there fails the gate |
| shared base classes deleted, not relocated | the six stubs are **deleted**, not moved into `ports/` |

The name `CaptureController` is **not** reused in TypeScript: the Python runtime
already owns a live `runtime.application.capture.CaptureController` with its own
test suite. Same name, different language, no import path in common — reusing it
would send the next reader hunting for a link that does not exist.

---

## 3. Seam inventory

Line references are pre-refactor `ui/CaptureWindow.tsx`.

### 3.1 Pure domain — move as-is

| Lines | Symbol |
|---|---|
| 31–81 | `Config*` unions, `CaptureSettings`, `DEFAULT_SETTINGS`, allowed-value tuples |
| 83–102 | `configOneOf`, `configBool`, `configString`, `defaultSettings()` |
| 104–135 | `mergeSettings()` — corrupt-tolerant; highest-value, fully testable |
| 165–178 | `validateSettings()` |
| 251–304 | UI state interfaces, `DEFAULT_*`, `oneOf`, option tuples |
| 307–309 | `audioToUi()` — the `mic` ↔ `microphone` bridge |
| 311–332 | `configDefaults()` — the settings→defaults precedence rule |
| 334–382 | `loadUiState`'s merge half (pure once the read at 344–345 is lifted) |
| 396–400 | `GIF_SIZE_ARG` — the `"75"` not `"75%"` map |
| 498–518 | `isGif()`, `durationSelection()` |

### 3.2 Pure but needs an injected environment

| Lines | Symbol | Blocker |
|---|---|---|
| 151–163 | `expandDir()` | calls `GLib.getenv` / `GLib.get_home_dir`. Takes a `(getenv, home)` pair instead, or moves to an adapter. **Decision deferred to task 4** — `settings.ts` taking an env resolver is the lower-friction option, since `expandDir` is pure string manipulation once the two lookups are passed in. |

### 3.3 The argv seam — highest-value extraction

| Lines | Symbol |
|---|---|
| 554–567 | screenshot argv |
| 575 | `audioFlag` mic conversion |
| 576–593 | recording argv + `GIF_SIZE_ARG` lookup |

Today argv construction is interleaved with `execAsync`. Splitting **build** (pure,
`domain/cli-args.ts`) from **spawn** (`adapters/exec-capture-launcher.ts`) is the
single change that makes engine reuse real. These ~35 lines carry both vocabulary
traps and are exactly what a hand-built second layout would get wrong.

### 3.4 I/O → adapters

`58–61`, `138–149`, `180–195` (settings) · `246–249`, `384–391` (UI state) ·
`404–406` (window hide, app bus) · `551–570`, `572–596` (capture actions) ·
`818–835` (backend probe)

### 3.5 GTK construction → `ui/`

`198–240` (icons) · `424–431` (`syncWindowSize`) · `433–1865` (component) ·
`666–807` (settings builder kit) · `809–816` (`clearChildren`)

### 3.6 Reusable builder kit → `ui/shared/`

`settingsLabel` · `settingsItem` · `settingsGroup` · `pathRow` · `toggleRow` ·
`pillRow` (`666–807`) · `select`/`applyGroup` (`486–496`) · `clearChildren` (`809`) ·
`captureIcon`/`withIcon` (`215–240`)

These are already generic and already callback-shaped. Extracting them **now**,
pre-refactor, is what stops a future layout from growing its own divergent row
builders.

---

## 4. Load-bearing GTK constraints — carry across verbatim

These comment blocks are empirical findings from live debugging. Relocating them is
an explicit acceptance criterion; treating them as decoration is not acceptable.

| Line | Constraint |
|---|---|
| 22–28 | The window paints nothing. Chrome lives on the child, or the first frame flashes an unclipped rectangle during the surface's show/resize transition. |
| 36–48 | No box-shadow. The surface is sized to the panel, so a shadow extends past it and is clipped square. The border carries the edge. |
| 217–222 | `Gtk.Image` + `set_pixel_size`. **`Gtk.Picture` + `set_size_request` is not equivalent** — the request is only a minimum and the 1024px SVG natural size still drives measurement, inflating every tile. |
| 409–431 | `syncWindowSize()` is deliberately **synchronous**. GTK never shrinks a layer-shell surface when content shrinks; deferring the resize made GTK paint an intermediate frame with new content inside the old surface, and the clipped shadow read as a rectangle trailing the window. |
| 763–767 | `Gtk.Switch`, not a hand-rolled track+knob. A `GtkBox` ignores a child's main-axis alignment, so the knob's `halign` never moved it and both states looked identical. |
| 1034–1040 | `centerbox`, not `box`. A `GtkBox` ignores a child's main-axis alignment, so the panel stretched to a stale surface size and painted below its content. |

---

## 5. The gates

### 5.1 `scripts/capture-hexagonal-gate.py`

Follows the docstring-and-checks precedent of
`scripts/speedtest-no-new-architecture.py` ("reuse the existing architecture is
otherwise unenforceable prose").

| # | Check | Fails today? |
|---|---|---|
| 1 | `domain/` and `ports/` import no `ags/*`, no `gi://*` | yes (no such dirs) |
| 2 | Only `adapters/` and the composition root call `execAsync` / `GLib.file_*` / `GLib.mkdir_with_parents` | yes (14 sites in `ui/`) |
| 3 | **Exactly one** request→argv translator, and it lives in `domain/` | no, but it is currently a `ui/` file; the location clause is what makes the seam real |
| 4 | The six dead stubs are absent | yes (6 files) |
| 5 | Every capture file is in `gui_tools_app_files`, and no entry is stale | currently noisy — needs the cache filter (§7) |
| 6 | Class-vocabulary parity against `scripts/capture-classic-parity.json` | baseline must be recorded |

Check 6 snapshots **sets**, it does not adjudicate semantics: `capture-window`,
`capture-root`, `settings` and `settings-group` are styled via
`window#capture-window` / `centerbox` selectors or not at all, and `settings-name`/
`settings-desc`/`settings-group-title` are passed as *variables* to
`settingsLabel()`. A semantic checker would flag six false positives; a set
snapshot does not.

### 5.2 Typecheck gate

`tsc --noEmit` scoped to `src/gui-tools/capture-tool/**`, tolerating the 28
third-party errors under `/usr/share/ags/js/**`. Zero tolerance for our files.

---

## 6. Provisioning coupling for the deletion

The stub removal is four coupled edits, not one. Verified:

| Site | Edit |
|---|---|
| `gui_tools/vars/main.yml:83–88` | remove 6 placement entries |
| `verify/vars/main.yml:493–498` | remove 6 assertions — **the verify role actively asserts these files exist** |
| `provisioning/tests/unit/test_gui_tools_role.py:232–241` | remove the pinned file list |
| `provisioning/tests/unit/test_verify_role.py:2311–2317` | remove the fixtures and the presence assertion |

Nothing imports the stubs, so the deletion is safe — but it is *load-bearing in
provisioning* and must land with its wiring.

---

## 7. Decisions

1. **CI is out of scope — the gates are developer-run.** `.github/workflows/gates.yml`
   triggers on `push: branches: [main]`, but this repository's default branch is
   `master` and `main` does not exist on the remote. The push trigger therefore
   cannot fire, and the last pull-request-triggered run was 2026-06-17 — the workflow
   file itself was last modified 2026-09-30. No task in this change touches CI.

   Consequence: both gates are `make` targets, run by the human or the agent doing
   the work, on a machine that has the desktop stack. That is also where they are
   most useful — the typecheck exists to catch a wrong signature *during* the move,
   which is exactly when it is run. Repairing the CI trigger is a separate change the
   owner has deferred.

   Worth recording as a standing observation, not a task here: this repository's
   gates are written as "executable prose" on the premise that *something runs them*
   (`scripts/speedtest-no-new-architecture.py`: "reuse the existing architecture is
   otherwise unenforceable prose"). That premise currently does not hold.

2. **`expandDir`'s home: inject an env resolver into `domain/settings.ts`.** The
   logic is pure string manipulation once `getenv`/`home` are parameters, so it
   belongs in domain rather than in an adapter.

3. **Gate 5's file walk must exclude `.pytest_cache/` and other dot-prefixed
   directories.** Observed live: a bare `pytest` run created `.pytest_cache/` inside
   the tool dir and check 5 flagged it. (`.gitignore` covers `__pycache__/` but not
   `.pytest_cache/` — a separate papercut, out of scope here.)

4. **Gate 5 does not cross-check `verify/vars/main.yml`.** Its assertions are absolute
   spine paths rather than repo-relative sources, so gate 5 cannot see them, and the
   deletion task must edit both by hand. Adding the cross-check is a follow-up.

---

## 8. Out of scope

The alternate layout. The layout-switch setting and its instance restart. Any new
engine or CLI capability. `bin/capture-tool`, the runtime, and the bar widget are
untouched. `style.css` and `types.ts` are unchanged — check 6 enforces it.