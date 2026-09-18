# GUI Unification — UX Specification

**Author:** Sally (UX Designer, BMad) · **Date:** 2026-09-18
**Status:** Draft for mock validation
**Scope:** rofi launcher, wallpaper-selector, hypr-pano, capture-tool, notifications
**Companion mocks:** `spikes/gui-unification/`

---

## 1. The problem, in one breath

Every GUI surface on this desktop drinks from the same well — one 16-colour palette
generated from the wallpaper — and yet they don't look like a family. Rofi reads as a
crisp, confident launcher: you can *see* where you are and *what is selected* at a
glance. The GTK tools read as soft, low-contrast glass: the palette is present but the
hierarchy is whispered.

Same colours. Different language.

That gap is not a palette problem. It is a **role-definition problem**: each tool decided,
on its own, what "a field", "selected", and "a panel" mean, and they all decided
differently.

---

## 2. Root cause (measured, not guessed)

| Element | Rofi (the reference) | GTK tools (today) | Consequence |
|---|---|---|---|
| Panel | opaque `@color01`, 4px `@color04` border | `alpha(@color_00, 0.92)`, hairline `alpha(fg, 0.12)` | rofi reads as a surface; GTK reads as a void |
| Search field | **solid filled** `@color01` | `alpha(@color_background, 0.5)` | GTK field reads as a *hole punched in the panel*, not a place to type |
| Selection | **solid fill** `@color10`, text flips to `@background` | accent tint `alpha(@color_06, 0.18)` + thin border | GTK selection is a whisper; rofi's is a statement |
| Selection hue | `@color10` | `@color_06` | two "chosen" colours on one desktop |
| Hover | (rofi is keyboard-select driven) | border shifts to `@color_04` | subtle, but the *only* affordance |

Two decisions account for most of the perceived difference:

1. **Fields are translucent holes instead of solid surfaces.**
2. **Selection is a tint instead of a fill** — and it uses a different accent slot.

---

## 3. Design principles (the rules that resolve future debates)

1. **One gesture per intent.** Every "chosen" thing — rofi row, selected card, segmented
   pill, active mode tab, clipboard card — uses the *same* selection gesture and the
   *same* accent slot. Consistency is the feature.
2. **Fields are surfaces, not holes.** An input sits *above* the panel as a filled
   surface, so it reads as "type here". Translucency is for the panel, never for a field.
3. **Selection is ink + fill, never a border whisper.** Hover may be quiet; selection
   must be unmistakable.
4. **Two accents, two intents — deliberately.** `@color10` means *"here is where you
   are"* (selection / focus). `@color06` means *"here is what you can do"* (primary
   action, active toggle). Never mix them.
5. **Imagery gets a ring, not a coat of paint.** When a surface contains a thumbnail,
   selection cannot be a solid fill (it would erase the content) — it becomes an accent
   ring + soft tint. Same accent, adapted gesture.
6. **The palette is the only ink.** No literal colours except semantic signals that must
   survive every wallpaper (the LIVE green, the recording dot) and brand app icons.
7. **Type may personalise the hue, never the gesture.** hypr-pano's clipboard cards keep
   per-type highlight colours; they must still use the shared ring+tint *treatment* so
   the system reads as one.

---

## 4. Semantic token map (v1)

Contract: mock variables `--color-*` map 1:1 onto runtime `@color_*`; rofi's
`@color00..15` / `@background` are the same slots. A palette swap restyles everything.

| Role | Slot | Treatment | Used by |
|---|---|---|---|
| `surface-panel` | `@color_00` / `@background` | `alpha(@color_00, 0.94)` glass; radius 16; border `1.5px @color_04` | all panels |
| `surface-frame` | `@color_01` | rofi's window fill (the sliver inside the border) | rofi |
| `surface-content` | `@color_00` / `@background` | rofi mainbox; GTK cards sit on the panel | rofi, card backgrounds |
| `surface-search` | `@color_01` | **solid**, radius 8, text `@color_foreground`, placeholder `alpha(@color_foreground, 0.55)` | rofi inputbar, ws-search, pano-search |
| `selection-fill` | `@color_10` | **solid fill**, text `@color_background`, radius 5 (rows) / 8–9 (pills) | rofi rows, segmented pills, mode tabs |
| `selection-ring` | `@color_10` | `2px` border + `alpha(@color_10, 0.12)` tint | cards with thumbnails |
| `selection-hover` | `@color_10` at 0.4 alpha | border only | cards |
| `action-primary` | `@color_06` | solid fill, text `@color_foreground` | CTAs (Take Screenshot, Apply) |
| `action-active` | `@color_06` | `alpha(@color_06, 0.18)` fill + `@color_06` border | toggle-on, active mode tab (where not the cursor's selection) |
| `hairline` | `alpha(@color_foreground, 0.12)` | 1px | card borders, dividers |
| `hairline-strong` | `alpha(@color_foreground, 0.22)` | 1px | neutral hover on outline buttons |
| `severity-caution` | `@color_03` | tint + border + text | critical notification tile, settings errors |
| `signal-live` | literal green | solid pill | wallpaper "LIVE" badge (must not follow palette) |

### Text-on-fill contrast rule

Selection flips text to `@color_background` (rofi's proven behaviour). Rule:

- Compute the contrast ratio of `@color_background` on the selection fill.
- If ratio ≥ 4.5:1 → use `@color_background`.
- Else → use `@color_foreground`.

**Open item (out of scope for the mock):** the generator could emit an
`--on-accent` token computed this way so the choice is decided once at generation
time instead of guessed per stylesheet. Current palette (dark `background`) passes
comfortably, so v1 hardcodes `@color_background` as rofi already does.

**Validated by the mocks — the two accents need different text rules.**
`@color_10` (selection) is bright by construction, so `@color_background` text reads
well. `@color_06` (action) is *not* guaranteed bright — in the live palette it is dark
steel `#2a496c`, so `@color_background` text on it fails contrast. Action text
therefore uses `@color_foreground`. This is exactly why the two accents carry distinct
roles instead of being collapsed into one.

---

## 5. Per-tool application

### 5.1 rofi launcher (the reference — keep, plus one fix)
- Keep: opaque `@color01` panel, `@color04` border, solid `@color10` selection with
  `@background` text.
- **Fix:** the search bar currently has no leading affordance (the prompt renders as an
  en-dash `"–"`). Rofi 2.0.0 supports an `icon` widget, so place the **same ITR
  `ui-search.svg`** the GTK tools use at the left of the entry via
  `inputbar { children: [ prompt-icon, entry ]; }`. Palette-themed automatically by ITR.
- Optional alignment: bring the panel radius to the GTK tools' 16px so windows match.

### 5.2 wallpaper-selector
- `surface-search`: translucent hole → **solid `@color_01`** (rofi's field).
- Panels already glass; move panel tint from `@color_00` to `@color_01` so the surface
  family matches rofi. Border stays hairline (it's a large window — a 4px accent frame
  would shout).
- Cards: selection = **ring `@color_10` + tint `alpha(@color_10, 0.12)`**; hover keeps a
  neutral hairline-strong. The `ws-quick` Apply pill uses `selection-fill` semantics
  (it is the cursor action on a card) — solid `@color_10`, text `@background`.
- The `LIVE` green and the amber deferral note stay literal (semantic).

### 5.3 hypr-pano
- `surface-search`: **solid `@color_01`**.
- Panel tint → `@color_01`.
- **Documented exception:** card selection keeps the *per-type* hue (text/code/colour/
  image/link/emoji tokens) but adopts the shared **ring + tint** gesture, so it still
  reads as the same system. Hover = neutral hairline-strong; selected = type-coloured
  ring + 12% type tint.
- Clear / Incognito buttons: treat as action/active roles (`@color_08`/`@color_01`
  currently) — align Clear to caution (destructive) and Incognito to `action-active`.

### 5.4 capture-tool
- Search n/a. Two changes for family consistency:
  - Mode switch (Screenshot/Recording): the *selected* mode is a selection → solid
    `@color_10` fill with `@background` text (currently an `@color_06` tint). Recording
    is differentiated by its icon + record dot, not a second hue.
  - Target tiles + segmented pills: selected = `@color_10` ring + 12% tint (tiles) /
    solid `@color_10` (pills).
  - Primary CTA stays `@color_06` (`action-primary`) — it is an action, not a selection.
  - Toggle-on stays `@color_06` (`action-active`).

### 5.5 notifications
- Cards keep `@color_00` glass. Tile/chips: success uses `action-active` (`@color_06`);
  critical keeps `severity-caution` (`@color_03`). Already close to spec — minor: hover
  strength aligned to the shared `selection-hover` formula.

---

## 6. Interaction states (shared vocabulary)

| State | Rows / pills | Cards |
|---|---|---|
| rest | transparent, `@color_foreground` | hairline border, card surface |
| hover | `alpha(@color_foreground, 0.08)` | border `hairline-strong` |
| selected / focus | solid `@color_10`, text `@color_background` | ring `@color_10` 2px + tint 12% |
| disabled / busy | 38% opacity, no pointer | 38% opacity |
| destructive | `@color_03` (caution) | `@color_03` ring |

Keyboard focus must always be as visible as pointer selection — no focus-only subtlety
(the rofi model: the cursor is always legible).

---

## 7. What the mocks must prove

1. All five tools, side by side, look like one product family across two different
   palettes.
2. Rofi's field + selection vocabulary is legible when transplanted into a card grid
   (ring, not fill) and into dense settings (pills).
3. hypr-pano's per-type selection still reads as "the same system, personalised".
4. Contrast holds for text on `@color_10` under both a dark and a light-ish palette.

## 8. Decisions the mocks put in front of juan david

- **D1 — Panel frame:** adopt rofi's accent frame (`1.5px @color_04`) on every tool vs
  keeping the hairline `alpha(fg, 0.12)`. *Spec recommends adopting the accent frame —
  this is the single biggest "these are siblings" cue.*
- **D2 — Panel border width:** 1.5px unified vs rofi's chunky 4px. *Spec recommends
  1.5–2px everywhere; rofi relaxes to 2px.*
- **D3 — Mode switch in capture:** solid `@color_10` selection vs keeping `@color_06`
  tint. *Spec recommends `@color_10`.*
- **D4 — Apply/quick pills:** solid `@color_10` vs outline. *Spec recommends solid.*
