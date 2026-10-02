## 1. Enum + templates (each variant is one atomic commit step)

- [ ] 1.1 `domain/enums.py` — add `BTOP_MINIMAL = "btop-minimal.theme"`, `BTOP_BALANCED = "btop-balanced.theme"`, `BTOP_FULL = "btop-full.theme"` to `ColorFormat`. **Must land in the same step as the templates below** — `TemplateCatalogService.derive` raises `TemplatesValidationError` for an unregistered template, which breaks `csg` entirely, not just the new format.
- [ ] 1.2 `defaults/templates/colors.btop-minimal.theme.j2` — all 48 keys, every gradient a luminance-ramp slice, neutral outlines, `download`/`upload` two-stop
- [ ] 1.3 `defaults/templates/colors.btop-balanced.theme.j2` — identical to 1.2 except `temp_*` and `cached_*` are semantic cool→warm
- [ ] 1.4 `defaults/templates/colors.btop-full.theme.j2` — identical to 1.3 except `cpu_*` is semantic cool→warm
- [ ] 1.5 Confirm no shared partial was introduced: every `*.j2` in `defaults/templates/` must parse as a `ColorFormat` value (`ls defaults/templates/*.j2` → 14 files, all valid)
- [ ] 1.6 Confirm the render path needs nothing else: `local_processor.py:83-86` already maps `colors.{fmt.value}.j2` → `colors.{fmt.value}`, so no output filename for `.theme` needs special handling
- [ ] 1.7 Confirm every emitted line starts at column 0 in all three templates (no indented loop bodies — `trim_blocks`/`lstrip_blocks` do not protect against a leading space before `[`)

## 2. Tests

- [ ] 2.1 `tests/unit/domain/test_enums.py` — assert the three `.value` strings exactly
- [ ] 2.2 `tests/unit/adapters/test_template_catalog_loader.py` — all three are discovered as their formats; a `colors.bogus.j2` still raises `TemplatesValidationError`
- [ ] 2.3 New `tests/unit/adapters/test_btop_theme_formats.py` — a parser-rules validator mirroring `btop_theme.cpp`: exact 48-key set match, valid value grammar (`#RRGGBB`/`#GG`/`R G B`, never 8 digits), and **no line begins with whitespace**
- [ ] 2.4 In that file, assert the difficulty dial: minimal vs balanced differ *only* in `temp_*`/`cached_*`; balanced vs full differ *only* in `cpu_*`; and the semantic-gradient set is a superset chain
- [ ] 2.5 In that file, assert `process_start`/`process_mid`/`process_end` are all present and non-empty (the fade-to-black trap), and that `download_mid`/`upload_mid` are empty
- [ ] 2.6 In that file, assert `cpu_box == mem_box == net_box == proc_box` and all five outline/divider values come from the palette
- [ ] 2.7 Rendering test: a generation request naming all three formats writes the three `*.theme` files with the expected bytes
- [ ] 2.8 Semantic-monotonicity test: for each semantic gradient, successive CIELAB stops are not cooler than the previous (guards against a palette that would invert the reading)

## 3. Count assertions

- [ ] 3.1 Update every `templates_count` assertion from 11 to 14 (CSG `info` command surface and any test asserting catalog size) — grep `templates_count` and the catalog-size assertions
- [ ] 3.2 `csg info` reports `templates.formats` including the three btop values

## 4. Verification

- [ ] 4.1 `uv run --directory src/cli-tools/color-scheme-generator pytest` green
- [ ] 4.2 `csg generate <image> -f btop-minimal.theme -f btop-balanced.theme -f btop-full.theme -o <tmp>` writes three files, each with all 48 keys
- [ ] 4.3 `cat -A <each file>` — confirm no line begins with a space or tab
- [ ] 4.4 Optional on-host check: copy a rendered theme to `~/.config/btop/themes/` and confirm `btop --version` plus the in-app theme list shows it (the theme is only *applied* once the provisioning change sets `color_theme`)
