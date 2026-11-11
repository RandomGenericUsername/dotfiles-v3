---
id: REQ-111
title: "Host radius granularity: outer-only decision and guards"
kind: requirement
status: proposed
lane: design
links:
  openspec: none
  bmad: none
  design: docs/111-host-radius-granularity.md
worktree: .worktrees/REQ-111/
branch: ticket/REQ-111-host-radius-granularity
---

# Host radius granularity: outer-only decision and guards

## Requirement

Decide and record whether Hyprland `decoration:rounding` may reach inner
consumer roles, then define the smallest slice that prevents semantic drift.

- **Outer-only.** `decoration:rounding` is an outer-window/outer-surface value.
  The host allowlist remains exactly `surface.panel.radius` and
  `surface.panel.border-width`.
- **`surface.panel` is the outer-surface role.** Consumers map their outermost
  window/panel geometry to it. It is not limited to the AGS bar panel.
- **Inner radii are skin-owned.** `surface.card.radius`,
  `surface.control.radius`, `surface.cell.radius` and `surface.pill.radius`
  are authored design values and must not be host-inheritable.
- **No new role now.** A `surface.window` role is deferred until a real
  toplevel outer surface cannot honestly use `panel`; it is not needed for the
  current rofi/wlogout/layer-shell consumers.
- **No behavior change.** This ticket is docs + regression guards only; no
  schema, runtime, assets value, provisioning, composition or tag change.

## Scope of this ticket

1. Design record: `docs/111-host-radius-granularity.md`.
2. Link the decision from docs/109 and the `SKIN-CONSUMERS` epic.
3. Name the guard slice for `dotfiles-assets` (does not run here):
   - negative fixture for an inner-radius `[host].inherit` path;
   - rofi host-probe render assertion (window follows; mainbox/inputbar/element
     do not);
   - README/docstring clarification that wlogout buttons are outer action cards.
4. Read-only visual evidence at host rounding 0 / live 9 / a large value.

## Acceptance

- [x] `docs/111-host-radius-granularity.md` records the decision, options,
  contract/runtime/assets impact, visual risks, criteria, migration and
  open questions.
- [x] Docs/109 links the granularity decision and still defers
  `surface.window` to a separate proposal.
- [x] `docs/epics/SKIN-CONSUMERS.md` lists this design/tracking ticket.
- [x] The ticket names the exact next implementation slice in
  `dotfiles-assets` and states explicitly that it changes no behavior.
- [ ] Read-only live probe at rounding 0, 9 and a large value confirms rofi
  outer follows while inner roles do not, and wlogout cards follow. (To run in
  the guard slice; this design pass records the existing 9px evidence.)
- [x] `make gates-ci` in this worktree is green before merge. Observed 2026-11-11:
  all four gates PASS (docs-only change).
- [x] No schema/runtime/assets/provisioning/composition/app change and no tag
  moved in this ticket.

## Evidence

- Live: `hyprctl -j getoption decoration:rounding` → int 9 on Hyprland 0.57.2.
- Generation `af4c31a8…`: host radius 9; rofi window 9 / mainbox 0 /
  inputbar 2 / element 0; wlogout button 9.
- Contract allowlist: `contracts/schemas/appearance-manifest.schema.json`
  `hostPolicy.inherit.items.enum` (two paths).
- Runtime mapping: `dotfiles-runtime/src/runtime/domain/host_defaults.py`
  `HOST_MAP` (two paths).
- Assets guard: `dotfiles-assets/scripts/validate-skins.py`
  `HOST_INHERITABLE` (two paths).
- Prior intent: docs/109 §Phase 1 scope and §H-3.2; docs/108 `W-2.12`.

## Next implementation slice (after this design is accepted)

**Repo:** `dotfiles-assets`, one ticket/branch/worktree.

1. Add `skins/tests/fixtures/invalid/host-inner-radius.toml` — a valid manifest
   whose `[host].inherit` names `surface.card.radius`; assert `validate-skins`
   fails with the known-path/allowlist message. Mirror the existing
   `host-unknown-inherit.toml` pattern.
2. Add a host-probe render test: resolve `terminal-host` with a probe radius,
   render `rofi.rasi`, assert `window` equals the probe and
   `mainbox`/`inputbar`/`element` equal the skin's card/control/cell radii.
   Repeat for `glass` and `paper`.
3. Extend the `validate-skins` module docstring / skins README with the
   outer-only rule and the wlogout action-card exception.
4. Run `make gates` / `validate-skins`; no runtime or contract change is
   expected.

**Follow-on only if triggered:** a separate contract proposal for
`surface.window` (`HG-2.1`–`HG-2.4`).

## Non-goals

- No inner-radius host mapping (`HG-X1`), no computed/derived inner radii
  (`HG-X2`), no layer-shell/toplevel conflation (`HG-X3`).
- No `surface.window` role in this ticket.
- No change to `surface.panel.radius`, host hash, generation identity, doctor,
  provisioning links, consumer templates or app skins.
