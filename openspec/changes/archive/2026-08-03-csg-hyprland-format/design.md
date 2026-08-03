## Context

CSG renders palette outputs from Jinja2 templates. Each template lives at `defaults/templates/colors.<fmt>.j2` and produces `colors.<fmt>`. The `<fmt>` segment is the `ColorFormat` enum member's `.value` (`domain/enums.py:31–39`). The render context exposed to every template is identical: `background`, `foreground`, `cursor` (each a `Color` with `.hex` like `#1e1e2e` and `.rgb`), `colors[i]` for `i in range(16)`, plus `source_image`, `backend`, `generated_at`.

Hyprland does not accept any of the eight existing outputs as a `colors.conf`: it requires `$name = rgb(hex)` — `$`-prefixed names, ` = ` separator, `rgb(...)` wrapper, bare hex (no `#`), no quotes, no trailing semicolon. No existing template matches this shape (closest are `.scss` and `.sh`, but both differ in separator, hex form, and terminators). So a 9th template is required for provisioning to theme Hyprland on first boot without a bespoke compositor-format generator in the provisioning layer.

## Goals / Non-Goals

**Goals:**
- Add `ColorFormat.HYPRLAND` such that `csg generate <image> -f conf` writes a valid Hyprland `colors.conf`.
- Make `default_formats = ["conf"]` (and the empty-list-means-all expansion) render the new format.
- Keep the naming convention intact: template `colors.conf.j2` → output `colors.conf` with zero special-casing in `LocalProcessor`.
- Surface the new format through `csg info` templates catalog and `dump-templates` automatically.
- Keep all eight existing formats byte-identical.

**Non-Goals:**
- No `LocalProcessor` branching for the Hyprland output filename (achieved by choosing enum value `"conf"`).
- No container-image template discovery changes (Dockerfiles bundle the templates dir wholesale; a 9th `.j2` flows through automatically — verify during implementation).
- No runtime desktop coloring (Phase 2).
- No changes to the render context schema (`Color`, palette model).

## Decisions

### D1. Enum value is `"conf"`, not `"hyprland"`

`LocalProcessor._render_formats` derives both template filename and output filename from `ColorFormat.value` (`local_processor.py:83–84`: `f"colors.{fmt.value}.j2"` → `f"colors.{fmt.value}"`). `TemplateCatalogService.derive` strips `colors.` prefix and `.j2` suffix and looks up `ColorFormat(fmt_key)` (`domain/services.py:75–90`). Therefore:

- `HYPRLAND = "conf"` → template `colors.conf.j2`, output `colors.conf`, catalog key `conf`, all consistent. **Chosen.**
- `HYPRLAND = "hyprland"` → output `colors.hyprland`; would require special-casing `local_processor.py` L84 to remap the output filename — a new branching pattern no other format uses. Rejected.

`GTK_CSS = "gtk.css"` proves multi-char, dotted values are already legal; a single-segment `"conf"` is the simplest consistent choice.

### D2. Template content contract

The new `colors.conf.j2` must emit, in this order:

```
$background = rgb(<bg>)
$foreground = rgb(<fg>)
$cursor = rgb(<cur>)
$accent = rgb(<accent>)
$color0 = rgb(<c0>)
...
$color15 = rgb(<c15>)
```

- Every hex is the palette color's `.hex` with the leading `#` stripped, wrapped in `rgb(...)`.
- `$accent` defaults to `colors[1].hex` (a defensible accent pick; matches the pywal community convention). Overridable if design review prefers a different index.
- No quotes, no trailing semicolons, one variable per line.

Strip the `#` via Jinja slicing: `{{ colors[i].hex[1:] }}`. No existing template does this, so the new template is the only place the wrapping/stripping logic lives.

### D3. No default-formats change

`defaults/settings.toml` keeps `default_formats = ["json", "sh"]`. The Hyprland format is opt-in via `-f conf` or a user's `default_formats` list. It does NOT join the shipped defaults, so existing `csg generate` invocations are unaffected unless the user opts in.

### D4. Info catalog + dump-templates flow through automatically

`domain/services.py` `_FORMATS = {f.value for f in ColorFormat}` and the settings schema `_VALID_FORMATS` are derived from the enum, so the new member is accepted automatically. `dump-templates` globs every `.j2` in the bundled dir, so `colors.conf.j2` is copied automatically. `csg info` reports the 9th format via the same catalog. No edits needed in these surfaces — only tests/docs/spec updates.

## Risks / Trade-offs

- **Value collision risk** — `"conf"` is generic; a future format could want `colors.conf`-ish naming. Low risk: the only other likely candidate would be a shell/env format, already covered by `sh`. Mitigation: the enum name `HYPRLAND` disambiguates intent; the value is the file-extension contract.
- **Hyprland syntax drift** — If Hyprland changes its variable syntax, this template (and the downstream provisioning render) must track it. Mitigation: the template is the single source of the syntax; provisioning consumes the emitted file as-is.
- **`--check`/idempotency interaction** — None new: the template is a pure function of the palette; same palette → same `colors.conf`. No state introduced.
- **Container mode** — Inner container image must contain `colors.conf.j2`. Dockerfiles bundle `defaults/templates/` wholesale; verified during implementation that no Dockerfile enumerates template files by name (if one does, add the new file to its COPY list).

## Migration Plan

Single-step additive change. Existing eight formats and their outputs are untouched. Users must explicitly opt in to `conf` (via `-f conf` or `default_formats`). No data migration, no rollback path beyond reverting the commit (which removes the enum member, template, and tests as a unit).
