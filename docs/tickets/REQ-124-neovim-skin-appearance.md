---
id: REQ-124
title: "Neovim follows the active skin appearance (follow-up)"
kind: requirement
status: done
lane: design
links:
  openspec: none
  bmad: none
  design: docs/116-neovim-skin-appearance.md
worktree: .worktrees/REQ-124/
branch: ticket/REQ-124-neovim-skin-appearance
---

# Neovim follows the active skin appearance (follow-up)

## Why

`REQ-123` makes Neovim consume the generated **palette**. The appearance plane
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
   - syntax/LSP/diagnostics → palette (from `REQ-123`);
   - explain which skin tokens are meaningful for a terminal editor and which
     are app-only (layer-shell geometry, wlogout paint, etc.).
4. Design the delivery chain: producer artifact → runtime publication →
   provisioning stable link → Neovim loader with fallback.
5. Add a visual/acceptance fixture showing the same editor under at least the
   `glass`, `flat` and `terminal` skins.

## Design outcome

**Decision: yes — chrome only.** Neovim reads the active skin's
`current/appearance/tokens.json` through a new provisioning-owned stable link
(`config/nvim/lua/dotfiles-appearance.json`) and applies it **after** the
REQ-123 palette. Syntax, LSP, diagnostics, diff and terminal colours stay
palette-owned.

**Artifact: no new contract format.** The generation already requires
`appearance.tokensPath = "appearance/tokens.json"`
(`contracts/schemas/generation-manifest.schema.json:294-301`). Reusing it avoids
widening the `rasi | conf | theme` enum and needs no contracts/ runtime release.
Rejected: a new `json`/`lua` artifact (enum + runtime + assets + release
churn), a per-skin Lua module (duplicates the palette), `conf`/`rasi`/`theme`
(wrong shape; literal hex forbidden), reading the skin TOML in the editor
(duplicates the runtime resolver), and palette-only (loses the skin's chrome
distinction).

Full record: [`docs/116-neovim-skin-appearance.md`](../116-neovim-skin-appearance.md).

## Non-goals

- No syntax-highlighting change here; that is `REQ-123`.
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

- [x] A design record states whether the editor follows skin appearance, with
      evidence from the current `appearance.artifacts` contract and the runtime
      generation manifest.
- [x] The mapping boundary (palette vs appearance) is explicit.
- [x] If a new artifact format is required, the contract change and its release
      impact are scoped; otherwise the chosen existing format is justified.
- [x] A delivery chain and a three-skin visual fixture are defined.
- [x] No tag, release, pin bump, package install/apply, or UI worktree touched.

## Evidence

- Design record: `docs/116-neovim-skin-appearance.md`.
- Generated appearance plane:
  `dotfiles-v3/docs/105-appearance-plane-v2.md`,
  `dotfiles-v3/docs/110-format-aware-skin-consumers.md`.
- Appearance artifact format enum:
  `contracts` `generation-manifest.schema.json` (`appearance.artifacts`
  `format` enum `rasi|conf|theme`, `:276-283`; required `tokensPath`
  `const: appearance/tokens.json`, `:294-301`).
- Runtime publication/verification of the token document:
  `dotfiles-runtime/src/runtime/adapters/appearance.py:71,474-479`;
  `generation_store.py:579-583,673`.
- Live generation: `~/.local/state/dotfiles/current/manifest.json` →
  `"tokensPath": "appearance/tokens.json"`; `current/appearance/tokens.json`
  is a resolved v2 document (six surface roles, state/type/ink/layout).
- Stable consumer links and current consumers:
  `dotfiles-provision/ansible/roles/state_links/vars/main.yml:37-46,53-54`;
  resolve assertion at `tasks/main.yml:73-97`.
- Existing Neovim palette and live reload:
  `dotfiles-assets/configs/nvim/lua/plugins/lazyvim.lua:1-15`;
  `dotfiles-assets/configs/nvim/lua/config/autocmds.lua:10-34`;
  `dotfiles-runtime/src/runtime/adapters/nvim_reloader.py:77-119`, wired at
  `dotfiles-runtime/src/runtime/cli/main.py:481-483`.
- Skin differences: `dotfiles-assets/skins/README.md:170-190` and
  `skins/manifests/{glass,flat,terminal}.toml`.
- Palette projection (predecessor): `docs/115-neovim-palette-projection.md`.

### Design-phase verification (2026-11-19)

- `bash scripts/worktree-guard.sh create REQ-124 neovim-skin-appearance` →
  `worktree=.worktrees/REQ-124/`, branch
  `ticket/REQ-124-neovim-skin-appearance`.
- The live manifest and `tokens.json` were read read-only; the three-skin
  comparison was resolved with the assets validator's own
  `_resolve_manifest` (mode then host precedence), not by eyeballing templates.
- No tag, release, pin bump, apply or UI repo was touched.

## Next step

Implementation is **not** started. The next slices (each separately gated, see
design §9) are: provisioning stable link → tpr full palette role map → assets
loader + headless three-skin fixtures → runtime skin-only reload confirmation →
composition pin cutover. Do not tag, release, or bump pins until the user
authorizes shipping.


## Released

- tpr v0.7.1 — full palette role map
- runtime v1.6.4 — format-set cache identity
- assets v0.22.0 — appearance loader + SIGUSR1 reload
- engine v0.1.94 — appearance tokens link + assets mirror
- composition v0.2.4 — pins
