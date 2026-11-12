---
id: REQ-120
title: "Neovim follows the active skin appearance (follow-up)"
kind: requirement
status: proposed
lane: design
links:
  openspec: none
  bmad: none
worktree: none
branch: none
---

# Neovim follows the active skin appearance (follow-up)

## Why

`REQ-116` makes Neovim consume the generated **palette**. The appearance plane
(`state/current/appearance/tokens.json` and the per-consumer artifacts) carries
the selected skin's surfaces, geometry, typography and opacity. Some editor
chrome (background, float/panel surfaces, statusline separation, opacity) could
follow the skin too.

This is deliberately separate from palette syntax highlighting: syntax colours
are a palette concern, while surfaces/geometry are a skin concern.

## Requirement (design first)

1. Decide whether the editor should consume the skin appearance at all, or stay
   palette-only. Record the decision and the rejected alternatives.
2. If yes, choose the artifact shape:
   - reuse an existing format (`conf`/`rasi`/`theme`) where honest; or
   - add a new artifact format to the generation contract — note that
     `appearance.artifacts` currently allows `rasi | conf | theme`, so a Lua
     artifact would be a contract change with its own schema/release.
3. Define the mapping boundary:
   - editor backgrounds/floats/statusline → appearance surfaces;
   - syntax/LSP/diagnostics → palette (from `REQ-116`);
   - explain which skin tokens are meaningful for a terminal editor and which
     are app-only (layer-shell geometry, wlogout paint, etc.).
4. Design the delivery chain: producer artifact → runtime publication →
   provisioning stable link → Neovim loader with fallback.
5. Add a visual/acceptance fixture showing the same editor under at least the
   `glass`, `flat` and `terminal` skins.

## Non-goals

- No syntax-highlighting change here; that is `REQ-116`.
- No live reload while Neovim is open unless separately designed.
- No change to the existing app consumers.

## Forbidden now

- No git tag, release, or release-note publication.
- No merge to `master`/`main`.
- No release-metadata or pin bump (`installer.pin`, `assets.tag`, tpr/runtime
  pins, `program-tuple.yaml`).
- No package install or apply/provision run.
- No touching any `ags-*`, `ags-platform`, or other UI worktree/repo.

## Acceptance

- [ ] A design record states whether the editor follows skin appearance, with
      evidence from the current `appearance.artifacts` contract and the runtime
      generation manifest.
- [ ] The mapping boundary (palette vs appearance) is explicit.
- [ ] If a new artifact format is required, the contract change and its release
      impact are scoped; otherwise the chosen existing format is justified.
- [ ] A delivery chain and a three-skin visual fixture are defined.
- [ ] No tag, release, pin bump, package install/apply, or UI worktree touched.

## Evidence

- Generated appearance plane:
  `dotfiles-v3/docs/105-appearance-plane-v2.md`,
  `dotfiles-v3/docs/110-format-aware-skin-consumers.md`.
- Appearance artifact format enum:
  `contracts` `generation-manifest.schema.json` (`appearance.artifacts`).
- Stable consumer links and current consumers:
  `dotfiles-provision/ansible/roles/state_links/vars/main.yml:38-46`.
- Palette projection (predecessor):
  `dotfiles-v3/docs/tickets/REQ-116-neovim-generated-palette.md`.

## Next step

Wait for `REQ-116` to settle the palette path, then write this design record.
Do not implement, tag, release, or bump pins until the user authorizes shipping.
