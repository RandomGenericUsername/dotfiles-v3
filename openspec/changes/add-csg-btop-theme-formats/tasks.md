## 1. Enum + templates (each variant is one atomic commit step)

- [x] 1.1 `domain/enums.py` — add `BTOP_MINIMAL = "btop-minimal.theme"`, `BTOP_BALANCED = "btop-balanced.theme"`, `BTOP_FULL = "btop-full.theme"` to `ColorFormat`. **Must land in the same step as the templates below** — `TemplateCatalogService.derive` raises `TemplatesValidationError` for an unregistered template, which breaks `csg` entirely, not just the new format.
- [x] 1.2 `defaults/templates/colors.btop-minimal.theme.j2` — all 48 keys, every gradient a luminance-ramp slice, neutral outlines, `download`/`upload` two-stop
- [x] 1.3 `defaults/templates/colors.btop-balanced.theme.j2` — identical to 1.2 except `temp_*` and `cached_*` are semantic cool→warm
- [x] 1.4 `defaults/templates/colors.btop-full.theme.j2` — identical to 1.3 except `cpu_*` is semantic cool→warm
- [x] 1.5 Confirm no shared partial was introduced: every `*.j2` in `defaults/templates/` must parse as a `ColorFormat` value (`ls defaults/templates/*.j2` → 14 files, all valid)
- [x] 1.6 Confirm the render path needs nothing else: `local_processor.py:83-86` already maps `colors.{fmt.value}.j2` → `colors.{fmt.value}`, so no output filename for `.theme` needs special handling
- [x] 1.7 Confirm every emitted line starts at column 0 in all three templates (no indented loop bodies — `trim_blocks`/`lstrip_blocks` do not protect against a leading space before `[`)

## 2. Tests

- [x] 2.1 `tests/unit/domain/test_enums.py` — assert the three `.value` strings exactly
- [x] 2.2 `tests/unit/adapters/test_template_catalog_loader.py` — all three are discovered as their formats; a `colors.bogus.j2` still raises `TemplatesValidationError`
- [x] 2.3 New `tests/unit/adapters/test_btop_theme_formats.py` — a parser-rules validator mirroring `btop_theme.cpp`: exact 48-key set match, valid value grammar (`#RRGGBB`/`#GG`/`R G B`, never 8 digits), and **no line begins with whitespace**
- [x] 2.4 In that file, assert the difficulty dial: minimal vs balanced differ *only* in `temp_*`/`cached_*`; balanced vs full differ *only* in `cpu_*`; and the semantic-gradient set is a superset chain
- [x] 2.5 In that file, assert `process_start`/`process_mid`/`process_end` are all present and non-empty (the fade-to-black trap), and that `download_mid`/`upload_mid` are empty
- [x] 2.6 In that file, assert `cpu_box == mem_box == net_box == proc_box` and all five outline/divider values come from the palette
- [x] 2.7 Rendering test: a generation request naming all three formats writes the three `*.theme` files with the expected bytes
- [x] 2.8 Semantic-monotonicity test: for each semantic gradient, successive CIELAB stops are not cooler than the previous (guards against a palette that would invert the reading)
- [x] 2.9 Promote `spikes/btop-theme-prototype/assert_theme_applies.py` into the CSG suite as `tests/integration/adapters/test_btop_theme_applies.py`, with:
  - **positive case** — each of the three rendered themes produces `Loading theme file: <our file>` in btop's DEBUG log **and** paints its own colours onto a real pty frame with zero `Default_theme` colours present
  - **negative control** — when `color_theme` names a theme that is absent, the assertion **fails** (this is what makes the positive case meaningful)
  - **skip path** — when the `btop` binary is absent, skip with a visible reason rather than passing silently
  - the harness must never report success on an exception; any error is a failure

## 3. Count assertions

- [x] 3.1 Update every `templates_count` assertion from 11 to 14 (CSG `info` command surface and any test asserting catalog size) — grep `templates_count` and the catalog-size assertions
- [x] 3.2 `csg info` reports `templates.formats` including the three btop values

## 4. Verification — all machine-checkable, no human eyes

Every criterion below is a command with an exit code. **No step requires a person
to look at a screen.** Where btop would otherwise be judged visually, the check
uses the two proven assertion channels (see D9).

- [x] 4.1 `uv run --directory src/cli-tools/color-scheme-generator pytest` green
- [x] 4.2 `csg generate <image> -f btop-minimal.theme -f btop-balanced.theme -f btop-full.theme -o <tmp>` writes exactly three files, each ending `.theme`
- [x] 4.3 `validate.py`-equivalent asserts, per file: exactly the 48-key set, valid value grammar, and **no line begins with whitespace** (`assert not any(l[:1] in ' \t' for l in text.splitlines() if l.strip())`)
- [x] 4.4 The three-way difference assertions hold: `set(minimal) ^ set(balanced) ⊆ {temp_*, cached_*}` and `set(balanced) ^ set(full) ⊆ {cpu_*}`
- [x] 4.5 Semantic monotonicity holds for every semantic gradient (CIELAB: each successive stop not cooler than the previous)
- [x] 4.6 `process_start`/`process_mid`/`process_end` all present and non-empty; `download_mid` and `upload_mid` are empty
- [x] 4.7 `cpu_box == mem_box == net_box == proc_box`, and all five outline/divider values occur in the palette
- [x] 4.8 **Theme application is proven, not eyeballed.** Run
      `python3 spikes/btop-theme-prototype/assert_theme_applies.py --theme-dir <rendered dir> --themes colors.btop-minimal.theme colors.btop-balanced.theme colors.btop-full.theme`
      and require exit code 0 with three `OK` lines. This asserts, per theme:
      (a) btop's DEBUG log contains `Loading theme file: <our file>`
      (`btop_theme.cpp:397`), and (b) the colours captured from a real pty frame
      are dominated by the theme's own colours with **zero** `Default_theme`
      colours present. Both channels are proven to fail when the theme is not
      applied.
- [x] 4.9 The harness's own negative control passes: run it against a directory
      where `color_theme` names a theme that is not present, and require exit
      code 1 with `FAILED`. A verification that cannot fail proves nothing.
- [x] 4.10 The harness skips cleanly (exit 0, `SKIP`) when `btop` is not
      installed, so CSG's suite stays green on machines without it — and the
      skip is visible in output rather than silent.
