---
id: REQ-111
title: "Host radius granularity: skin-delegated rectangle radii"
kind: requirement
status: design-accepted
lane: design
links:
  openspec: none
  bmad: none
  design: docs/111-host-radius-granularity.md
worktree: .worktrees/REQ-111/
branch: ticket/REQ-111-host-radius-granularity
---

# Host radius granularity: skin-delegated rectangle radii

## Requirement

Decide and record how Hyprland `decoration:rounding` reaches consumer surface
roles, then define the implementation slices that lock it in.

- **Skin-delegated rectangles.** A skin may delegate `surface.panel.radius`,
  `surface.card.radius`, `surface.control.radius` and `surface.cell.radius` to
  the host, plus `surface.panel.border-width` to `general:border_size`.
- **Pill stays explicit.** `surface.pill.radius` is never host-inheritable; a
  capsule must not become a rounded rectangle because the compositor changed.
- **Opt-in per skin and per path.** `glass`, `paper` and `terminal-host` will
  delegate the full rectangle set in the assets slice. `terminal` and `flat`
  remain explicit with no `[host]` policy.
- **Consumers keep their mappings.** rofi `window`/`mainbox`/`inputbar`/
  `element` map to panel/card/control/cell; wlogout action cards remain panel
  (outer action cards, not inner controls); GTK cards/controls use card/control.
- **No new role.** `surface.window` stays deferred; no inner border-width,
  padding, gap, type or colour delegation; no derived radii.

This ticket records the design and cross-links. It changes no schema, runtime,
assets value, provisioning, engine, composition or tag.

## Scope of this ticket

1. Revise `docs/111-host-radius-granularity.md` from outer-only to the
   skin-delegated rectangle model, with criteria `HG-2.1`–`HG-2.12`, a
   validation matrix, risks, non-goals and the implementation sequence.
2. Update docs/109 granularity wording, docs/108 `W-2.12`, and the
   `SKIN-CONSUMERS` epic row.
3. Mark the prior outer-only assets guards (REQ-025) as needing deliberate
   inversion in the assets slice: the `host-inner-radius` fixture and the
   "only the outer window moves" rofi test are obsolete; add a pill negative
   fixture.
4. Record the read-only validation plan at host rounding 0 / 9 / large for
   rofi, wlogout and GTK.

## Acceptance

- [x] `docs/111` records the revised model, options, contract/version impact,
  implementation sequence, validation matrix, risks, criteria, migration and
  non-goals.
- [x] docs/109 links the revision and supersedes the outer-only wording;
  docs/108 `W-2.12` states wlogout stays a panel-mapped outer action card.
- [x] `docs/epics/SKIN-CONSUMERS.md` links the revised design and criteria IDs.
- [x] This ticket names the exact implementation slices and states that this
  design pass changes no behavior.
- [ ] Contracts/runtime/assets/engine/composition slices implemented and tagged
  (`HG-2.3`–`HG-2.9`).
- [ ] Read-only validation matrix V-1…V-11 recorded (`HG-2.10`).
- [x] `make gates-ci` in this worktree is green before merge. Observed 2026-11-11:
  docs-only change; gates recorded in the commit report.
- [x] No schema/runtime/assets/provisioning/composition/app change and no tag
  moved in this ticket.

## Evidence

- Live: `hyprctl -j getoption decoration:rounding` → int 9 on Hyprland 0.57.2.
- Existing generation `af4c31a8…` under panel-only policy: rofi window 9 /
  mainbox 0 / inputbar 2 / element 0; wlogout button 9. This is the baseline the
  revised model changes for opted-in skins.
- Contract allowlist: `contracts/schemas/appearance-manifest.schema.json`
  `hostPolicy.inherit.items.enum` (two paths today).
- Runtime mapping: `dotfiles-runtime/src/runtime/domain/host_defaults.py`
  `HOST_MAP`/`HOST_BOUNDS` (two paths today).
- Assets guard: `dotfiles-assets/scripts/validate-skins.py`
  `HOST_INHERITABLE`/`HOST_PROBE`; obsolete negative fixture
  `skins/tests/fixtures/invalid/host-inner-radius.toml`; obsolete rofi test
  `test_rofi_host_probe_moves_only_the_outer_window_radius`.
- wlogout mapping: `dotfiles-assets/skins/templates/wlogout.gtk.css.j2`
  (button radius/border from panel, fill from card).
- Prior intent: docs/109 §Phase 1 scope and §H-3.2; docs/108 `W-2.12`.

## Next implementation slices

**1. `contracts` — additive allowlist (`HG-2.3`)**

- Add `surface.card.radius`, `surface.control.radius`, `surface.cell.radius`
  to `hostPolicy.inherit.items.enum` and to generation `host.defaults`
  (`0..64`). Pill remains absent.
- Tests: new paths accepted; pill and inner border-width rejected; old
  manifests/generations validate; `appearance.v3` unchanged.
- Release additive minor; do not bump `HOST_MAP_VERSION`.

**2. `dotfiles-runtime` — mapping (`HG-2.4`)**

- Add the three paths to `HOST_MAP` (same `decoration:rounding` source) and
  `HOST_BOUNDS` (`0..64`); validate generation defaults; doctor compares all
  delegated paths; `hostHash` includes only participating paths.
- Tests: values reach every delegated role; pill rejected; panel-only
  generations keep identity; host 0/9/24 and bound 64 pass, 65 fails.

**3. `dotfiles-assets` — skins and guards (`HG-2.5`–`HG-2.7`)**

- Expand `HOST_INHERITABLE` to the five paths and `HOST_PROBE` to cover all
  five.
- `glass`, `paper`, `terminal-host` opt in to the four radii + panel border;
  `terminal`/`flat` unchanged.
- Remove/convert `host-inner-radius.toml`; add a `surface.pill.radius`
  negative fixture; replace the outer-only rofi test with the delegated matrix.
- Add wlogout panel-action-card and GTK3/GTK4 delegated card/control probes;
  assert pills stay authored. Update README/docstring.
- Release minor.

**4. `dotfiles-provision` / engine (`HG-2.8`)**

- Update any mirrored schema/token constants; the verify token-path list
  already names panel/card/cell/control. No consumer link/template/layout
  changes. Bump the engine pin after upstream tags.

**5. `dotfiles-v3` composition (`HG-2.9`)**

- Update `program-tuple.yaml` and pins only after releases; run `make gates-ci`
  and `make deploy-coverage`; tag the composition.

**6. Local read-only validation (`HG-2.10`)**

- Probe rofi/wlogout/GTK at host 0/9/large using temp XDG roots; no apply and
  no live generation commit.

## Non-goals

- No pill delegation (`HG-X1`), no derived/scaled radii (`HG-X2`), no forced
  delegation (`HG-X3`), no inner border/padding/type/colour delegation
  (`HG-X4`), no `surface.window` role (`HG-X5`).
- No claim that the compositor rounds layer-shell content or inner widgets
  (`HG-X6`); the outer-only rule is no longer universal (`HG-X7`).
- No change to `terminal`/`flat`, app layout, provisioning links, consumer
  templates or host mapping version in the design slice.
