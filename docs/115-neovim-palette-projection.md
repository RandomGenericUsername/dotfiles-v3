# 115 — Neovim palette projection (REQ-123 design)

> **Status:** design started. Implementation is split across theme-producer,
> dotfiles-runtime, dotfiles-provision and dotfiles-assets. No tag, release or
> pin bump happens in this phase.

## 1. Goal

Make Neovim consume the same wallpaper-derived palette that already drives
Hyprland, GTK, rofi, btop, wlogout and kitty, instead of a fixed Catppuccin
colorscheme. The editor keeps receiving a complete, self-contained colorscheme;
the palette producer owns the role→highlight mapping.

## 2. Current pipeline

- `theme-producer` renders palette projections from the selected wallpaper
  (`colors.yaml`, `colors.conf`, `colors.rasi`, `colors.kitty`,
  `colors.btop.theme`, `colors.sequences`, `colors.gtk.css`, `colors.adw.css`)
  through the open projection registry:
  `theme-producer/src/theme_producer/adapters/projections/registry.py:75-130`.
- The runtime caches the eight-artifact set and publishes it under
  `state/current/palette/` (`dotfiles-runtime/src/runtime/domain/models.py:56-77`,
  `dotfiles-runtime/src/runtime/adapters/producer_process.py:228-243`).
- Provisioning owns the stable consumer links:
  `dotfiles-provision/ansible/roles/state_links/vars/main.yml:38-46`.
- Neovim is not in that consumer set. LazyVim currently selects Catppuccin
  (`dotfiles-assets/configs/nvim/lua/plugins/lazyvim.lua`).
- LazyVim's `colorscheme` option accepts a function:
  `LazyVim/lua/lazyvim/config/init.lua:11-15,250-263`.

## 3. Decision

Add a new **open projection** to `theme-producer`:

```text
name:      nvim
filename:  colors.nvim.lua
template:  colors.nvim.lua.j2
capability: open
```

The rendered artifact is a Lua module, not a colors file on the runtime path.
The nvim config loads it by module name; no host path appears in the assets
corpus.

### 3.1 Artifact shape

```lua
local M = {}

M.name = "dotfiles"
M.mode = "dark" -- or "light"
M.palette = {
  background = "#…",
  foreground = "#…",
  accent = "#…",
  -- semantic roles used by the highlights below
  ansi = { "#…", --[[ 16 slots ]] },
}

M.highlights = {
  Normal = { fg = M.palette.foreground, bg = M.palette.background },
  -- …
}

function M.load()
  vim.cmd("hi clear")
  if vim.fn.exists("syntax_on") == 1 then
    vim.cmd("syntax reset")
  end
  vim.g.colors_name = M.name
  for group, attrs in pairs(M.highlights) do
    vim.api.nvim_set_hl(0, group, attrs)
  end
  for i, color in ipairs(M.palette.ansi) do
    vim.g["terminal_color_" .. (i - 1)] = color
  end
end

return M
```

The template is pure: it reads the projection context only (no filesystem, no
other template). The runtime exposes one selected mode per generation; the
template must render correctly when invoked with `--mode dark` or `--mode light`.

### 3.2 Highlight mapping

Use semantic Material roles, not legacy colour names:

| Neovim group(s) | Palette source |
| --- | --- |
| `Normal` | fg `on_surface`, bg `surface` |
| `NormalFloat`, `FloatBorder` | bg `surface_container`, border `outline` |
| `Cursor`, `TermCursor` | bg `primary` |
| `Visual` | bg `primary_container` |
| `Search`, `CurSearch` | bg `tertiary_container`, fg `on_tertiary_container` |
| `Pmenu`, `PmenuSel` | bg `surface_container_high`, sel `secondary_container` |
| `StatusLine`, `StatusLineNC` | bg `surface_container_high` / `surface_container` |
| `TabLine`, `TabLineSel` | `surface_container` / `secondary_container` |
| `WinSeparator`, `VertSplit` | `outline_variant` |
| `LineNr`, `CursorLineNr` | `on_surface_variant` / `primary` |
| `SignColumn`, `Folded` | `surface_container` |
| `Comment` | `on_surface_variant` |
| `Constant`, `Number`, `Boolean` | `tertiary` |
| `String` | `secondary` |
| `Identifier`, `Function` | `primary` |
| `Statement`, `Keyword`, `Operator` | `tertiary` |
| `Type`, `StorageClass`, `Structure` | `secondary` |
| `Special`, `SpecialChar` | `primary_fixed_dim` |
| `Error`, `DiagnosticError` | `error` |
| `Warning`, `DiagnosticWarn` | `warning` |
| `Info`, `DiagnosticInfo` | `secondary` |
| `Hint`, `DiagnosticHint` | `tertiary` |
| `DiffAdd/Change/Delete` | `tertiary_container` / `secondary_container` / `error_container` |
| `Todo` | fg `on_primary_container`, bg `primary_container`, bold |
| LSP references / underlines | `outline`, `error`, `warning` |
| Terminal colours 0–15 | the projection’s 16 legacy colours |

Treesitter and LSP groups inherit from the standard groups; no plugin-specific
hardcoding is needed. The template may emit the common Treesitter groups
(`@comment`, `@string`, `@function`, …) as explicit aliases when the standard
groups are not enough.

## 4. Cross-repo slices

### 4.1 theme-producer

- Add `colors.nvim.lua.j2`.
- Register `nvim` in `OPEN_PROJECTIONS`, `FORMAT_NAMES` and
  `_PROJECTION_BY_FORMAT`; capability stays `open`.
- Add a fixture (`colors.nvim.lua`) and tests that render both modes and assert
  the Lua parses/loads.
- `tpr` `--format nvim.lua` (or the chosen format name) must work.

### 4.2 dotfiles-runtime

- Extend `PaletteArtifacts` with `colors_nvim` and the manifest key
  `colors.nvim.lua`.
- Hash it in `producer_process.build_palette_entry`, carry it through
  `derive`, `cache`, `seeder` and `inspect`.
- Add `current/palette/colors.nvim.lua` to the published generation.
- Keep the identity of the existing eight artifacts unchanged.

### 4.3 dotfiles-provision

- Add the stable consumer link:
  `{ base: palette, spine: nvim/lua/dotfiles-palette.lua, target: colors.nvim.lua }`.
- Mirror it in `verify_consumer_symlinks`.
- Update the hardcoded consumer-list test in
  `tests/unit/test_v3_locality.py:90-105`.

### 4.4 dotfiles-assets

Replace the temporary Catppuccin selection with:

```lua
return {
  { "LazyVim/LazyVim", opts = {
    colorscheme = function()
      local ok, palette = pcall(require, "dotfiles-palette")
      if ok and type(palette.load) == "function" then
        palette.load()
      else
        require("catppuccin").load()
      end
    end,
  } },
}
```

- The module name is the only contract; no host path.
- Catppuccin remains the fallback for a fresh host before the first runtime
  seed (or a missing pointer).
- Update `lazy-lock.json` only if the plugin set changes; this slice does not
  add a plugin.

### 4.5 dotfiles-v3

- Pin the released tpr/runtime/engine/assets tags.
- Run `deploy-coverage` and the composition gates.
- No pin bump until the four upstream slices pass their own gates.

## 5. Acceptance

- [ ] `colors.nvim.lua` renders for dark and light modes, parses as Lua, and
      exposes `M.load()` plus the highlight table.
- [ ] The runtime publishes the artifact without changing the existing eight
      identities; `meta.json` records it.
- [ ] Provisioning exposes `config/nvim/lua/dotfiles-palette.lua` and verify
      asserts it resolves.
- [ ] LazyVim loads the generated colorscheme on next start; a missing pointer
      falls back to Catppuccin without an error.
- [ ] No assets config names a host path.
- [ ] Each repo's gates pass before any tag/release.

## 6. Risks / open questions

- **Mode semantics:** the runtime generation selects one palette mode. The
  editor follows the selected generation; live dark/light switching is out of
  scope.
- **Live reload:** a new palette applies on the next Neovim start. An RPC
  reloader is a separate design.
- **Highlight breadth:** the first slice covers the core editor, diagnostics,
  diff and common Treesitter groups. Plugin-specific groups can be added later
  without changing the artifact contract.
- **Contract impact:** the palette artifact set is runtime-owned, not the
  appearance contract; adding `colors.nvim.lua` should not widen
  `appearance.artifacts`. Confirm in the runtime slice.
