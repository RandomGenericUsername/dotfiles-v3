---
title: 'Separate wallpaper application from palette reloads'
type: 'bugfix'
created: '2026-09-23'
status: 'done'
review_loop_iteration: 0
baseline_commit: '333c19c3fae980d1fc2551326ecb99d860b6dc58'
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-09-11-phase5/ARCHITECTURE-SPINE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `wallpaper set` applies the selected image in its visible-first phase, then applies it again because Hyprpaper is mixed into Reconcile's palette/UI reloader list. This duplicate apply can cause a second visual transition. The shared list also obscures the distinct roles: Hyprpaper displays the image; other reloaders consume generated palette artifacts.

**Approach:** Give wallpaper application a distinct runtime port/stage owned by `ReconcileDesktopStateUseCase`. Ordinary reconcile applies the persisted wallpaper once; `wallpaper set` keeps its early visible apply and tells the final reconcile that this stage already ran. Reconcile remains responsible for final convergence and all palette/UI reloads.

## Boundaries & Constraints

**Always:** Keep the synchronous imperative runtime pipeline and hexagonal boundaries. Preserve visible-first behavior, single-lock serialization, state/history semantics, existing per-consumer failure reporting, and ordinary reconcile's ability to restore the wallpaper from persisted state. The wallpaper set path must issue exactly one wallpaper apply before palette/UI reloads.

**Ask First:** None.

**Never:** Do not remove wallpaper restoration from ordinary reconcile. Do not make the wallpaper apply part of the palette/UI reloader collection. Do not add daemon orchestration, queues, or rollback of a wallpaper already shown.

</frozen-after-approval>

## Code Map

- `src/runtime/src/runtime/ports/desktop_reloader.py`, `src/runtime/src/runtime/ports/wallpaper_applier.py` -- distinct contracts for consumer reloads and wallpaper application.
- `src/runtime/src/runtime/adapters/hyprpaper_reloader.py` -- current Hyprpaper IPC adapter; implement the distinct apply role.
- `src/runtime/src/runtime/application/reconcile.py` -- convergence owner; invoke the wallpaper stage once before palette/UI reloaders, with an explicit way for a caller to report that the stage already ran.
- `src/runtime/src/runtime/application/swap_visible.py` -- visible-first phase; use the wallpaper-apply contract here.
- `src/runtime/src/runtime/cli/main.py` -- composition root builds separate wallpaper and palette/UI actors for set, reconcile, stale regeneration, and doctor repair.
- `src/runtime/tests/unit/test_cli_wallpaper_set.py`, `src/runtime/tests/unit/test_cli_reconcile.py`, `src/runtime/tests/unit/test_hyprpaper_reloader.py`, `src/runtime/tests/integration/test_wallpaper_set_capstone_integration.py` -- existing wiring and behavior expectations.

## Tasks & Acceptance

**Execution:**
- [x] `src/runtime/src/runtime/ports/desktop_reloader.py`, `src/runtime/src/runtime/ports/wallpaper_applier.py`, `src/runtime/src/runtime/adapters/hyprpaper_reloader.py` -- represent Hyprpaper as a wallpaper applier, distinct from palette/UI reloaders -- make runtime roles explicit.
- [x] `src/runtime/src/runtime/application/reconcile.py`, `src/runtime/src/runtime/application/swap_visible.py` -- sequence the dedicated wallpaper stage separately and let visible-first convergence skip only the already-completed apply -- retain Reconcile as convergence owner without repeating the image operation.
- [x] `src/runtime/src/runtime/cli/main.py` -- wire separate wallpaper and palette/UI actors for wallpaper set and all ordinary convergence entry points -- keep all command paths correctly composed.
- [x] `src/runtime/src/runtime/adapters/` and `src/runtime/src/runtime/application/` documentation/comments -- update names and ordering descriptions -- prevent the old role conflation from returning.

**Acceptance Criteria:**
- Given `wallpaper set` succeeds, when its runtime pipeline completes, then Hyprpaper receives exactly one apply for the selected wallpaper, before palette/UI reloaders run.
- Given an ordinary `reconcile`, when it converges persisted state, then Hyprpaper applies that wallpaper exactly once and palette/UI reloaders still run.
- Given Hyprpaper application fails in either path, when the command reports its result, then the failure is surfaced using the existing failure policy and is not silently treated as success.
- Given a failure after the visible-first apply, when final convergence fails, then the newly visible wallpaper remains selected and recovery can reconcile from persisted state.

## Spec Change Log

## Design Notes

The visible-first phase already persists a wallpaper-only state and repoints wallpaper links before invoking Hyprpaper. The final reconcile must therefore skip only the wallpaper-apply stage for that invocation; it still owns final state convergence, history, and palette/UI reloads. Ordinary reconcile has no earlier apply and keeps that stage enabled.

## Verification

**Manual checks:** Inspect the composed `wallpaper set` and ordinary `reconcile` actor order. Confirm the former has one Hyprpaper apply before palette/UI reloads and the latter has one Hyprpaper apply during reconciliation. Do not run or add tests unless requested.

## Suggested Review Order

**Command flow**

- The set command applies the selected wallpaper early, then tells final reconciliation that step is complete.
  [`main.py:572`](../../src/runtime/src/runtime/cli/main.py#L572)
- Ordinary reconcile gets the applier separately from color reloaders.
  [`main.py:1243`](../../src/runtime/src/runtime/cli/main.py#L1243)

**Reconcile stages**

- Reconcile applies the persisted wallpaper once before running palette/UI reloaders.
  [`reconcile.py:316`](../../src/runtime/src/runtime/application/reconcile.py#L316)
- The wallpaper applier contract is separate from the desktop consumer reloader contract.
  [`wallpaper_applier.py:6`](../../src/runtime/src/runtime/ports/wallpaper_applier.py#L6)
  [`desktop_reloader.py:6`](../../src/runtime/src/runtime/ports/desktop_reloader.py#L6)

**Hyprpaper implementation**

- Hyprpaper now implements the dedicated apply operation; the old reloader name remains as a compatibility wrapper.
  [`hyprpaper_reloader.py:140`](../../src/runtime/src/runtime/adapters/hyprpaper_reloader.py#L140)
- The visible-first use case uses the wallpaper apply port after repointing wallpaper links.
  [`swap_visible.py:150`](../../src/runtime/src/runtime/application/swap_visible.py#L150)
