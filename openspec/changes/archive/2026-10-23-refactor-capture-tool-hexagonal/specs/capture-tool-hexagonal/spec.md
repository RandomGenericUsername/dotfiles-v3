## Purpose

Mechanical guarantees that the capture tool's GUI is layered hexagonally, that its
capture engine is shared through exactly one pure request→argv translator, and that
the refactor is behaviour-preserving. Ratified against the repo's existing
`oci-strict-hexagonal-layering` convention, extended to a second module.

## ADDED Requirements

### Requirement: The pure layers SHALL import no toolkit

`domain/` and `ports/` under `src/gui-tools/capture-tool/` SHALL contain no import
of `ags/*` (GTK bindings, `ags/gtk4/app`, `ags/process`) and no `gi://*`
(GLib/Gio). `scripts/capture-hexagonal-gate.py` check 1 enforces this. The layer
directories SHALL exist and SHALL be non-empty.

#### Scenario: Domain module importing GLib fails the gate
- **WHEN** `domain/settings.ts` contains `import GLib from "gi://GLib?version=2.0"`
- **THEN** the gate fails with `pure layer imports 'gi://GLib?version=2.0' -- no GTK/GLib/ags/* in domain/`

#### Scenario: Ports module importing the process module fails the gate
- **WHEN** `ports/capture-launcher.ts` contains `import { execAsync } from "ags/process"`
- **THEN** the gate fails with the same rule, naming `ports/`

#### Scenario: Missing layer directory fails the gate
- **WHEN** `src/gui-tools/capture-tool/domain/` does not exist
- **THEN** the gate fails with `missing layer directories: domain ... -- the refactor has not been performed yet`

---

### Requirement: Persistence and process spawning SHALL live only in adapters

No file in `ui/`, `domain/` or `ports/` may reference `execAsync`,
`GLib.file_get_contents`, `GLib.file_set_contents`, `GLib.file_test` or
`GLib.mkdir_with_parents`. Those calls belong to `adapters/`. Gate check 2
enforces this. `adapters/` SHALL exist and SHALL be non-empty.

`GLib.getenv` and `GLib.get_home_dir` are environment reads rather than persistence
and are NOT covered by this rule; they are injected into `domain/` instead.

#### Scenario: UI module calling execAsync fails the gate
- **WHEN** `ui/classic/ClassicWindow.tsx` contains `execAsync(args)`
- **THEN** the gate fails with `'execAsync' in ui/ -- persistence and spawning belong in adapters/`

#### Scenario: Adapter calling file_set_contents passes
- **WHEN** `adapters/glib-settings-store.ts` calls `GLib.file_set_contents`
- **THEN** the gate passes

#### Scenario: Domain reading an env var by injection passes
- **WHEN** `domain/settings.ts` receives `getenv` as a parameter and never imports GLib
- **THEN** the gate passes

---

### Requirement: Exactly one request→argv translator SHALL exist, in domain/

Capture argv SHALL be constructed by exactly one module in the whole tool, and that
module SHALL live in `domain/`. Gate check 3 enforces both the uniqueness and the
location. This is the seam that makes "two layouts, one engine" true rather than
aspirational: it is what stops a second layout from re-deriving the GIF size token
and the audio vocabulary by hand.

#### Scenario: Second translator fails the gate
- **WHEN** a module in `ui/` builds `["capture-tool", "screenshot", ...]`
- **THEN** the gate fails with `N modules build capture argv -- layouts must share ONE translator or the GIF size token and audio vocabulary drift`

#### Scenario: Translator outside domain/ fails the gate
- **WHEN** the single translator lives in `ui/` rather than `domain/`
- **THEN** the gate fails, naming the reason that the engine seam must be pure

#### Scenario: Single translator in domain/ passes
- **WHEN** `domain/cli-args.ts` is the only module building capture argv
- **THEN** the gate passes with `check 3: single argv translator at domain/cli-args.ts`

---

### Requirement: The translator SHALL emit the backend's exact token vocabulary

The GIF scale token SHALL be `original`, `75`, or `50` — never a percentage string.
The `--audio` flag SHALL be `none`, `system`, or `mic` — never `microphone`. These
are the two vocabulary traps between the UI layer and `bin/capture-tool`'s argparse,
which rejects anything else.

#### Scenario: GIF size is a bare number
- **WHEN** a GIF recording request with scale `75%` is translated
- **THEN** the argv contains `--size 75`, not `--size 75%`

#### Scenario: Microphone maps to mic
- **WHEN** a recording request with audio source `microphone` is translated
- **THEN** the argv contains `--audio mic`, not `--audio microphone`

---

### Requirement: Ports SHALL declare no concrete implementation

`ports/` SHALL contain only interfaces and abstract types. A concrete class with a
body in `ports/` fails the gate. This mirrors
`oci-strict-hexagonal-layering`'s "ports are ABCs or typed dataclass aggregates only".

#### Scenario: Concrete class in ports/ fails the gate
- **WHEN** `ports/capture-launcher.ts` declares a class that builds the argv itself
- **THEN** the gate fails, directing the implementation to `adapters/`

---

### Requirement: The pre-hexagonal stubs SHALL be deleted, not relocated

`ui/ScreenshotView.tsx`, `ui/RecordingView.tsx`,
`controllers/CaptureController.ts`, `controllers/ScreenshotController.ts`,
`controllers/RecordingController.ts` and `controllers/TargetResolver.ts` SHALL NOT
exist. They are unimplemented scaffolds; relocating them into `ports/` would create
a parallel, never-exercised architecture beside the real one.

Their removal SHALL be complete across all four coupling sites: the placement
entries in `gui_tools/vars/main.yml`, the assertions in `verify/vars/main.yml`, and
the pinned lists in `test_gui_tools_role.py` and `test_verify_role.py`.

#### Scenario: A stub still present fails the gate
- **WHEN** `controllers/TargetResolver.ts` exists
- **THEN** the gate fails with `unused pre-hexagonal stub -- deleted by this refactor`

#### Scenario: Stubs deleted but verify role still asserts them fails the role tests
- **WHEN** the stubs are deleted and `verify/vars/main.yml:493-498` is left untouched
- **THEN** `provisioning/tests/unit/test_verify_role.py` fails, because the verify role asserts those files are deployed

---

### Requirement: Every capture GUI file SHALL be registered for per-file placement

Every file under `src/gui-tools/capture-tool/` (excluding `tests/`, `README.md`,
`bin/` and generated directories) SHALL appear as a `source:` entry in
`gui_tools_app_files`, and no entry SHALL name a file that does not exist. Placement
is PER-FILE, so an unregistered file silently never deploys — the exact silent-no-op
class of bug the role's own header warns about. Gate check 5 enforces both directions.

#### Scenario: New layer file not registered fails the gate
- **WHEN** `domain/cli-args.ts` exists but is absent from `gui_tools_app_files`
- **THEN** the gate fails with `not in gui_tools_app_files -- per-file placement means it will NEVER deploy`

#### Scenario: Deleted file still registered fails the gate
- **WHEN** `gui_tools_app_files` still names `ui/CaptureWindow.tsx` after it is deleted
- **THEN** the gate fails with `registered in gui_tools_app_files but not on disk`

#### Scenario: Build artifact in the tool directory does not fail the gate
- **WHEN** `.pytest_cache/` exists inside `src/gui-tools/capture-tool/`
- **THEN** the gate ignores it and stays green

---

### Requirement: The classic layout's class vocabulary SHALL be unchanged

The refactor moves code between modules. It SHALL NOT add, drop or rename a single
CSS class token used by the classic layout, nor a single selector in `style.css`.
`scripts/capture-hexagonal-gate.py` check 6 compares both sets against
`scripts/capture-classic-parity.json`.

The check compares **sets**, not semantics: `capture-window`, `capture-root`,
`settings` and `settings-group` are styled via `window#capture-window` or
`centerbox` selectors or not at all, and `settings-name`/`settings-desc`/
`settings-group-title` are passed as variables to `settingsLabel()`. A semantic
"every used token must have a rule" check would raise six false positives; the set
snapshot is the correct granularity for "the layout did not change".

#### Scenario: A class token is added fails the gate
- **WHEN** the classic layout gains a `class="floating-grid"`
- **THEN** the gate fails with `token 'floating-grid' is new -- not in the baseline`

#### Scenario: A class token is dropped fails the gate
- **WHEN** `panel-footer` is removed from the classic layout
- **THEN** the gate fails with `token 'panel-footer' disappeared -- refactor must not drop classes`

#### Scenario: Missing baseline exits 2
- **WHEN** `scripts/capture-classic-parity.json` does not exist
- **THEN** the gate exits 2 with `run with --update-parity once to record the pre-refactor class vocabulary`

---

### Requirement: The GUI SHALL typecheck with zero errors in its own files

`src/gui-tools/capture-tool/**` SHALL pass `tsc --noEmit` with zero errors. Errors
under `/usr/share/ags/js/**` (the AGS runtime and gnim) are third-party and
tolerated by location, following the `ALLOWLIST` precedent in
`scripts/wifi-mock-parity.py`.

This is a genuine new guarantee, not a restatement: `ags bundle` transpiles without
checking, so today a type error reaches production silently. Verified — a file
assigning a string to a `number` bundles with exit 0.

The typecheck requires `skipLibCheck: true`, an `include` covering
`@girs/index.d.ts`, and `lib: ["ES2022", "DOM"]`. Omitting the `@girs` include makes
every `gi://` import unresolvable and degrades JSX handler parameters to implicit
`any`, producing ~101 spurious errors.

#### Scenario: A type error in the capture tool fails the gate
- **WHEN** `domain/settings.ts` assigns a string to a `number`-typed field
- **THEN** the typecheck gate fails naming the file and line

#### Scenario: Third-party ags runtime errors do not fail the gate
- **WHEN** `tsc` reports errors under `/usr/share/ags/js/node_modules/gnim/**`
- **THEN** the gate filters them out and stays green

---

### Requirement: The extracted pure domain logic SHALL have direct unit tests

`mergeSettings`, `validateSettings`, `configDefaults`, the `loadUiState` merge,
`audioToUi` and the GIF size mapping SHALL each have direct tests covering
first-run, corrupt, partial, out-of-range and wrong-type inputs. Today this logic is
only exercised indirectly through the Python CLI tests, and it is exactly the code a
file move can silently break.

#### Scenario: Corrupt config degrades to defaults
- **WHEN** `mergeSettings` receives malformed JSON's already-parsed garbage (a non-object)
- **THEN** every field falls back to its default

#### Scenario: Out-of-range custom duration is clamped
- **WHEN** the persisted `customDuration` is 1
- **THEN** the merge falls back to the base value; when it is 99999 it clamps to 3600 and rounds

---

### Requirement: Load-bearing GTK constraints SHALL be preserved verbatim

The following empirically-derived constraints SHALL travel with the code they govern.
Each is a comment block recording a live-debugging finding; losing them invites
re-introducing the bug.

| Constraint | Governs |
|---|---|
| The window paints nothing; chrome lives on the child | window shell |
| No box-shadow on the panel | `capture-panel` |
| `Gtk.Image` + `set_pixel_size`, never `Gtk.Picture` + `set_size_request` | icon builder |
| `syncWindowSize()` is deliberately synchronous | view switching |
| `centerbox`, never `box`, as the window's direct child | window shell |
| `Gtk.Switch`, never a hand-rolled track+knob | `toggleRow` |

#### Scenario: Comment dropped during the move
- **WHEN** `syncWindowSize()` moves to `ui/classic/ClassicWindow.tsx` without its rationale
- **THEN** code review rejects the task; the comment is part of the deliverable, not decoration

---

### Requirement: Refactoring SHALL NOT change observable behaviour

The acceptance floor for every task: the capture test suite stays at 94 passing, the
provisioning suites stay at 93 passing plus one pre-existing unrelated failure, the
class vocabulary is unchanged, and `style.css` and `types.ts` are untouched. The
configuration contract at `~/.config/capture-tool/config.json` and the UI-state file
at `~/.local/state/capture-tool/capture-ui.json` SHALL round-trip byte-compatibly —
`bin/capture-tool` reads the config on every invocation, so its format is a backend
contract, not a GUI implementation detail.

#### Scenario: A new key added to the config file
- **WHEN** the refactor writes an additional field into `config.json`
- **THEN** this violates the requirement — the backend does not know that key and the GUI's merge is the only reader that tolerates it