# 113 — `surface.window` role and the kitty `conf` projection

> **Status:** design/contract proposal only (2026-11-11). No schema, runtime,
> assets, provisioning, live-config or tag change is part of this pass.
> **Approved decisions combined here:** **D4-B** (add `surface.window` now) and
> **D2-B** (project a paint-free kitty `conf` artifact).
> **Supersedes:** [`112`](./112-kitty-btop-window-roles.md) §3 (the decision to
> defer `surface.window`) and §6 (the font-family-only kitty slice). The
> evidence in 112 about units, btop and notification cards still stands.
> **Visual review:** [`design/window-role-kitty-projection.html`](./design/window-role-kitty-projection.html).
> **Tracking ticket:** [`tickets/REQ-113-window-role-kitty-projection.md`](./tickets/REQ-113-window-role-kitty-projection.md).

This note turns two approved decisions into one reviewable contract slice:

1. **D4-B** — `surface.window` becomes a real, required outer/toplevel surface
   role. It is not an alias for `surface.panel`; `panel` remains the
   layer-shell / in-app outer panel role.
2. **D2-B** — kitty gains one generated, paint-free `appearance/kitty.conf`
   artifact projecting font family, font size, window padding and background
   opacity. Colours stay the palette's job.

The two decisions meet at one token: `surface.window.opacity` is the explicit
opacity source for a real toplevel. Kitty is the first consumer; it is **not**
derived from a paint alpha.

---

## 1. Decision summary

| Question | Decision |
| --- | --- |
| Does `surface.window` exist? | **Yes, required in every skin.** Eight tokens: `bg`, `border`, `border-width`, `radius`, `padding`, `shadow`, `blur`, `opacity`. |
| Is it a rename/alias of `surface.panel`? | **No.** There is no runtime fallback, no alias placeholder and no “window if present else panel” rule. A missing window group fails closed. |
| Which consumers are `window`? | rofi outer `window`, wlogout outer `window`, GTK3/GTK4 `window` and `headerbar`. |
| Which consumers stay `panel`? | AGS bar/settings and every AGS layer-shell overlay surface. |
| Are notification cards `window`? | **No.** The layer-shell container is transparent; the visible notification is `surface.card`. |
| Is `surface.window.radius` / `border-width` host-inheritable? | **Yes.** They are added to the explicit `[host].inherit` allowlist. `surface.panel.radius` / `border-width` stay delegable for layer-shell panels. |
| Does `surface.window` change kitty colours? | **No.** `colors.kitty` remains the only colour artifact. The new `conf` artifact is paint-free. |
| Does btop change? | **No.** btop remains palette-only (D3-A). |
| Token model version | **Appearance token model v3**: manifest `schemaVersion: 3`, resolved `tokens.json` `version: 3`, `appearance.json` `version: 3`. |
| Contract release | **`contracts v0.12.0`** (breaking on the 0.x line; every consumer re-pins). |

---

## 2. `surface.window` — exact semantics and schema

### 2.1 Meaning

`surface.window` is the **outermost application surface that the compositor
manages as a window** — a toplevel or an app-owned outer shell that is
presented as a decorated/rounded window. It owns the outer paint, frame,
corner geometry, inner window padding, shadow, blur and toplevel opacity.

`surface.panel` is still the **outer panel/overlay surface that is not a
decorated toplevel**: the AGS bar, its settings surface, and AGS layer-shell
overlays. `surface.card` remains an inner card. `control`, `cell` and `pill`
are unchanged.

The distinction is semantic, not a size distinction:

| Role | What it describes | Typical host treatment |
| --- | --- | --- |
| `surface.window` | A real toplevel the compositor places, decorates and rounds | Compositor window rules, `decoration:rounding`, `general:border_size` |
| `surface.panel` | An app-owned outer panel or layer-shell surface | Layer-shell placement; may still echo host rounding |
| `surface.card` | An inner card/block inside a window or panel | App-owned; may opt into rectangle radii |
| `surface.control` | Button/entry/row action | App-owned |
| `surface.cell` | List row/tile | App-owned |
| `surface.pill` | Badge/capsule/chip | Explicit shape, never host-delegated |

### 2.2 Token set

```text
surface.window.bg            paint
surface.window.border        border paint
surface.window.border-width  non-negative number (px)
surface.window.radius        non-negative number (px)
surface.window.padding       non-negative number (px)
surface.window.shadow        shadow paint
surface.window.blur          none | blur(<n>px) [saturate(<n>)]
surface.window.opacity       number in [0, 1], unitless
```

Manifest shape:

```toml
[groups.surface.window]
bg = "alpha(@surface, 0.94)"
border = "@primary"
border-width = 1.5
radius = 12
padding = 11
shadow = "none"
blur = "none"
opacity = 0.94
```

`opacity` is a **new value type**, not a length. It is the only numeric token
that is neither `<n>px` nor unitless-with-a-special-CSS-position. The resolved
token document stores the number; CSS expansion (if a template ever uses it)
renders a bare unitless number, and `conf` expansion renders a bare decimal.
The contract clamps it to `[0, 1]`; it is never derived from an `alpha()` in
another token.

`surface.panel.opacity` is deliberately **not** added. Panel translucency is
already expressed by its paint; a second panel opacity would make it ambiguous
whether the value multiplies the paint or replaces it. Kitty is a toplevel, so
the window token is the honest source.

### 2.3 Why this passes the old W-1…W-6 criteria

Docs 112 required a real outer surface, distinct semantics, token
justification, a host-policy decision, migration/gates and no silent alias.
D4-B satisfies all six:

- **W-1** rofi, wlogout and GTK all paint real outermost windows/toplevels.
- **W-2** an OS-managed toplevel has different frame/decoration/opacity
  semantics than the AGS bar's layer-shell panel.
- **W-3** `opacity` is a token that neither panel nor card can honestly carry.
- **W-4** host delegation is explicit: window radius and border width only.
- **W-5** every skin, mode override, template, host map and validator migrates.
- **W-6** no alias; window is not a second name for panel.

---

## 3. Consumer mapping

### 3.1 Mapping table

| Consumer | Slot | Before | After | Notes |
| --- | --- | --- | --- | --- |
| rofi | `window` | `surface.panel.*` | **`surface.window.*`** | bg, border, border-width, radius, padding |
| rofi | `mainbox` | `surface.card.*` | `surface.card.*` | unchanged |
| rofi | `inputbar` | `surface.control.*` | `surface.control.*` | unchanged |
| rofi | `element` | `surface.cell.*` | `surface.cell.*` | unchanged |
| wlogout | `window` | `surface.panel.bg` | **`surface.window.bg`** | outer toplevel paint |
| wlogout | `button` | `card` fill/padding + `panel` radius/border-width | **`card` fill/padding/border paint + `window` radius/border-width** | action cards are inner cards inside a real window; their outer geometry follows the window role |
| GTK3 / GTK4 | `window` | `surface.panel.bg` | **`surface.window.bg`** | paint only; GTK does not emit an outer radius/border to avoid double-framing with the compositor |
| GTK3 / GTK4 | `headerbar` | `surface.card.bg` + `card` border-width | **`surface.window.bg` + `window.border-width` / `window.border`** | headerbar is toplevel chrome, not an inner card; this is the one deliberate visual delta in the built-in skins |
| GTK3 / GTK4 | `popover`, `.card` | `surface.card.*` | `surface.card.*` | unchanged |
| GTK3 / GTK4 | `button`, `entry` | `surface.control.*` | `surface.control.*` | unchanged |
| AGS bar / settings | `.settings-surface`, panel surfaces | `surface.panel.*` | `surface.panel.*` | layer-shell panel, not a decorated toplevel |
| AGS clipboard / capture / wallpaper-selector / icme / btop-studio | outer overlay surface | `surface.panel.*` | `surface.panel.*` | layer-shell overlays |
| AGS notifications | layer-shell container | transparent | **transparent** | not a window; it paints nothing |
| AGS notifications | `.notif-card` | `surface.card.*` | `surface.card.*` | cards on a layer-shell stack |
| AGS notifications | chips/badges | `surface.pill.*` | `surface.pill.*` | unchanged |
| kitty | terminal window | palette only | **palette + `window.opacity` + `window.padding` + `type.*`** | no `window.bg/border/radius/shadow/blur`; kitty's background is palette |
| btop | terminal TUI | palette only | **palette only** | no window projection (D3-A) |

### 3.2 Why notification cards are still not `window`

The notifications app creates an Astal layer-shell overlay, not a decorated
toplevel (`ags-notifications/ui/NotificationsWindow.tsx:963-967`). The visible
notification is `.notif-card`; the layer-shell window is only a transparent
hit/stack container. Giving that container `window` paint would paint the whole
screen; giving each card `window` would give an inner card an outer frame.
Both are wrong. The mapping stays: container transparent, card `surface.card`.

### 3.3 GTK headerbar decision

`headerbar` is part of the toplevel chrome, not an inner card. Mapping it to
`window.bg` and `window.border` makes the sheet semantically honest and lets a
skin tune toplevel chrome independently of cards. It also means glass/flat/
paper headerbars change appearance slightly (the card tint becomes the window
tint). This is called out as **OQ-1** for visual sign-off; the alternative is
to keep headerbar on `card`, which is a smaller visual change but leaves a
toplevel-chrome slot on an inner-card role.

---

## 4. Host delegation

### 4.1 Allowlist extension

`surface.window.radius` and `surface.window.border-width` are added to the
`[host].inherit` enum. The allowlist becomes exactly seven paths:

```text
surface.window.radius
surface.window.border-width
surface.panel.radius
surface.panel.border-width
surface.card.radius
surface.control.radius
surface.cell.radius
```

`surface.panel.radius` and `surface.panel.border-width` are **not removed**.
The AGS bar is a layer-shell outer panel and already follows host rounding; it
has no toplevel `window` element to remap. Keeping both means:

- toplevel consumers (rofi/wlogout/GTK) take geometry from `window`;
- layer-shell panels (AGS bar/settings) keep taking geometry from `panel`;
- no consumer uses both for the same slot.

`surface.window.padding` and `surface.window.opacity` are **not delegable**.
`surface.pill.radius` remains absent. The map version stays
`hyprland.paint.v1` (`HOST_MAP_VERSION = 1`): the source mapping for existing
paths is unchanged; the participating-path set and therefore `hostHash` change
only when a skin opts into the new paths.

### 4.2 Bounds and fallback

| Path | Hyprland source | Bounds |
| --- | --- | --- |
| `surface.window.radius` | `decoration:rounding` | `0..64` |
| `surface.window.border-width` | `general:border_size` | `0..16` |

Precedence is unchanged: **mode override > host > skin fallback**.
`fallback = "skin"` is still the default; `fallback = "error"` fails closed.
No paint, colour, padding, opacity, type or layout path becomes delegable.

### 4.3 No silent alias

- `surface.window` is never populated from `surface.panel` at runtime.
- `{{SKIN_SURFACE_WINDOW_*}}` has no fallback to `{{SKIN_SURFACE_PANEL_*}}`.
- A v2 manifest with no `window` group is rejected with a message naming
  `[groups.surface.window]`; it is not rendered with panel values.
- `surface.panel` is not deprecated. It keeps its own consumers.

The migration copies panel values into authored window groups **once, in the
manifest**, so the result is explicit and reviewable. A runtime derivation
would be the forbidden alias.

---

## 5. Contract and version changes

### 5.1 Release matrix (proposed, nothing tagged in this pass)

| Repo | Proposed release | Change |
| --- | --- | --- |
| `contracts` | **`v0.12.0`** | required window role, opacity type, seven-path host allowlist, schema v3, fixtures/docs |
| `ags-platform` | **`v1.1.0`** | `APPEARANCE_VERSION = 3`; window schema + opacity token kind |
| `dotfiles-runtime` | **`v1.5.0`** | v3 manifest/token support, window host paths, opacity renderer, `conf` px→pt renderer |
| `dotfiles-assets` | **`v0.19.0`** | window groups in all skins, template remaps, `kitty.conf.j2`, gates |
| `dotfiles-provision` | **`v0.1.63`** | kitty static include, `appearance.conf` stable link, verify |
| `dotfiles-v3` composition | **`v0.1.68`** | pin tuple, regenerate, live verification |

These are proposals, not tags. The real release is gated by the phases in §10.

### 5.2 Schema edits

`contracts/schemas/appearance-manifest.schema.json`

- `schemaVersion` const: `2` → **`3`**.
- `surfaceGroup.properties.window` = new `windowRole`; add `"window"` to
  `surfaceGroup.required`.
- New `windowRole` object with `additionalProperties: false`, required
  `bg`, `border`, `border-width`, `radius`, `padding`, `shadow`, `blur`,
  `opacity`.
- New `opacityValue`: `{ "type": "number", "minimum": 0, "maximum": 1 }`.
- `hostPolicy.inherit.items.enum`: add `surface.window.radius` and
  `surface.window.border-width`; keep the five existing paths.
- Descriptions: window is a real toplevel; opacity is unitless; window
  padding/opacity are not delegable.

`contracts/schemas/appearance-json.schema.json`

- `version` const: `2` → **`3`**.
- Same `surfaceGroup` / `windowRole` / `opacityValue` definitions.
- Description: six surface roles, opacity rendered unitless.

`contracts/schemas/appearance-artifact.schema.json`

- `version` const: `2` → **`3`**. The metadata shape is unchanged, but the
  artifact belongs to the v3 token model; keeping `2` would make the version
  claim misleading.

`contracts/schemas/generation-manifest.schema.json`

- `version` stays **3** (the generation unit shape is unchanged).
- `host.defaults` gains `surface.window.radius` (`0..64`) and
  `surface.window.border-width` (`0..16`); `additionalProperties: false`
  stays.
- The `appearance.artifacts` family is unchanged; `conf` is already reserved,
  so kitty needs no new format.

`appearance.md`, `skins.md`, `generations.md`, `CHANGELOG.md`

- Role table becomes six roles; window semantics, opacity type and the
  seven-path host allowlist are normative; migration and no-alias rules are
  explicit.

### 5.3 Consumer/parser changes

- `ags-platform/ports/appearance.ts`: `APPEARANCE_VERSION = 3`,
  `SURFACE_SCHEMA.window`, new `opacity` token kind with `[0,1]` bounds.
  Old apps must re-pin before a v3 generation reaches them; otherwise the
  version check fails loudly instead of partially reading the document.
- `dotfiles-runtime` vendored schemas re-pin; `MANIFEST_V2` becomes `V3`
  (v2 manifests fail with an explicit migration error). v1 remains the
  migration-only legacy path.
- Any strict JSON-schema validator in `dotfiles-assets` and
  `dotfiles-provision` re-pins the v0.12.0 bytes.

---

## 6. Skin manifest migration

### 6.1 Required group in every skin

All five built-in manifests gain `[groups.surface.window]`. Paper also gains a
complete `[mode.light.surface.window]` because a mode override replaces the
whole `surface` group.

Initial values copy the skin's panel values (explicitly authored) and add the
opacity decision:

| Skin | window `bg` | border / width | radius | padding | shadow / blur | opacity |
| --- | --- | --- | --- | --- | --- | ---: |
| `glass` | `alpha(@surface, 0.94)` | `@primary` / `1.5` | `12` | `11` | `none` / `none` | `0.94` |
| `flat` | `transparent` | `transparent` / `0` | `0` | `11` | `none` / `none` | `1.0` |
| `paper` | `@surface_container_lowest` | `alpha(@on_surface, 0.22)` / `1` | `6` | `11` | authored panel shadow / `none` | `1.0` |
| `paper` light | `mode.light.surface.panel.bg` | same as light panel border / width | `6` | `11` | same as light panel / `none` | `1.0` |
| `terminal` | `@surface` | `alpha(@on_surface, 0.22)` / `1` | `0` | `9` | `none` / `none` | `1.0` |
| `terminal-host` | `@surface` | `alpha(@on_surface, 0.22)` / `1` | `0` | `9` | `none` / `none` | `1.0` |

`glass` opacity `0.94` is an authored value chosen to match that skin's
translucent identity. It is **not** parsed from `alpha(@surface, 0.94)`.
If visual review prefers an opaque kitty window under glass, change the
authored token to `1.0` (OQ-3).

### 6.2 Host policy per skin

| Skin | window radius/border inherited? | panel rectangle host policy |
| --- | --- | --- |
| `glass` | yes (add both window paths) | unchanged |
| `paper` | yes (add both window paths) | unchanged |
| `terminal-host` | yes (add both window paths) | unchanged |
| `terminal` | no (`[host]`-free) | explicit |
| `flat` | no (`[host]`-free) | explicit |

`fallback = "skin"` stays. The `[host]` policy remains optional and
non-empty; an old policy naming only panel/card/control/cell paths remains
syntactically valid, though the shipped skins opt into window geometry.

### 6.3 Template placeholders

New placeholders are the normal flattened paths:

```text
{{SKIN_SURFACE_WINDOW_BG}}
{{SKIN_SURFACE_WINDOW_BORDER}}
{{SKIN_SURFACE_WINDOW_BORDER_WIDTH}}
{{SKIN_SURFACE_WINDOW_RADIUS}}
{{SKIN_SURFACE_WINDOW_PADDING}}
{{SKIN_SURFACE_WINDOW_SHADOW}}
{{SKIN_SURFACE_WINDOW_BLUR}}
{{SKIN_SURFACE_WINDOW_OPACITY}}
```

They are new names, not aliases. Existing `{{SKIN_SURFACE_PANEL_*}}`
placeholders keep their meaning and remain valid in panel consumers.

---

## 7. kitty projection (D2-B)

### 7.1 Artifact

- Skin template: `dotfiles-assets/skins/templates/kitty.conf.j2`
- Consumer: `kitty`
- Format: `conf`
- Runtime artifact: `appearance/kitty.conf`
- Generated text is **paint-free** and contains no literal colour. All colours
  remain in `current/colors.kitty` from the palette.

Template content (conceptual):

```text
# managed: generated appearance for kitty — paint-free
font_family {{SKIN_TYPE_FONT_FAMILY}}
font_size {{SKIN_TYPE_SIZE_BODY}}
window_padding_width {{SKIN_SURFACE_WINDOW_PADDING}}
background_opacity {{SKIN_SURFACE_WINDOW_OPACITY}}
```

The renderer, not the template, applies the px→pt conversion and strips the
unit. The template must not append `px` or `pt`.

### 7.2 Token map

| kitty option | Skin token | Rule |
| --- | --- | --- |
| `font_family` | `type.font-family` | first usable CSS family (below) |
| `font_size` | `type.size-body` | px → pt, bare number |
| `window_padding_width` | `surface.window.padding` | px → pt, bare number |
| `background_opacity` | `surface.window.opacity` | direct `[0,1]` number |
| all colours / ANSI / cursor / selection | palette `colors.kitty` | unchanged; not a skin token |

`surface.window.padding` is the outer window's inner padding, which is exactly
what kitty's `window_padding_width` is. `type.size-body` is the skin's body
text size, which is the terminal's text. No other chrome is projected:
`window_border_radius`, `window_border_width`, `window_margin_width`, cursor
shape/trail, tab bar and title bar stay app-owned or compositor-owned.

### 7.3 px → pt rule (normative)

Kitty lengths are **points**, and kitty's config parser accepts a bare number,
not a `px` or `pt` suffix. The live probe on kitty 0.50.0 is:

```text
BadLine(ValueError("could not convert string to float: '9px'"))
BadLine(ValueError("could not convert string to float: '12px'"))
font_size 9.0 / window_padding_width 8.25 / background_opacity 0.94 -> []
```

The conversion uses the CSS reference pixel at 96 dpi:

```text
1 CSS px = 1/96 in
1 pt     = 1/72 in
1 px     = 72/96 pt = 0.75 pt

font_size             = clamp(round_half_up(type.size-body        * 0.75, 2), 6.0, 36.0)
window_padding_width  = clamp(round_half_up(surface.window.padding * 0.75, 2), 0.0, 32.0)
```

- `round_half_up(x, 2)` rounds to two decimal places, ties away from zero.
- The rendered value is a bare decimal with trailing zeros stripped:
  `12 → 9`, `12.5 → 9.38`, `13 → 9.75`, `11 → 8.25`, `9 → 6.75`.
- Never emit `pt` or `px`; never use locale-dependent decimal separators.
- The clamps are presentation safety, not a contract change; the authored
  token remains the value in `tokens.json`.

The visible effect is intentional: a 12px body becomes 9pt, not kitty's 11pt
default. This is a design change that must be reviewed on the host (OQ-4).

### 7.4 Font-family rule (normative)

The skin value is a CSS family list, e.g.
`JetBrainsMono Nerd Font, monospace` or
`system-ui, "Cantarell", "Noto Sans", sans-serif`.

1. Split on commas, trim each entry, strip matching single/double quotes and
   CSS backslash escapes.
2. Drop CSS-wide keywords: `inherit`, `initial`, `unset`, `revert`,
   `revert-layer`.
3. Drop non-portable system keywords: `system-ui`, `ui-sans-serif`,
   `ui-monospace`, `ui-serif`.
4. Take the first remaining family. Generic families (`monospace`, `serif`,
   `sans-serif`) are legal kitty values and are kept if they are first.
5. If no family remains, emit `font_family monospace` (kitty's own default),
   never `inherit`.

Examples:

| `type.font-family` | projected |
| --- | --- |
| `JetBrainsMono Nerd Font, monospace` | `JetBrainsMono Nerd Font` |
| `inherit` | `monospace` |
| `system-ui, "Cantarell", "Noto Sans", sans-serif` | `Cantarell` |

The last case is a known risk: `Cantarell` is a UI font, not a terminal
monospace face. D2-B approved the first-family rule; if that is unacceptable,
a dedicated terminal family token is a separate contract decision (OQ-2).

### 7.5 Opacity rule

`background_opacity` is `surface.window.opacity`, clamped by the contract to
`[0,1]` and rendered as a bare decimal with at most three fractional digits.
It is never computed from `surface.window.bg`, `panel.bg`, an `alpha()` value
or the palette. A skin that wants an opaque terminal authors `1.0`; a skin
that wants glass authors the value it wants.

### 7.6 Runtime renderer

The existing `conf` format renderer fails closed on paint tokens. Extend it
with a format-specific numeric policy:

- `conf` length tokens → **pt bare number** via the rule in §7.3;
- `surface.*.opacity` → **unitless bare number** in every format;
- `font-weight` → unitless (unchanged);
- `letter-spacing` → `em` if ever used (unchanged);
- paint tokens in a `conf` template → fail closed with the existing
  `SKIN_PAINT_UNREPRESENTABLE` error;
- no `px`/`pt` suffix is ever emitted by the `conf` renderer.

`format: "theme"` stays reserved and unchanged. `format: "rasi"` stays
solid-role px geometry and unchanged. CSS stays byte-identical for every
existing token; only a template that newly uses `surface.window.opacity`
would see the unitless CSS rendering.

### 7.7 Static config, import order and reload

Provisioning renders `templates/kitty/kitty.conf.j2` (the static file, not the
skin template). The new order is:

```text
# managed by provisioning — do not edit; put customisations in local.conf
include <absolute current dir>/colors.kitty
include appearance.conf
include local.conf
auto_reload_config -1
```

- `colors.kitty` first: palette.
- `appearance.conf` second: generated skin projection.
- `local.conf` last: user overrides win.
- `auto_reload_config -1` stays; the runtime's `KittyReloader` sends
  `SIGUSR1`, reloading the included files for open windows. New windows read
  the same includes on start.

Provisioning owns one stable link, following the existing state_links shape:

```text
<install>/config/kitty/appearance.conf -> <state>/dotfiles/current/appearance/kitty.conf
```

`state_links_consumers` gains
`{ base: appearance, spine: kitty/appearance.conf, target: kitty.conf }`.
The link is created post-seed like rofi/GTK/wlogout; the runtime never writes
it. `kitty_config` still renders the static config and does not write under
the state root.

### 7.8 Validation

- **Assets gate:** render `appearance/kitty.conf` into a temp file and run
  `kitty +runpy` with `load_config(..., accumulate_bad_lines=b)`; assert
  `b == []`, no paint placeholder, and the expected `font_family`,
  `font_size`, `window_padding_width`, `background_opacity`.
- **Provisioning verify:** assert the rendered static `kitty.conf` includes
  `colors.kitty` first, `appearance.conf` second and `local.conf` last; assert
  the `appearance.conf` link resolves to `current/appearance/kitty.conf`; parse
  the full static config with `kitty +runpy`.
- **CI portability:** the pure renderer + schema gates always run. The
  `kitty +runpy` parse is a live-host gate; on a runner without kitty it must
  report an explicit skip, not a silent pass.

### 7.9 btop stays palette-only

No btop template, no `theme` artifact, no window tokens. The 48-key colour
theme remains the whole surface (D3-A, docs 112 §2). This decision is
unchanged by D4-B.

---

## 8. Compatibility and migration

| Artifact / consumer | v2 (today) | v3 (proposed) | Compatibility rule |
| --- | --- | --- | --- |
| Skin manifest | `schemaVersion = 2`, five roles | `schemaVersion = 3`, six roles | v2 rejected with a migration error; no window fallback |
| `tokens.json` | `version = 2` | `version = 3` | old parsers reject the version before reading roles |
| `appearance.json` | `version = 2` | `version = 3` | metadata follows the token model |
| Generation manifest | `version = 3` | `version = 3` | shape unchanged; `host.defaults` gains two optional keys |
| CSS targets | five-role placeholders | six-role placeholders | existing placeholders unchanged; new window placeholders added |
| rofi rasi artifact | panel for `window` | window for `window` | explicit template remap; same numeric values as panel in the initial migration |
| wlogout CSS | panel for outer/button geometry | window for outer/button geometry | explicit remap; card paint unchanged |
| GTK CSS | panel/card | window for window/headerbar | headerbar visual delta (OQ-1) |
| AGS CSS | panel/card | panel/card | unchanged |
| kitty | palette only | palette + `conf` | new artifact; colours unchanged; new link/import |
| btop | palette only | palette only | unchanged |

Migration steps, in order:

1. Land contracts v0.12.0 with schema v3, window role, opacity and host paths.
2. Land `ags-platform` v1.1.0 and runtime v1.5.0 together; neither emits/reads
   v3 alone.
3. Land assets v0.19.0: manifests, template remaps, kitty template, fixtures.
4. Land provisioning: static kitty include, stable link, verify.
5. Cut the composition pin; regenerate; verify. No dual-publish window.

Expected identity churn: every skin's resolved token document changes, so
every appearance and generation hash changes once. That is a one-time,
intentional migration, not drift.

---

## 9. Acceptance criteria

### Window role and contract

- **W-1** `surface.window` is required in every manifest and resolved token
  document, with exactly the eight tokens in §2.2.
- **W-2** `surface.window.opacity` is a unitless number in `[0,1]`; CSS
  expansion renders it unitless; no `alpha()` is parsed to derive it.
- **W-3** Manifest `schemaVersion`, token `version` and `appearance.json`
  `version` are all `3`; generation manifest stays `version: 3`.
- **W-4** `[host].inherit` accepts exactly the seven paths in §4.1;
  `surface.window.padding`, `surface.window.opacity` and
  `surface.pill.radius` are rejected.
- **W-5** A v2 manifest or a manifest missing `window` fails closed with a
  message naming the missing group; no panel→window alias exists.
- **W-6** `surface.panel` remains a distinct role with unchanged semantics and
  its existing consumers.

### Consumer mapping

- **W-7** rofi's outer `window` uses `surface.window.*`; `mainbox`,
  `inputbar` and `element` still use card/control/cell.
- **W-8** wlogout's outer `window` uses `surface.window.bg`; action buttons
  use card fill/padding/border paint and window radius/border-width.
- **W-9** GTK3/GTK4 `window` uses `surface.window.bg`; `headerbar` uses
  `surface.window.bg` + `window.border`; `popover`/`.card`/`button`/`entry`
  keep card/control.
- **W-10** AGS bar/settings and AGS overlay surfaces remain `surface.panel`;
  notification containers remain transparent and notification cards remain
  `surface.card`; pills remain `surface.pill`.
- **W-11** kitty consumes only `surface.window.opacity`,
  `surface.window.padding` and type tokens from the window projection; it does
  not consume window paint/border/radius/shadow/blur.

### Host delegation

- **H-1** A skin with `surface.window.radius` and
  `surface.window.border-width` in `[host].inherit` resolves both from
  Hyprland, with mode > host > skin precedence.
- **H-2** `glass`, `paper` and `terminal-host` opt into window geometry;
  `terminal` and `flat` stay `[host]`-free.
- **H-3** A host probe at a changed rounding/border value moves the window
  slots (rofi/wlogout/GTK) and leaves window padding/opacity, card, control,
  cell and pill unchanged.
- **H-4** The generation `host.defaults` records window values only when they
  participated; `hostHash`/`intent.host` follow.

### kitty

- **K-1** A paint-free `appearance/kitty.conf` is produced for consumer
  `kitty`, format `conf`; `colors.kitty` is unchanged and remains the only
  colour source.
- **K-2** `font_family` follows the first-usable-family rule in §7.4;
  `inherit` becomes `monospace`, never a literal `inherit`.
- **K-3** `font_size` and `window_padding_width` follow the exact px→pt rule
  in §7.3, emit bare decimals and respect the clamps.
- **K-4** `background_opacity` is exactly `surface.window.opacity`; no alpha
  derivation exists in code, tests or docs.
- **K-5** The static kitty config imports colours, then appearance, then
  `local.conf`, keeps `auto_reload_config -1`, and open windows reload via
  `SIGUSR1`.
- **K-6** The `appearance.conf` stable link resolves through
  `current/appearance/kitty.conf`; a missing link is a verify failure.
- **K-7** `kitty +runpy` parses the generated artifact and the assembled static
  config with zero bad lines; the gate is explicit-skip where kitty is absent.
- **K-8** btop ships no new artifact and remains palette-only.

### Migration, docs and gates

- **M-1** All five skins carry an explicit `window` group; paper's
  `mode.light` carries a complete `window` group.
- **M-2** No template references a panel token in a window slot and no
  window token falls back to panel.
- **M-3** The contracts/ags-platform/runtime/assets/provisioning/composition
  releases are sequenced as in §10; no production pin points at a branch.
- **M-4** The mockup is self-contained, uses the live dark palette, has no
  external assets/network, and is linked from `docs/design/README.md`.
- **M-5** `make gates-ci` is green in the docs worktree; no live apply is part
  of this slice.

---

## 10. Phased implementation order

| Phase | Repo(s) | Deliverable | Gate |
| --- | --- | --- | --- |
| **1. Contracts** | `contracts` | v0.12.0: schema v3, window role, opacity, seven-path host enum, generation host keys, docs, positive/negative fixtures | `make test`, schema fixture gate, tag v0.12.0 |
| **2. Runtime + parser** | `dotfiles-runtime`, `ags-platform` | v1.5.0 / v1.1.0: v3 accepted, v2 rejected with migration error, window host map/bounds, opacity renderer, `conf` px→pt renderer, platform window schema | runtime tests/lint/hermetic; platform tests/typecheck; paired release |
| **3. Assets** | `dotfiles-assets` | v0.19.0: window groups in every skin + paper light; rofi/wlogout/GTK remaps; `kitty.conf.j2`; `required_artifacts` kitty/conf; fixtures/README | `validate-skins`, `kitty +runpy` artifact gate, skin tests |
| **4. Provisioning** | `dotfiles-provision` | v0.1.63: kitty static include order, `appearance.conf` link, verify assertions/import-order gate | ansible lint, verify in temp XDG, no live apply |
| **5. Composition** | `dotfiles-v3` | v0.1.68: pin tuple, regenerate one generation, visual review, rollback note | `make gates-ci`, `dotfiles-provision verify`, host smoke |

No phase may skip backwards: assets may not ship a `kitty.conf.j2` before the
runtime can render `conf` points; provisioning may not link appearance before
the runtime publishes it; composition may not pin a runtime that emits v3
while any in-tree strict validator is still v2.

---

## 11. Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| v3 is a breaking token model | old apps/validators reject the generation | release tags are the sync boundary; platform + runtime pair first; loud version failure |
| px→pt changes perceived size | kitty body 12px becomes 9pt vs default 11pt | document the formula, review on host, clamp; OQ-4 can retune the token, not the formula |
| Font family is a UI family | flat/paper may project Cantarell (not monospace) | first-family rule is explicit; add a terminal family token only via a new contract decision (OQ-2) |
| Opacity changes glass kitty | window becomes translucent where it was opaque | glass authors `0.94` explicitly; OQ-3 can choose `1.0` |
| GTK headerbar visual delta | window chrome changes tint | mockup review; OQ-1 keeps `card` as the fallback choice |
| wlogout mixed mapping | button geometry from window but paint from card | explicit table + test asserts each slot's source |
| Host window paths double-count | window and panel both follow rounding | no consumer uses both for one slot; panel stays for layer-shell only |
| AGS apps go dark | old parser rejects v3 | platform v1.1.0 lands before runtime emits v3 |
| Missing kitty link | kitty warns and silently keeps defaults | provisioning verify asserts link + parse |
| Conf renderer leaks px | kitty parse failure | renderer test asserts bare decimals; `kitty +runpy` gate |

---

## 12. Open questions needing a user decision

1. **OQ-1 — GTK headerbar role.** Recommend `headerbar → surface.window`
   (toplevel chrome). Alternative: keep `surface.card` for visual parity.
   Which wins?
2. **OQ-2 — terminal font family.** D2-B's first-family rule can project a
   proportional UI font for flat/paper. Recommend keeping the rule for this
   slice and adding `type.font-family-terminal` only if a real terminal face
   is required. Approve the deferral?
3. **OQ-3 — glass opacity.** Recommend authored `surface.window.opacity =
   0.94` (matches the glass identity but is not derived). Alternative: `1.0`
   to keep kitty opaque. Which value ships?
4. **OQ-4 — px→pt tuning.** Recommend the exact `0.75` conversion with the
   §7.3 clamps, accepting 12px → 9pt. If that is too small, should the skin's
   `type.size-body` change, or should the conversion gain a scale factor
   (which would no longer be a pure unit conversion)?
5. **OQ-5 — panel host delegation.** Recommend keeping
   `surface.panel.radius`/`border-width` in the allowlist for the AGS bar
   while adding the window paths. Alternative: transfer host geometry
   exclusively to `window`, which would regress the bar. Confirm keep-both?
6. **OQ-6 — naming.** D4-B names the role `surface.window`; docs 111 asked
   whether `surface.outer` would be better. Recommend `surface.window` because
   the role means a real toplevel, and `panel` already covers non-toplevel
   outer surfaces. Confirm the final name before the contract tag.

---

## 13. Evidence

- Current five-role vocabulary and value types:
  `contracts/appearance.md:229-270`; host section `:301-350`.
- Current host allowlist and semantics:
  `contracts/schemas/appearance-manifest.schema.json` `hostPolicy`;
  `dotfiles-runtime/src/runtime/domain/host_defaults.py:25-46`.
- Current role discovery and format rendering:
  `dotfiles-runtime/src/runtime/adapters/skin_expander.py:108-123,368-414`.
- Current kitty static config:
  `dotfiles-assets/templates/kitty/kitty.conf.j2`;
  `dotfiles-provision/ansible/roles/kitty_config/`.
- Kitty point/px probe (kitty 0.50.0):
  `font_size 9.0` and `window_padding_width 8.25` parse with `b == []`;
  `9px`/`12px` are `BadLine(ValueError(...))`.
- Consumer templates:
  `dotfiles-assets/skins/templates/rofi.rasi.j2`,
  `wlogout.gtk.css.j2`, `gtk3.gtk.css.j2`, `gtk4.gtk.css.j2`,
  `ags-notifications.gtk.css.j2`.
- Notification layer-shell evidence:
  `ags-notifications/ui/NotificationsWindow.tsx:963-967`.
- btop palette-only evidence: docs 112 §2 and
  `theme-producer/src/theme_producer/adapters/projections/btop.py`.
- Reloaders:
  `dotfiles-runtime/src/runtime/adapters/kitty_reloader.py`,
  `btop_reloader.py`.
- Prior decisions:
  [`109`](./109-hyprland-host-defaults.md) (host defaults),
  [`110`](./110-format-aware-skin-consumers.md) (format families),
  [`111`](./111-host-radius-granularity.md) (rectangle radii),
  [`112`](./112-kitty-btop-window-roles.md) (palette/unit evidence).
