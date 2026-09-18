# ICME Redesign — UX Specification

**Author:** Sally (UX Designer, BMad) · **Date:** 2026-09-18
**Tool:** `src/gui-tools/icon-color-mapping-editor/` (Icon Color Mapping Editor)
**Companion mock:** `spikes/gui-unification/icme.html`
**Related:** `gui-unification-ux-spec.md` (shared language)

---

## 1. What ICME is, and the irony

ICME is the **authoring surface** for the desktop's icon recolouring system: pick a
shape, pick a palette swatch, save the `color_mappings`. Its users are you — a
power user editing the very palette that paints the desktop.

And it is the only GUI tool that **does not follow that palette**. Its stylesheet
is a hardcoded copy of a dark dev-tool theme:

| Role in ICME today | Literal | Should be |
|---|---|---|
| window / center surface | `#16181d`, `#191c22` | `@color_00` |
| side panels | `#1d2026` | raised surface from `@color_01` |
| raised controls | `#23272f` | `@color_01` |
| universal border | `#313742` | `alpha(@color_foreground, 0.12)` |
| primary text | `#d7dbe2` | `@color_foreground` |
| muted text | `#8b93a1` | `alpha(@color_foreground, 0.62)` |
| accent / selection | `#6ea8fe` (+ `#8fb8f5` hover) | `@color_10` (selection) |
| action / primary button | `#2c4b7c` | `@color_06` (action) |
| amber (warnings, bare) | `#e0a45e` | `@color_03` (caution) |
| green (templated) | `#7bc47f` | `@color_06` (positive/action) |
| red (errors) | `#e08585` | `@color_08` (or documented literal) |

So changing the wallpaper repaints the bar, rofi, pano, capture, selector,
notifications — and leaves the editor looking like a different machine.

**Design thesis:** the editor should be the *most* palette-literate window on the
desktop. It proves the system it edits. That is a genuinely delightful detail: you
recolour the wallpaper, the editor you edit colours in changes with it.

---

## 2. Where the shared language applies, and where it must adapt

ICME is a **full-window productivity tool**, not a floating overlay. The
`gui-unification` panel treatment (opaque `@color_01` + `@color_04` frame + 16px
radius) is designed for *overlays over the wallpaper*. For a 1280×800 tool:

- **Keep** the semantic vocabulary: selection = `@color_10`, action = `@color_06`,
  fields = solid `@color_01`, borders = hairline foreground, hover is quiet.
- **Adapt** the chrome: surfaces are palette-derived **layered neutrals**
  (`@color_00` base, raised panels from `@color_01` at low mix), plus a **subtle
  `@color_04` frame** so the window still belongs to the family. Full-bleed glass
  would hurt a dense tool.
- **Do not** use the floating-panel opacity — a text/diff-heavy editor needs
  opaque surfaces for legibility.

---

## 3. The palette-swatch tension (the key design constraint)

ICME's *content* is palette colours. Using palette colours for its *chrome* risks
confusing chrome with swatches. Rules to keep them distinct:

1. **Swatches are always inside a bounded cell** (grid cell / chip / named row)
   with a hairline frame; chrome is never a raw filled block of an arbitrary
   token.
2. **The current token is marked with the selection ring `@color_10` + a
   contrast-aware check glyph**, never by filling the cell (filling would hide the
   colour being chosen — the same "imagery gets a ring, not a coat of paint" rule
   from the shared spec §3.5).
3. **Selection accents are reserved for cursor/selection**, not for decoration, so
   a `@color_10` ring always means "this is chosen", never "this is a colour".
4. Missing tokens / not-in-`colors.yaml` use the caution treatment (`@color_03`
   tint + tag), which is already the tool's amber convention.

---

## 4. Layout (unchanged IA — this is a reskin + clarity pass)

The three-column IA is sound and stays:

```
┌──────────────┬────────────────────────────────────┬──────────────────────┐
│ INPUTS       │ canvas-bar: breadcrumb · mode ·     │ SELECTION            │
│ ─ manifest   │   [Show whole group][Bar bg][Close] │ ─ Shape/Placeholder/  │
│ ─ scheme     │                                     │   Maps to/Used by    │
│ ─ status     │  ┌──────┐ ┌──────┐ ┌──────┐         │ ── inspector nav ──   │
│ ─ tree       │  │vcard │ │vcard │ │vcard │         │ SHAPES               │
│   group      │  └──────┘ └──────┘ └──────┘         │ EDIT SCOPE           │
│   variant ●  │  ...                                │ palette swatches     │
│              │  ── diff ─────────────────────────   │ named tokens         │
│              │                                     │ [Revert][Save]       │
└──────────────┴────────────────────────────────────┴──────────────────────┘
```

### Improvements over the live UI

1. **Empty state guidance.** On open, the right panel shows four empty KV rows
   ("Shape —", "Placeholder —") and a greyed token grid with no instruction. Add a
   one-line prompt in the Selection pane: *"Select a shape in the preview, then
   pick a palette colour."* — the tool's whole flow in one sentence.
2. **Group tree active row** becomes the shared **solid selection fill** (rofi's
   row language); the templated/bare badge adapts to a translucent chip so it
   stays legible on the fill.
3. **Mode badges** (`templated` / `bare`) move from literal green/amber to
   palette roles: `@color_06` (positive/action) and `@color_03` (caution).
4. **Path fields** are solid `@color_01` fields (shared field rule); the editable
   one keeps a **`@color_04` accent border** instead of the amber `.rw` (amber is
   now reserved for caution, so it stops meaning two things).
5. **Scope toggles + view toggles** use the action-active role (`@color_06`
   tint + border), matching capture-tool.
6. **Primary "Save changes"** is the action-accent (`@color_06` fill, foreground
   text); **Revert** is a ghost button. Today's `#2c4b7c` reads as a generic
   dev-tool primary.
7. **Diff** keeps conventional add/remove semantics. Red/green are *content*
   semantics (like the LIVE badge): use `@color_08` for deletions and a
   documented literal green for additions if the palette lacks a green, and say so
   in a comment. Diff legibility outranks palette purity.
8. **The palette mismatch surfaced**: the live tool shows `accent`,
   `accent-muted`, `surface` rows as *"missing — not in colors.yaml"*. That is a
   real content bug (`defaults.yaml` maps to semantic keys the generator never
   emits), not a styling issue. The redesign should render these as an explicit
   **"unmapped semantic token"** state with a short explanation and a link to
   `defaults.yaml`, so the author understands why their icon didn't recolour.

---

## 5. States (shared vocabulary, adapted)

| State | Treatment |
|---|---|
| Active tree row / shape row | solid `@color_10`, text `@color_background` |
| Current token cell | `@color_10` 2px ring + contrast check (never a fill) |
| Current named-token row | `@color_10` ring + 12% tint |
| Current variant card | `@color_10` ring + 12% tint (was `#6ea8fe` border) |
| Toggle on (view/scope) | `@color_06` tint + `@color_06` border |
| Editable path field | solid `@color_01` + `@color_04` border |
| Read-only path field | solid `@color_01` + hairline |
| Warning / bare / missing | `@color_03` tint + text |
| Save error / scope warning | `@color_08` (or `#e08585` literal if contrast demands) |
| Primary button | `@color_06` fill, `@color_foreground` text |
| Ghost button | transparent + hairline, hover hairline-strong |

---

## 6. Cleanup this redesign should also do

The structural map found dead code; a reskin is the moment to retire it:

- Remove the unmounted `TemplatesTab.tsx` + its `.tabs/.tab*`, `.col.*`,
  `.app`, `.sel-info`, `.assign` CSS (or archive the feature deliberately).
- Fix the **near-duplicate amber** `.input-warn` `#e0a35e` vs `#e0a45e`.
- Add real rules for `.picker` and `.diff-pane` (applied but unstyled today), or
  drop the classes.
- Drop `.cell.missing` / `.diff-empty` if unused, or wire them.
- The window uses `#icme-window` while TSX also sets `class="icme-window"` with no
  rule — pick one convention.

---

## 7. What the mock must prove

1. The editor restyles with the wallpaper (flip the palette switch and the whole
   three-pane window follows) — with **zero** hardcoded chrome colours.
2. Palette swatches stay clearly distinguishable from chrome, and the current
   token is legible (ring + check, not fill).
3. The tool still reads as a dense, professional authoring surface — unified does
   not mean washed out.

## 8. Open decisions

- **D1 — accent frame on a full window:** subtle `@color_04` frame (recommended)
  vs none. *Mock shows the frame.*
- **D2 — tree row selection:** solid `@color_10` (recommended, rofi language) vs
  ring+tint (preserves badge colour without adaptation).
- **D3 — templated/bare badges:** palette roles (`@color_06`/`@color_03`) vs keep
  literal green/amber as semantic signals.
- **D4 — diff add/remove:** keep conventional green/red literals (recommended) vs
  force palette tokens.
