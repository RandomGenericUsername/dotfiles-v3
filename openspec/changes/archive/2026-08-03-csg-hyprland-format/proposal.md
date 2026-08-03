## Why

The dotfiles Phase 1 provisioning plan establishes a chaining spine under `$XDG_DATA_HOME/dotfiles/` where the `csg`, `weg`, and `itr` compute providers read and write. The default color palette is derived at provisioning time from the default wallpaper via `csg generate`. For Hyprland, the compositor loads color variables from a `colors.conf` file (`$color0 = rgb(...)`, `$background = rgb(...)`, etc.) sourced from the Hyprland skeleton config. CSG currently ships 8 output-format templates (JSON, SH, CSS, GTK_CSS, YAML, RASI, SCSS, SEQUENCES) — none of which emits Hyprland's variable syntax (`$name = rgb(hex)` with no quotes, no trailing semicolon). To provision a correctly themed desktop on first boot without bespoke compositor glue in the provisioning layer, CSG should know how to render a Hyprland `colors.conf`.

## What Changes

- **New `ColorFormat` member** — `ColorFormat.HYPRLAND = "conf"` added to `domain/enums.py`. The value `"conf"` makes the template-naming convention (`colors.<fmt>.j2` → output `colors.<fmt>`) produce the desired `colors.conf` output filename with no special-casing in `LocalProcessor`.
- **New bundled template** — `defaults/templates/colors.conf.j2` emitting Hyprland variable syntax: `$background`, `$foreground`, `$cursor`, `$accent`, and `$color0`–`$color15`, each `rgb(<hex-without-#>)`, no quotes, no trailing semicolons.
- **Auto-participating surfaces (verified, no edits)** — `--format`/`-f` CLI choices derive from the enum (`cli/main.py`), settings validation (`settings/schema.py` `_VALID_FORMATS`), the template catalog service (`domain/services.py` `_FORMATS`), container-mode command reconstruction, output adapters, and `dump-templates` (globs all `.j2`).
- **Explicit edits** — `tests/unit/domain/test_enums.py` adds a member assertion; `docs/ARCHITECTURE_PLAN.md` and the `csg-templates-info-catalog` spec update the bundled-format count 8 → 9.

## Capabilities

### New Capabilities
- `csg-hyprland-format`: `csg generate` accepts `-f conf` (and `default_formats = ["conf"]`) and writes a Hyprland-compatible `colors.conf` whose variables follow the `$name = rgb(hex)` convention, as a 9th bundled output format alongside the existing eight.

### Modified Capabilities
- `csg-templates-info-catalog`: the templates catalog now surfaces 9 bundled format entries instead of 8; `templates.templates_count` reflects the new count and `templates.formats` includes `"conf"`.

## Impact

- **Source files**:
  - `src/cli-tools/color-scheme-generator/src/color_scheme_generator/domain/enums.py` — add `ColorFormat.HYPRLAND = "conf"`.
  - `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/colors.conf.j2` — new template.
  - `src/cli-tools/color-scheme-generator/docs/ARCHITECTURE_PLAN.md` — update format list and bundled-template count (L32, L493–500, L673).
- **Tests**:
  - `src/cli-tools/color-scheme-generator/tests/unit/domain/test_enums.py` — add assertion for `ColorFormat.HYPRLAND == "conf"`.
  - Optional format-rendering test asserting the rendered `colors.conf` matches the Hyprland syntax contract.
- **Specs**:
  - `openspec/specs/csg-templates-info-catalog/spec.md` — update "8 for bundled templates" / "all 8 standard format entries" literals to 9.
- **Behavior**: `csg generate <image> -f conf` writes `colors.conf` with Hyprland variable syntax; `default_formats = ["conf"]` renders it by default; `csg info` reports the 9th format. No existing behavior changes for the other eight formats.

## Out of Scope

- Emitting any other compositor-specific format (e.g. Waybar `colors.css` already exists via the CSS format).
- Writing derived colors into a running Hyprland/Waybar/Hyprpaper session (Phase 2 runtime concern).
- Any change to the provisioning `default_palette` role — it is a downstream consumer of this capability.
