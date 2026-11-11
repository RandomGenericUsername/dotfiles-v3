# 112 — kitty/btop projection and the `surface.window` question

> **Status:** design/investigation only (2026-11-11). No schema, runtime,
> assets, provisioning or live-config change. Visual review artifact:
> [`design/kitty-btop-window-roles.html`](./design/kitty-btop-window-roles.html).
>
> **Superseded in part (2026-11-11):** approved decisions D4-B and D2-B reverse
> this document's deferral of `surface.window` and its font-family-only kitty
> slice. See [`113`](./113-window-role-kitty-projection.md) for the approved
> window role, host delegation, skin migration and full kitty `conf`
> projection. The unit/btop/notification evidence below still stands.

This note answers three questions that were left open by
[`110`](./110-format-aware-skin-consumers.md) and
[`111`](./111-host-radius-granularity.md):

1. How much of a skin can kitty take today, beyond the palette?
2. Is btop anything other than palette-only?
3. Is a new `surface.window` role needed, or is the current `surface.panel` =
   outer / `surface.card` = inner split already the right model?

The short answers are: **kitty is palette-only today and only `font_family` is
honest without a unit rule**, **btop stays palette-only**, and **no
`surface.window` role is needed now** — `surface.panel` is the outer role and
`surface.card` is an inner card, including notification cards.

---

## 1. kitty — current behaviour and projection candidates

### 1.1 Confirmed current behaviour

The provisioned config includes the runtime palette and nothing else:

```text
dotfiles-assets/templates/kitty/kitty.conf.j2:1-4
# managed by provisioning — do not edit; put customisations in local.conf
include {{ kitty_config_state_current_dir }}/colors.kitty
include local.conf
auto_reload_config -1
```

Evidence on the live host (read-only):

```text
$ cat ~/.config/kitty/kitty.conf
# managed by provisioning — do not edit; put customisations in local.conf
include /home/inumaki/.local/state/dotfiles/current/colors.kitty
include local.conf
auto_reload_config -1

$ kitty +runpy 'from kitty.config import load_config; b=[]; o=load_config(".../kitty.conf", accumulate_bad_lines=b); print(b, o.background, o.font_family, o.font_size, o.window_padding_width, o.background_opacity)'
[] Color(17, 19, 24) monospace 11.0 FloatEdges(left=0, top=0, right=0, bottom=0) 1.0
```

That is the whole projection today: the palette's `background`/`foreground`/
`cursor`/ANSI table/selection. The font, padding, opacity and chrome are
kitty's own defaults (`monospace`, `11pt`, `0`, `1.0`). New windows inherit
the `include`; open windows are refreshed by the runtime.

`KittyReloader` enumerates `pgrep -x kitty` and sends `SIGUSR1`, so every open
kitty reloads the included palette:
`dotfiles-runtime/src/runtime/adapters/kitty_reloader.py:1-9,77-116`.
Reload is event-driven; `auto_reload_config -1` deliberately disables kitty's
own watcher because the runtime replaces a symlink, not watched content
(`docs/handoffs/HANDOFF-kitty-terminal-colors.md` §5).

### 1.2 What is feasible in `kitty.conf` beyond palette

The skin vocabulary is `surface.{panel,card,cell,control,pill}`, `state`,
`type` and `ink` (`contracts/appearance.md:234-270`). kitty is a terminal
emulator with its own chrome options. The question is not “does kitty have a
knob?” but “does the skin token mean the same thing, in a legal unit?”.

| Candidate | kitty option | kitty unit | Nearest skin token | Verdict | Why |
| --- | --- | --- | --- | --- | --- |
| ANSI/fg/bg/cursor/selection | `color0..15`, `foreground`, `background`, `cursor`, `selection_*` | literal hex | palette, not skin | **Already shipped** (`colors.kitty`) | Palette is the producer; the skin plane forbids literal hex (`SC-5`). |
| Font family | `font_family` | font spec / string | `type.font-family` | **Honest, but needs a mapping rule** | Verb­atim string is legal. The skin value is a CSS family list (`"JetBrainsMono Nerd Font, monospace"`); kitty wants one family/spec, so a rule must take the first family or a dedicated terminal family token must exist. No such template ships today (`skins/schema.json:131-136` requires only `rofi/rasi`). |
| Font size | `font_size` | **points** | `type.size-*` | **Not honest yet** | The expander renders skin lengths as `12px`; `font_size 12px` is a parse error (probe below). A px→pt rule would also change the perceived scale: terminal's body is 12px (9pt at 96dpi) versus kitty's 11pt default. |
| Window padding | `window_padding_width` | **points** | `surface.panel.padding` | **Not honest yet** | Same `px` mismatch; additionally this is terminal cell padding between text and the window border, not an app panel's inner rhythm. |
| Background opacity | `background_opacity` | unitless 0–1 | `surface.panel.bg` alpha | **Not representable** | Some skins use `alpha(@surface, 0.94)`; others use opaque roles. There is no opacity token, and deriving a float by parsing paint expressions would be a palette-aware projection, not a skin token. |
| Window border radius | `window_border_radius` | px or pt | `surface.panel.radius` | **App-owned / redundant** | It rounds kitty's *internal* split borders, not the compositor window. Hyprland already owns the real outer rounding; mapping it here would double-frame. |
| Window border width | `window_border_width` | px or pt | `surface.panel.border-width` | **App-owned** | It separates split windows, not the outer panel frame. |
| Window margin | `window_margin_width` | points | none | **App-owned** | No token, and it is layout, not skin paint/rhythm. |
| Cursor shape / trail | `cursor_shape`, `cursor_trail*` | enum/floats | none | **App-owned** | The skin has no cursor-shape token; only the cursor *colour* is palette. |
| Tab bar colours | `active_tab_*`, `inactive_tab_*`, `tab_bar_background` | literal hex | palette, not skin | **Palette-only, not skin** | These could be added to the palette artifact, but they are colours. The skin plane has no tab token. |
| Tab bar shape | `tab_bar_style`, `tab_powerline_style`, `tab_bar_edge` | enum | none | **App-owned** | No token; style is structure/chrome. |
| Window title bar | `window_title_bar_*` | paint/enum | none | **App-owned** | OS decoration; no skin token. |

Unit probes on kitty 0.50.0:

```text
$ kitty +runpy '... load_config("kitty_units.conf", accumulate_bad_lines=b) ...'
# file: window_padding_width 9px / font_size 12px
[BadLine(number=1, line='window_padding_width 9px', exception=ValueError("could not convert string to float: '9px'")),
 BadLine(number=2, line='font_size 12px', exception=ValueError("could not convert string to float: '12px'"))]
```

The runtime already fails closed on paint in a `conf` target:
`dotfiles-runtime/src/runtime/adapters/skin_expander.py:392-414` substitutes an
unrepresentable marker and the template gate rejects it; the assets gate mirrors
this at `dotfiles-assets/scripts/validate-skins.py:865-870`. A `conf` artifact
can therefore carry type/geometry only, and only if the units are legal.

### 1.3 Decision for kitty

- **Keep kitty palette-only in this slice.** The palette projection is live,
  reloaded, and complete for colours.
- **The format target is `conf`, output `appearance/kitty.conf`**, named
  `<consumer>.conf.j2` (`docs/110` §3.1). It is reserved in
  `skins/schema.json:131-136`; only `rofi/rasi` is required today.
- **A future minimal slice may project `font_family` only.** It needs no unit
  rule and no paint, but it does need:
  1. a documented mapping from the CSS family list to one kitty family/spec;
  2. a `kitty.conf.j2` template that references only `SKIN_TYPE_FONT_FAMILY`;
  3. an `appearance.conf` consumer link and a launch/live lane decision.
  Everything else (size, padding, opacity, borders, cursor shape, tab chrome)
  stays app-owned until a unit/opacity contract exists.
- Do **not** project `type.size-*` or `surface.*.padding` by appending `px`:
  kitty rejects it (probe above). A px→pt rule is a contract change, not a
  template tweak.

---

## 2. btop — palette-only, permanently

### 2.1 Confirmed surface

`theme-producer` emits exactly 48 colour keys:
`theme-producer/src/theme_producer/adapters/projections/btop.py:24-102`
(`BTOP_KEYS`) and resolves each to a palette `MaterialRole`
(`:104-137`, `:147-152`). The emitted file is `theme[key]="#rrggbb"` only.

The managed btop config sets exactly two settings:

```text
dotfiles-assets/templates/btop/btop.conf.j2:48-49
color_theme = "{{ btop_config_active_theme }}"
save_config_on_exit = false
```

btop has no include mechanism, no skin variables and no theme keys for radius,
padding, font family or font size. `color_theme` selects a theme file by
filename from the scanned theme directory; a miss silently falls back to
`Default_theme` (documented at `btop.conf.j2:11-33`). The runtime refreshes an
open btop with `SIGUSR2`:
`dotfiles-runtime/src/runtime/adapters/btop_reloader.py:1-40,105-146`.

### 2.2 Candidate matrix

| Candidate | btop surface | Verdict |
| --- | --- | --- |
| Paint / ANSI-ish terminal colours | 48 `theme[...]` hex keys | **Palette only** (`colors.btop.theme`) |
| Corner radius | none | **Not applicable** |
| Padding / spacing / rhythm | none (btop's own box layout) | **Not applicable** |
| Font family / size | none (the host terminal owns the font) | **Not applicable** |
| Graph symbols / presets / update interval | `btop.conf` settings | **App-owned config**, not skin |
| Transparency / blur / shadow | none (terminal compositing) | **Not applicable** |
| Selection/hover semantics | fixed btop key roles (`selected_bg/fg`, `proc_*`) | **Palette mapping**, already encoded in `BTOP_KEY_ROLES` |

**Decision:** btop remains palette-only. A skin `.theme` output would require
literal hex for every key — that is the palette's job, not the skin's — and the
remaining knobs have no skin tokens. There is no meaningful btop projection
beyond the palette.

---

## 3. `surface.window` — role review and decision

### 3.1 The roles are already distinct

| Role | Contract meaning | Real consumers |
| --- | --- | --- |
| `surface.panel` | **outer** panel/window surface: paint, frame, radius, padding, shadow, blur | AGS bar settings panel (`.settings-surface`, `ags.gtk.css.j2:68-75`), rofi `window` (`rofi.rasi.j2:18-24`), wlogout `window` (`wlogout.gtk.css.j2:2-4`) |
| `surface.card` | **inner** card/panel: notification cards, dialog cards, inner content blocks | `.notif-card` (`ags-notifications.gtk.css.j2:22-28`), rofi `mainbox` (`rofi.rasi.j2:26-31`), wlogout action-card fill (`wlogout.gtk.css.j2:6-12`, with panel geometry by explicit mapping) |
| `surface.control` | compact interactive control: button/entry/row action, own type | rofi `inputbar`, AGS settings buttons, notification footer controls |
| `surface.cell` | list row/tile, own hover paint | rofi `element`, AGS list rows/tiles |
| `surface.pill` | badge/chip/capsule, own type/tracking | notification chips/badges, AGS pills |
| `surface.window` | **does not exist** | none |

The contract names five roles and no outer-card role:
`contracts/appearance.md:239-250`.

### 3.2 Why notification cards are `card`, not an outer surface

The notifications app creates an Astal **layer-shell overlay**, not a painted
toplevel:

```text
ags-notifications/ui/NotificationsWindow.tsx:963-967
<window name="notifications-window" class="notifications-window"
        anchor={TOP | RIGHT} layer={Astal.Layer.OVERLAY}
        keymode={Astal.Keymode.ON_DEMAND} ...>
```

The generated stylesheet states the consequence directly:

```text
dotfiles-assets/skins/templates/ags-notifications.gtk.css.j2:4-5
Notifications are cards, not windows: the card takes
surface.card.bg/surface.card.radius/...
```

The layer-shell window itself is only a transparent hit/stack container; the
visible notifications are `.notif-card` elements. Using `panel` for them would
give every card the outer-window frame/shadow, and using a hypothetical
`window` role would still describe the wrong thing: the card is an inner card,
not the outer shell.

### 3.3 Criteria for ever adding `surface.window`

Add it only if **all** of these hold:

- **W-1 Real outer surface.** At least one consumer paints an actual outermost
  toplevel/window surface, not a transparent layer-shell stack or an inner
  card.
- **W-2 Distinct semantics.** `surface.panel` cannot honestly describe it —
  for example, an OS-managed toplevel needs different frame/shadow/decoration
  behaviour than an in-app panel. “The word window appears in the source” is
  not enough.
- **W-3 Token justification.** It needs at least one token that is not already
  panel/card semantics (paint, radius, shadow, padding, blur) and a reason a
  consumer cannot map to `panel`.
- **W-4 Host policy decision.** State explicitly whether any `window` token is
  host-inheritable; the default is no (see §3.4).
- **W-5 Migration and gates.** A contract release, every skin/mode migration,
  runtime/assets version bump, consumer remapping and a negative fixture.
- **W-6 No silent alias.** If it is only a rename of `panel`, do not add it;
  document the alias instead.

### 3.4 Decision

**Recommendation (a): no new role now.** `surface.panel` is the outer surface
and `surface.card` is an inner card. This is not a naming bug: the current
consumers all map honestly, and the notification case is explicitly “cards,
not windows”. A new role would duplicate `panel` for every existing consumer
and force a migration with no behavioural gain.

`surface.window` stays **deferred**, not rejected, and may be revisited only
when W-1…W-6 are met. The trigger is a genuine painted toplevel with different
semantics — for example, if notifications are promoted from a layer-shell card
stack to a real decorated toplevel that owns its own outer frame. Until then:

- no schema/token addition;
- no new host-inheritable path;
- no consumer remapping;
- `surface.panel` remains the only outer surface role.

If the trigger ever fires, the first question is whether it should be named
`surface.window` or `surface.outer` (`docs/111` open question 3), because
wlogout-style action cards may also need the distinction.

---

## 4. Criteria and acceptance for this design

- **K-1** The kitty config still includes `current/colors.kitty`, new windows
  read it, and open windows reload via `KittyReloader`/`SIGUSR1`.
- **K-2** No kitty skin artifact ships in this slice; the `conf` target stays
  reserved.
- **K-3** The design records the `px` vs `pt` blocker with a parse probe, not
  an assumption.
- **B-1** btop remains palette-only; the 48-key colour table is the whole
  theme surface.
- **W-1** `surface.panel` is documented as the outer role; `surface.card` is
  documented as an inner card.
- **W-2** Notification cards are recorded as cards on a layer-shell container,
  not as an outer window.
- **W-3** No `surface.window` schema, token, host path or consumer mapping is
  added.
- **D-1** The mockup is self-contained, uses the live dark palette and no
  external assets, and is linked from `docs/design/README.md`.

## 5. Open questions

1. **kitty `font_family` mapping.** Should the expander take the first family
   from the CSS list, or should terminal skins gain a dedicated
   `type.font-family-terminal` token? The former is smaller; the latter is
   explicit about the different grammar.
2. **kitty px→pt rule.** Is a documented 1px = 0.75pt (96dpi CSS px) mapping
   acceptable for `font_size`/padding, or does kitty stay type/geometry-free
   indefinitely? Recommendation: defer; the terminal's 12px body maps to 9pt
   versus kitty's 11pt default, so this is a visible design decision.
3. **kitty tab bar palette.** Should palette artifacts gain tab colours
   (`active_tab_*`, `inactive_tab_*`, `tab_bar_background`)? That is palette
   enrichment, not a skin projection, and should be proposed by the palette
   producer.
4. **`surface.window` trigger.** Does any consumer plan to promote
   notifications from layer-shell cards to a real decorated toplevel? If yes,
   start the contract proposal and answer W-1…W-6; if no, keep it deferred.
5. **Naming.** If the role is ever needed, is `surface.window` or
   `surface.outer` the honest name for an outer surface that includes non-
   toplevel cases?

## 6. Next implementation slice (if any)

- **kitty:** optional, smallest honest slice — add an assets-only
  `kitty.conf.j2` that projects **`font_family` only**, with the first-family
  mapping documented, register `kitty/conf` in the assets required artifacts,
  and add a `kitty +runpy` parse gate. It must not touch `font_size`, padding,
  opacity or chrome, and it needs a provisioning link decision before it can
  be live. **No runtime or schema change.**
- **btop:** no slice. Palette-only is the final state.
- **`surface.window`:** no slice. Keep the deferred decision and revisit only
  on the W-1 trigger.

No live config, assets value, schema, runtime, provisioning or tag changes are
part of this design pass.
