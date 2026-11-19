# 116 — Neovim skin appearance projection (REQ-124 design)

> **Status:** design record. No runtime, assets, contract, provisioning or
> composition change is part of this document. The implementation slices in §9
> are proposals for separate, gated repo changes; no tag, release, pin bump or
> host apply happens here.

## 1. Decision

**Yes, Neovim consumes the active skin appearance — for editor *chrome* only,
not for syntax.**

The editor already consumes the wallpaper palette through REQ-123
(`config/nvim/lua/dotfiles-palette.lua` → `colors.nvim.lua`). That palette owns
syntax, LSP, diagnostics, diff and terminal colours. It does **not** know
whether the selected skin is translucent glass, zero-chrome flat or opaque
terminal. The appearance generation does know that, and its resolved
`tokens.json` is already published for every generation. Reusing it lets the
same skin that changes the bar, GTK and rofi also change the editor's floats,
statusline, tabline, separators and Visual selection, while syntax remains
palette-driven.

**Artifact recommendation: reuse `current/appearance/tokens.json` through a
provisioning-owned stable link; no new contract artifact format.**

The link is the same mechanism already used for GTK/rofi/kitty/wlogout, and
`tokens.json` is already named by the frozen manifest field
`appearance.tokensPath` (`contracts/schemas/generation-manifest.schema.json:299-301`).
No `appearance.artifacts` enum change is needed, so there is no contracts
release and no release-metadata impact. This is the smallest honest extension
of the existing plane.

## 2. Evidence from the live plane

| Claim | Evidence |
| --- | --- |
| The generation requires one token document. | `contracts/schemas/generation-manifest.schema.json:294-301` — `tokensPath` is required and `const: "appearance/tokens.json"`. |
| Non-CSS format enum is `rasi \| conf \| theme`; no `json`/`lua`. | `contracts/schemas/generation-manifest.schema.json:255-286` — `artifact` requires `consumer`, `path`, `format`; enum at `:276-283`; path pattern at `:271-274`. |
| The runtime publishes and verifies the token document. | `dotfiles-runtime/src/runtime/adapters/appearance.py:71,474-479`; `generation_store.py:579-583,673` writes `tokensPath` into `manifest.json`. |
| The live generation names it. | `~/.local/state/dotfiles/current/manifest.json` → `"tokensPath": "appearance/tokens.json"`; `state/current` is one atomic generation pointer. |
| The live token document is resolved, not a skin manifest. | `~/.local/state/dotfiles/current/appearance/tokens.json` has `version: 2`, all six surface roles, state/type/ink/layout; mode and host defaults are already applied. |
| Provisioning owns stable links; Neovim already has one optional palette link. | `dotfiles-provision/ansible/roles/state_links/vars/main.yml:37-46` (required), `:53-54` (optional nvim palette); role loop at `tasks/main.yml:51,61`, resolve assertion at `:73-97`. |
| The palette module and SIGUSR1 reload already exist. | `dotfiles-assets/configs/nvim/lua/plugins/lazyvim.lua:1-15`; `dotfiles-assets/configs/nvim/lua/config/autocmds.lua:10-34`; `dotfiles-runtime/src/runtime/adapters/nvim_reloader.py:1-5,77-119`; wired last in `dotfiles-runtime/src/runtime/cli/main.py:481-483`. |
| Skin differences are real and tokenised. | `dotfiles-assets/skins/README.md:170-190` (glass/flat/paper/terminal/terminal-host token table); manifests under `dotfiles-assets/skins/manifests/`. |
| Palette-only would lose the distinction. | The palette has no surface/radius/opacity role; `glass` is `alpha(@surface, 0.94)` with `@primary` border, `flat` is `transparent`/border 0, `terminal` is opaque `@surface` with a 1px hairline (`skins/manifests/{glass,flat,terminal}.toml`). |

## 3. Rejected alternatives

| Alternative | Why rejected |
| --- | --- |
| **New `appearance.artifacts` format `json` (or `lua`)** | Widens the frozen enum (`rasi\|conf\|theme`), needs a contracts minor release, runtime suffix discovery, assets template/gate work, provisioning verification and a composition pin bump. It creates a second appearance truth even though `tokensPath` already names the canonical one. This is exactly the contract change this ticket is asked to avoid unless reuse is dishonest. |
| **A `lua` module generated per skin (REQ-123 shape)** | Duplicates the palette module and bakes skin + palette into one artifact. It would need `@role`/`alpha()` resolution at render time and would make a skin change and a palette change the same identity. It also adds a template per skin for data that already exists as JSON. |
| **`conf` / `rasi` / `theme` artifact** | These are flat, consumer-specific dialects (kitty key/value, rofi solid roles, btop hex keys). None can carry the nested `surface`/`state`/`type`/`ink` document, and `theme`/`conf` cannot reference palette roles without literal hex, which the skin plane forbids. |
| **Read the skin TOML from the assets corpus in Neovim** | The editor would have to implement mode selection, `[host]` resolution and fail-closed validation — runtime responsibilities — and would depend on a source path, not a generation. Rejected by the v3 generation-only model. |
| **Stay palette-only** | The palette cannot express float separation, statusline/panel paint, border presence or zero-chrome. The editor would be the only consumer ignoring the selected skin, which is the defect this ticket exists to decide. |
| **Read `current/appearance/tokens.json` by hard-coded absolute path** | The module name/link is the only contract (REQ-123 rule). A host path in the assets corpus is forbidden and would break XDG isolation. |

## 4. Artifact shape and delivery chain

### 4.1 Stable link

Provisioning adds one required consumer (tokens.json is mandatory in every v3
generation):

```yaml
# dotfiles-provision/ansible/roles/state_links/vars/main.yml
state_links_consumers:
  # … existing palette/appearance links …
  - { base: appearance, spine: nvim/lua/dotfiles-appearance.json, target: tokens.json }
```

Result:

```text
<install>/config/nvim/lua/dotfiles-appearance.json
  -> $XDG_STATE_HOME/dotfiles/current/appearance/tokens.json
$XDG_CONFIG_HOME/nvim -> <install>/config/nvim        # existing spine link
```

It is a **stable** link: it names `current`, never a generation hash. The
runtime never writes it; provisioning never repoints it. The required table is
the right family (not `state_links_optional_consumers`) because `tokensPath` is
a required manifest field: if the link is dangling, the generation is broken
and `verify` should say so. The existing resolve assertion already covers it
once it is added to `state_links_consumers`
(`dotfiles-provision/ansible/roles/state_links/tasks/main.yml:73-97`).

### 4.2 Neovim loader

`lua/dotfiles-appearance.lua` (new assets file) is a small, pure-ish module:

```lua
-- conceptual contract, not implementation
local M = {}

-- Read <config>/lua/dotfiles-appearance.json with vim.json.decode.
-- Return false when absent/invalid version/structurally invalid: palette-only.
function M.load() ... end

-- Apply only the chrome groups (table in §5) on top of palette.load().
function M.apply() ... end

-- Pure resolver, exported for headless fixture tests.
-- resolve(tokens, roles) -> { normal_bg=..., float_bg=..., statusline_bg=...,
--                             border="none"|"single", ... , provenance={...} }
function M.resolve(tokens, roles) ... end
```

- Path resolution is `vim.fn.stdpath("config") .. "/lua/dotfiles-appearance.json"`.
  No absolute path is stored in the assets corpus.
- `M.load()` fails soft: missing file, undecodable JSON, `version ~= 2`, a
  missing `surface.window` role, or an unknown expression → return `false` and
  leave the REQ-123 palette in force. It never invents a colour and never
  crashes startup.
- `M.apply()` is called **after** `palette.load()` so chrome overrides win.
- The palette module is the role source for `@role` expressions. This requires
  the tpr projection to expose the palette's role map (see §5.3): the current
  `M.palette` is a lossy subset and does not contain every role a skin may
  name (for example `paper` uses `@surface_container_lowest`). The first
  implementation slice adds the full role map additively; until then the
  loader uses a documented surface-role fallback and records a degradation.

### 4.3 Fallback order

1. Valid `dotfiles-appearance.json` → palette + skin chrome.
2. Missing/invalid appearance JSON → palette only (REQ-123), unchanged.
3. Missing palette module too → Catppuccin (existing REQ-123 fallback).
4. A single bad token (unknown role/expression) → keep the palette value for
   the affected group only; do not discard the whole skin.

### 4.4 Live reload

No new signal and no runtime change are needed. Every committed generation
(including a skin-only change) already runs the synchronous reloader chain,
and `NvimReloader` sends `SIGUSR1` to every `nvim`
(`dotfiles-runtime/src/runtime/cli/main.py:481-483`,
`nvim_reloader.py:77-119`). The existing `Signal` autocmd
(`autocmds.lua:26-30`) calls `reload_palette()`; the implementation extends that
function to also drop `package.loaded["dotfiles-appearance"]`, reload the JSON,
and re-apply chrome after `palette.load()`. The user command
`:DotfilesColorsReload` does the same. No polling and no second watch.

## 5. Mapping boundary

### 5.1 Ownership split

| Concern | Owner | Neovim effect |
| --- | --- | --- |
| Syntax, treesitter, LSP, diagnostics, diff, terminal 0–15 | **Palette (REQ-123)** | No change in this ticket. |
| `Normal`/body foreground | **Palette (REQ-123)** | `on_surface` stays the body ink. |
| Editor window/panel/card paint, float separation | **Appearance (this ticket)** | Chrome groups below. |
| Selection/hover/disabled state | **Appearance** | `Visual`, `CursorLine`, `PmenuSel`. |
| Statusline/tabline/separators | **Appearance** | Chrome groups below. |
| Window decoration/opacity/blur/shadow | **Compositor/terminal** | Not representable in a terminal editor; ignored. |
| Layer-shell/bar geometry (`layout.*`), pill/control metrics | **Apps** | Ignored. |

### 5.2 Neovim chrome mapping

The loader sets only these groups (everything else is palette/plugin-owned):

| Neovim group(s) | Appearance token | Notes |
| --- | --- | --- |
| `Normal` (bg only) | `surface.window.bg` | FG stays palette. `transparent` → palette background. |
| `NormalFloat` | `surface.card.bg` | `transparent` → `Normal` bg. |
| `FloatBorder` | `surface.card.border` | `transparent`/`none` → no border; width 0 → `none`. |
| `FloatTitle` | `state.selected.fill` / `ink` | Falls back to `ink.accent` when absent. |
| `Pmenu` | `surface.card.bg` | |
| `PmenuSel` | `state.selected.fill` / `ink` | |
| `PmenuThumb` | `ink.dim` | |
| `StatusLine` | `surface.panel.bg` / `ink.ink` | Bold when `type.font-weight >= 600`. |
| `StatusLineNC` | `surface.panel.bg` / `ink.dim` | |
| `StatusLineTerm` | same as `StatusLine` | |
| `TabLine` | `surface.card.bg` / `ink.dim` | |
| `TabLineSel` | `state.selected.fill` / `ink` | |
| `TabLineFill` | `surface.window.bg` | |
| `WinSeparator`, `VertSplit` | `surface.card.border` | Fallback `ink.dim`; width 0 → `ink.dim` (no border colour). |
| `Visual` | `state.selected.fill` / `ink` | Explicitly appearance, per requirement. |
| `CursorLine` | `state.hover.fill` | |
| `CursorLineNr` | `ink.accent` | |
| `LineNr` | `ink.dim` | |
| `SignColumn` | `surface.window.bg` | Keeps the gutter flush with the editor. |
| `Folded` | `surface.card.bg` / `ink.dim` | |
| `ColorColumn` | `state.hover.fill` | |
| `winborder` (`'winborder'` option, Neovim 0.11+) | `surface.window.border-width` / `surface.card.border-width` | 0 → `none`, any positive value → `single` (nearest built-in; radii have no editor equivalent). |

Not mapped: `Search`/`IncSearch`/`CurSearch`, `Diagnostic*`, LSP underlines,
`Diff*`, `Todo`, `Comment`/`String`/`Keyword`/… — all remain REQ-123 palette.

### 5.3 Resolving token expressions

`tokens.json` stores role expressions, not hex. The loader supports exactly
this subset and fails soft on anything else:

| Expression | Handling |
| --- | --- |
| `@role` | `palette.roles[role]` (full 50-role map; see below). |
| `alpha(@role, n)` | sRGB integer composite of the role over the current resolved background for that group (Normal bg for window/card, panel bg for statusline). This is a documented flattening, not real transparency. |
| `transparent` | For a window/panel/card background → the parent resolved bg (`Normal` for floats/statusline, palette background for `Normal`). For a border → no border. |
| `none` | Same as absent for that slot. |
| `auto` (`ink.ink-over`) | Not used by chrome; ignored. |
| numbers (`radius`, `padding`, `border-width`, sizes) | Only `border-width > 0` is used (as a border presence); the rest are ignored. |
| shadows (`0 10px 28px rgba(...)`) | Ignored. |

Role availability: the current `colors.nvim.lua` `M.palette` contains only the
roles REQ-123's highlight table needed (verified in the live artifact; e.g. it
has `surface_container_low` but not `surface_container_lowest`). The design
requires the tpr nvim projection to expose the **full palette role map** under
an additive key (recommended `M.roles`, keeping `M.palette` unchanged for
REQ-123 compatibility). This is a palette-artifact content change, not an
appearance contract change. If it is not ready in the first slice, the loader
ships an explicit fallback table for surface roles
(`surface_container_lowest` → `surface_container_low`, `surface_container_highest`
→ `surface_container_high`, `surface_dim`/`surface_bright` → `surface`,
`on_background` → `on_surface`) and records the degradation; it never guesses
hex.

### 5.4 Meaningful vs app-only skin tokens

| Token group | Terminal Neovim | Why |
| --- | --- | --- |
| `surface.window`, `surface.panel`, `surface.card` `bg`/`border` and `border-width` | **Meaningful** | Map to Normal/floats/statusline/separators/`winborder`. |
| `state.hover`, `state.selected`, `state.disabled` `fill`/`ink` | **Meaningful** | Map to CursorLine/Visual/PmenuSel/dim ink. |
| `ink.ink`, `ink.dim`, `ink.accent` | **Meaningful** | Chrome foreground and dim text. |
| `type.font-weight` | **Partially** | `>= 600` → `bold` on chrome groups only. |
| `type.font-family`, `size-*`, `letter-spacing` | **App-only** | The terminal owns the font; Neovim highlight groups cannot set family/size/tracking. (A future GUI client could consume them; out of scope.) |
| `surface.window.opacity`, `blur`, `shadow`, `radius`, `padding`; `surface.*.radius`/`padding` | **App/compositor-only** | No editor equivalent; opacity/blur belong to the terminal/compositor, radii/padding to GTK/layer-shell. Ignored, not faked. |
| `surface.pill`, `surface.control` metrics | **App-only** | Bar/rofi/GTK component shapes. |
| `layout.<app>` | **App-only** | Layer-shell geometry (`panel-width`, `card-width`, `root-height`); Neovim reads none of it. |
| `mode` | **Already resolved** | `tokens.json` has the selected mode applied; the editor follows the generation, not a second media query. |

## 6. Three-skin acceptance fixture

The fixture must prove the loader produces **different chrome from one
unchanged palette** for `glass`, `flat` and `terminal`, without a UI.

### 6.1 Expected differences

Resolved with the current `dark` mode and a fixed host snapshot
(`surface.window.radius=8`, `window.border-width=2`, `panel.radius=8`,
`panel.border-width=2`, `card/control/cell.radius=4`), reproducing the runtime's
mode-then-host precedence (`dotfiles-assets/scripts/validate-skins.py`,
`_resolve_manifest`):

| Chrome output | `glass` | `flat` | `terminal` |
| --- | --- | --- | --- |
| `Normal.bg` source | `surface.window.bg` = `alpha(@surface, 0.94)` | `surface.window.bg` = `transparent` → palette background | `surface.window.bg` = `@surface` |
| `NormalFloat.bg` | `alpha(@surface_container_high, 0.18)` | `transparent` → `Normal.bg` | `@surface_container` |
| Float/statusline border presence | yes (card border 1, panel 2) | no (border-width 0, `transparent`) | yes (1px `alpha(@on_surface, 0.22)`) |
| `StatusLine.bg` | `surface.panel.bg` = `alpha(@surface, 0.94)` | `transparent` → `Normal.bg` | `@surface` |
| `Visual.bg` / `.fg` | `@primary_container` / `@on_primary_container` | `@primary` / `@on_primary` | `@primary_container` / `@on_primary_container` |
| `winborder` | `single` (2 > 0) | `none` (0) | `single` (1 > 0) |
| `StatusLine` bold (`type.font-weight`) | no (400) | no (400) | no (500) |
| Ignored surface values | `radius 8`, `padding 11`, `opacity 0.94` | `radius 0`, `padding 11` | `radius 0`, `padding 9` |

The important assertion is relational, not pixel-perfect: with the same
palette, `flat` has no float/statusline separation, `glass` has a subtle
translucent card over the palette surface, and `terminal` has an opaque
surface-container card with a hairline border.

### 6.2 Headless verification

Fixtures (checked in with the implementation, not now):

```text
dotfiles-assets/tests/fixtures/nvim-appearance/
  glass.tokens.json      # copies of the resolved tokens (§6.1 inputs)
  flat.tokens.json
  terminal.tokens.json
  palette.roles.json     # the same palette role map for all three
  expected-chrome.json   # provenance + resolved values per skin
```

Run the pure resolver with no UI and no user config:

```bash
for skin in glass flat terminal; do
  nvim --headless --clean \
    -u NONE \
    --cmd "set rtp+=<assets>/configs/nvim" \
    -c "lua local a=require('dotfiles-appearance'); \
        local t=vim.json.decode(table.concat(vim.fn.readfile('tests/fixtures/nvim-appearance/${skin}.tokens.json'),'\n')); \
        local r=vim.json.decode(table.concat(vim.fn.readfile('tests/fixtures/nvim-appearance/palette.roles.json'),'\n')); \
        local c=a.resolve(t,r); \
        assert(c.provenance.statusline_bg == EXPECTED['${skin}'].statusline_bg); \
        assert(c.winborder == EXPECTED['${skin}'].winborder)" \
    -c 'qa!'
done
```

Assertions are on `resolve()` output (token provenance + resolved hex +
`winborder`), so a fixture failure names the token path rather than a diff
image. A second test loads the real generated `tokens.json` under an isolated
`XDG_STATE_HOME` and asserts `require("dotfiles-appearance").load()` returns
`false` (not an error) when the pointer is absent.

### 6.3 Documented visual mock

For review without a running loader, `docs/116-nvim-skin-mock.md` (a follow-up
fixture in the implementation slice, or an appendix here) records three
side-by-side captures of the same buffer/floats/statusline under `glass`,
`flat`, `terminal`. The mock is evidence of intent; the headless assertion in
§6.2 is the gate because it can run on a stock runner.

## 7. Risks and open questions

| Id | Risk / question | Handling |
| --- | --- | --- |
| A-1 | `tokens.json` uses `@role`/`alpha()`; Neovim must resolve them. | Bounded resolver in §5.3; fail soft; full role map from tpr. |
| A-2 | `alpha()` has no real transparency in a terminal highlight. | Documented flattening over the parent background; never claim real opacity. |
| A-3 | Palette module's role subset misses skin roles (e.g. `surface_container_lowest`). | tpr additive `M.roles`; explicit fallback table until it lands. |
| A-4 | Neovim has no radius/padding/shadow. | Ignore them; map border presence to `winborder` only. |
| A-5 | A skin change and a palette change share one `SIGUSR1`. | Reload both palette and appearance in the same handler; idempotent by file content. |
| A-6 | LazyVim/lualine may override statusline/tabline groups after the colorscheme. | Apply appearance after `palette.load()` and verify group values on `ColorScheme`/`VimEnter`; a lualine theme adapter is an optional second slice. |
| A-7 | Empty/partial generations (no appearance/tokens). | `M.load()` returns `false`; palette-only, never an error. |
| A-8 | The required provisioning link fails `verify` on hosts with a pre-v3 state. | tokens.json is required by the v3 contract; the existing absent-generation skip covers fresh hosts. Document rollback: remove the link with the provisioning rollback. |

## 8. Non-goals

- No syntax, LSP, diagnostics or terminal-colour change (REQ-123 owns them).
- No contracts change, no new artifact format, no enum widening.
- No runtime change: the generation, token publication and `SIGUSR1` reloader
  already exist.
- No Neovim GUI (neovide/nvim-qt) font/type work.
- No apply, release, tag or pin bump in this design phase.

## 9. Implementation slices (next, each separately gated)

Order matters: the loader and its link can land behind a fail-soft path before
the role map is complete.

1. **dotfiles-provision** — add
   `{ base: appearance, spine: nvim/lua/dotfiles-appearance.json, target: tokens.json }`
   to `state_links_consumers`; mirror the hardcoded consumer-count test
   (`tests/unit/test_v3_locality.py`). Gate: provisioning unit/verify tests.
   Release: provisioning minor.
2. **theme-producer** (palette, additive) — expose the full palette role map in
   `colors.nvim.lua` (recommended `M.roles`, `M.palette` unchanged); add a test
   that every `@role` used by the five bundled skins is present. Gate: tpr
   tests/lint and both palette modes. Release: tpr minor.
3. **dotfiles-assets** — add `lua/dotfiles-appearance.lua` (read/decode/validate,
   §5 mapping, `resolve()` for headless tests), call `appearance.apply()` after
   `palette.load()` in `lazyvim.lua`, and extend `autocmds.lua`'s
   `reload_palette()` to reload appearance too. Add the three-token fixtures and
   headless assertions from §6.2. No host path; `make gates` in assets.
4. **dotfiles-runtime** — no production change expected. Confirm (test) that a
   skin-only generation change still invokes `NvimReloader`; if the reloader
   list is gated on palette change, fix that with a test. No new signal.
5. **dotfiles-v3** — pin the released provisioning/tpr/assets/runtime tags, run
   `make deploy-coverage` and `make gates-ci`, and record the three-skin
   visual/headless evidence. This is the shipping step and is explicitly
   deferred until the user authorizes it.

## 10. Acceptance for this design

- [x] The editor follows skin appearance for chrome, with the palette boundary
      explicit.
- [x] The artifact decision reuses `tokens.json` through a provisioning link;
      no contract change is required.
- [x] The delivery chain (generation → stable link → loader → fallback → live
      reload) is defined.
- [x] A three-skin (`glass`/`flat`/`terminal`) token-level acceptance fixture
      and a headless verification method are defined.
- [x] No tag, release, pin bump, package install/apply, or UI worktree is
      touched.
