## Why

The capture tool's GUI is one 1865-line file, `src/gui-tools/capture-tool/ui/CaptureWindow.tsx`, that owns domain logic, persistence, process spawning, and every GTK widget. Five concrete problems, all verified on this branch:

1. **Zero compile-time safety net.** AGS 3.1.2 bundles with `ags bundle`, which is a *transpile*, not a type check. Verified: a file containing `const bad: number = "not a number"` and `function f(a: string): void { return 42 }` bundles with **exit 0** and ships `var bad = "not a number"`. Only module-resolution failures are caught. Every type error in the GUI surfaces as a runtime failure — and the GUI only runs when the operator presses SUPER+PRINT on a live Wayland session.

2. **The pure logic has no direct tests.** `mergeSettings` (corrupt-tolerant config merge, `CaptureWindow.tsx:104`), `validateSettings` (`:165`), `configDefaults` (the three-tier precedence rule, `:315`) and `loadUiState`'s merge half (`:334`) are exactly the code most likely to break silently during a move, and today they are only exercised indirectly through the Python CLI tests.

3. **Dead scaffolding creates a parallel abstraction.** `controllers/{Capture,Screenshot,Recording}Controller.ts`, `controllers/TargetResolver.ts` and `ui/{Screenshot,Recording}View.tsx` are unimplemented stubs (the file itself says so at `:15`). They are deployed by provisioning and asserted by the verify role, so they persist as a *second*, never-exercised architecture next to the real one.

4. **The engine-reuse seam does not exist yet.** argv construction is interleaved with `execAsync` (`:554`, `:576`), so the GIF size token (`GIF_SIZE_ARG`, `:396` — `"75"`, not `"75%"`) and the audio vocabulary (`audioToUi`, `:307` — `mic` ↔ `microphone`) are duplicated per-call-site. A second UI built by hand would silently diverge on both.

5. **The next feature depends on this.** A second, richer capture layout is planned. It must reuse the engine exactly, must leave the current layout byte-identical, and must be able to guarantee "the current tool is unchanged" mechanically rather than by assertion.

The repo already has a ratified answer to (1)–(4) for the `oci` module: `openspec/specs/oci-strict-hexagonal-layering/spec.md`, enforced by an AST linter in `tests/architecture/test_layering.py`. The capture tool does not conform to it because it predates it.

## What Changes

**A behavior-preserving restructure of `src/gui-tools/capture-tool/` into hexagonal layers. No feature, no layout, no visible change.**

- **Layers.** `domain/` (pure data + pure functions, zero GTK/GLib/subprocess), `ports/` (interfaces only, no concrete implementations), `adapters/` (all I/O: GLib persistence, `execAsync`, backend probe), `ui/` (GTK construction only). `app.tsx` becomes a composition root that wires ports to adapters.
- **The engine-reuse seam.** A single pure `domain/cli-args.ts` translating a capture request into argv. Both the current layout and any future layout call it, so flag names, the GIF size token, and the audio vocabulary have exactly one source.
- **The dead scaffolding is deleted**, together with its six placement entries in `gui_tools/vars/main.yml`, its six assertions in `verify/vars/main.yml`, and the two provisioning test files that pin them.
- **Two new executable gates**, following the repo's existing `scripts/*-parity.py` / `*-no-new-architecture.py` precedent:
  - `scripts/capture-hexagonal-gate.py` — layering, adapter ownership, single-argv-translator, no-dead-scaffold, per-file provisioning registration, and a **class-vocabulary parity snapshot** that fails if a single CSS class token is added, dropped, or renamed.
  - a TypeScript typecheck gate over `src/gui-tools/capture-tool/`, scoped to *our* files. Measured baseline: **2 errors in our code**, **28 in the ags runtime itself** (third-party, tolerated).
- **Unit tests for the extracted pure logic**, which is what makes the move verifiable rather than hopeful.

**Explicitly NOT in this change:** the new layout; any layout-switch setting; any new engine/CLI capability; any change to `bin/capture-tool`, the runtime, or the bar. Those are the next change, built on this one.

## Capabilities

### New Capabilities

- `capture-tool-hexagonal`: the layer boundaries and import-direction rules for the capture GUI, the single request→argv translator, the builder-kit reuse contract, the dead-scaffolding removal, and the two gates that enforce all of it.

### Modified Capabilities

*(None — no existing spec covers the capture GUI. This change introduces its first.)*

## Impact

- **GUI sources** (`src/gui-tools/capture-tool/`): `ui/CaptureWindow.tsx` split across `domain/`, `ports/`, `adapters/`, `ui/`; `app.tsx` reduced to wiring; six stub files deleted. `style.css` and `types.ts` unchanged.
- **Provisioning**: `gui_tools/vars/main.yml` (remove 6 placements, add the new layer files), `verify/vars/main.yml` (remove 6 assertions). Placement stays **per-file** — an unregistered file silently never deploys, which is why this is gated.
- **Gates**: `make gates` gains two new developer-run targets. CI is untouched —
  the existing workflow's push trigger names a branch that does not exist
  (design.md §7.1).
- **Behavior**: none. This is the acceptance criterion, not a side effect.
- **Prerequisite for**: the alternate-layout change, which depends on this being green.