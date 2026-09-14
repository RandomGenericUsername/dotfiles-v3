## Context

CSG renders one artifact per requested format with
`template_name = f"colors.{fmt.value}.j2"` and
`output_path = output_dir / f"colors.{fmt.value}"`
(`adapters/local_processor.py`). Formats are a **closed enum**
(`domain/enums.py`):

```
JSON=json, SH=sh, CSS=css, GTK_CSS=gtk.css, ADW_CSS=adw.css,
YAML=yaml, SEQUENCES=sequences, RASI=rasi, SCSS=scss, HYPRLAND=conf
```

`TemplateCatalogService.derive` (`domain/services.py`) raises
`TemplatesValidationError` for any `colors.<key>.j2` whose `<key>` is not in
`ColorFormat`; `OutputSettingsSchema._validate_default_formats` (`adapters/settings/schema.py`)
validates `default_formats` against the same set. `conf` is **Hyprland**
(`$name = rgb(rrggbb)`), not a terminal.

## Goals / Non-Goals

**Goals**
- A `kitty` format exists, renders valid kitty syntax, and is discoverable by the
  catalog and the CLI like any sibling.
- Zero behavioural change to existing formats.

**Non-Goals**
- Runtime consumption, reload, provisioning, or kitty.conf (sibling changes).
- A generic "arbitrary template" escape hatch — out of scope; the enum stays the
  authority.

## Decisions

### D1. Add to the closed `ColorFormat` enum (a custom template cannot work)
Verified: the catalog loader rejects unknown formats, so `colors.kitty.j2` in a
user templates dir would fail validation. The enum is the single authority.

### D2. Plain kitty syntax (`key #rrggbb`), not `$var = rgb()`
Verified against kitty 0.48.2: `$color0 = rgb(...)` is rejected
(`Ignoring invalid config line`). The template emits:
```
background #rrggbb
foreground #rrggbb
cursor #rrggbb
color0 #rrggbb
...
color15 #rrggbb
selection_background #rrggbb
selection_foreground #rrggbb
```
Colours come from the same `ColorScheme` model used by `colors.rasi.j2` /
`colors.sequences.j2` (`background`, `foreground`, `cursor`, `colors[0..15]`), so
the kitty artifact can never drift from the other consumers.

### D3. Selection colours from the palette, not invented
`selection_background` = `background`, `selection_foreground` = `foreground`
(a readable default from the same palette); no new colour derivation is
introduced. If a dedicated token is wanted later it is a separate change.

### D4. No metadata in the fragment
kitty parses every line strictly, so the fragment carries **only** supported
colour keys — no `generated-at`/`source-image` comments (unlike `rasi`).
