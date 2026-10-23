## Context

CSG renders one artifact per requested format with
`template_name = f"colors.{fmt.value}.j2"` and
`output_path = output_dir / f"colors.{fmt.value}"`
(`adapters/local_processor.py:83-86`). Formats are a **closed enum**
(`domain/enums.py:31-42`):

```
JSON=json, SH=sh, CSS=css, GTK_CSS=gtk.css, ADW_CSS=adw.css,
YAML=yaml, SEQUENCES=sequences, RASI=rasi, SCSS=scss,
HYPRLAND=conf, KITTY=kitty
```

`TemplateCatalogService.derive` (`domain/services.py:82-101`) raises
`TemplatesValidationError` for any `colors.<key>.j2` whose `<key>` is not in
`ColorFormat`; `OutputSettingsSchema._validate_default_formats` validates
`default_formats` against the same set.

Three properties of the palette model drive the whole design, and all three were
verified against the live palette rather than assumed:

1. **`colors[]` is a luminance ramp, not an ANSI palette.** Every backend sorts
   ascending by `sum(rgb)` — `pywal_generator.py:74`,
   `custom_generator.py:78`, `wallust_generator.py:108`. A conventional
   `color0`→`main_bg` mapping would produce garbage.
2. **The ramp contains duplicates.** The live palette yields only **9 distinct**
   colors across 16 slots, so templates address deduplicated adjacent stops.
3. **btop's key names misrepresent what they render.** Traced every
   `Theme::g()` call site in `btop_draw.cpp`:

   | gradient | actually renders |
   |---|---|
   | `temp` | CPU temp, per-core temps, GPU temp — scaled `temp*100/temp_max` (**relative**) |
   | `cpu` | CPU meter, **GPU util graphs + meter**, per-core graphs, enc/dec meters, battery (**6 call sites**) |
   | `cached` | **CPU watts, GPU power draw, P-state** — *not* cache |
   | `available` | **disk I/O activity (%busy)** — *not* free RAM |
   | `used` | disk used meter, GPU VRAM |
   | `free` | disk free meter, GPU mem util |
   | `download`/`upload` | net graphs (no "more is brighter" reading) |
   | `process` | process-list thread/mem/cpu |

## Goals / Non-Goals

**Goals**
- Three btop formats exist, render all 48 keys from the shared `ColorScheme`,
  and are discoverable by the catalog and CLI like any sibling.
- Rendered bytes satisfy btop 1.4.7's actual parser.
- The three variants form a legible difficulty dial.
- Zero behavioural change to existing formats.

**Non-Goals**
- Runtime consumption or distribution (`add-runtime-btop-theme-artifacts`).
- `btop.conf`, `config_links`, or the `btop` package entry
  (`provision-btop-config`).
- Any reload mechanism.
- A btop-as-source backend.
- A generic "arbitrary template" escape hatch — the enum stays the authority.

## Decisions

### D1. Add to the closed `ColorFormat` enum; templates and enum land atomically
Verified: `TemplateCatalogService.derive` rejects unregistered formats, so a
template shipped without its enum member would break `csg` **entirely**, not
merely the new format. The enum member and the template are therefore a single
inseparable unit of work. Each variant ships as one commit step.

### D2. Three formats, not one template emitting three files
A Jinja template renders exactly one output file. Emitting three themes from one
format is therefore impossible without adding a new output concept — which would
be a much larger change to the render contract. Three formats is the mechanism
the architecture already supports, and it keeps each variant independently
addressable on the CLI (`-f btop-minimal.theme`).

### D3. No shared `.j2` partial
Tempting to factor the 15 identical base-surface lines into one include, but any
extra `*.j2` in the templates directory is catalog-scanned: `colors.btop-base.j2`
would parse as format `btop-base` and raise `TemplatesValidationError`, breaking
`csg`. Each template is fully self-contained. Structural similarity between the
three is maintained by generating and reviewing them together, not by a shared
file.

### D4. Meaningful mapping by role, and key names are not to be trusted
Each gradient maps by **what btop actually renders**, per the call-site table
above. Two consequences are deliberate:

- `cached` (power) groups with `used`, and `available` (disk I/O) groups with
  `free` — so each color stands for a real meaning rather than a misleading name.
- `cpu` is the highest-leverage key at 6 call sites. Forcing it semantic makes
  `csg-full` dramatically louder, which is the intended meaning of that tier.

### D5. `temp` is relative-scaled, so semantic cool→warm is safe
`Theme::g("temp").at(clamp(temp * 100 / temp_max, 0, 100))` scales against the
detected maximum, not an absolute scale. "Warmer" therefore means *closer to this
machine's ceiling*, which is exactly the intended reading and survives a wallpaper
change. Verified the chosen stops are monotone in hue (blue 208° → terracotta
12° → gold 35°) with CIELAB ΔE of 47.8 and 36.9 between adjacent stops, well above
the ~10 legibility threshold.

By contrast `cpu` and `cached` are **not** inherently hot — high wattage under
load is normal, not alarming — which is why they only become semantic from
`csg-balanced` and `csg-full` upward, at the user's explicit choice.

### D6. Two-stop gradients where the ramp has no direction
`download`/`upload` measure throughput, for which "brighter = more" is not a
meaningful reading. These emit `theme[<x>_mid]=""`, invoking btop's documented
two-stop idiom (`btop_theme.cpp:260-264`).

### D7. Every emitted line starts at column 0
btop treats `#` as a comment **only at offset 0**; a leading space before `[`
makes the parser skip forward and mangle the line
(`btop_theme.cpp:399-406`). CSG renders with `trim_blocks`/`lstrip_blocks`
(`jinja_template_renderer.py`), so this is easy to get wrong by indenting a loop
body. Asserted explicitly in tests.

### D8. All 48 keys, no reliance on btop's fallbacks
Although nothing is required, emitting all 48 means the artifact is
self-describing and cannot silently inherit a stock-theme color if btop's defaults
ever change. This includes the process-state keys added in btop 1.4.6
(`proc_pause_bg`, `proc_follow_bg`, `proc_banner_bg`, `proc_banner_fg`,
`followed_bg`, `followed_fg`) and defines **all three** of `process_start` /
`process_mid` / `process_end` — defining only some triggers a fade-to-black,
because the fallback is guarded on `process_start` alone while
`generateGradients` reads `rgbs["process_end"]` via `operator[]`
(`btop_theme.cpp:328`).

### D9. Theme application is asserted from btop's own output, never by eye
The obvious verification — "launch btop and check it looks themed" — is not
acceptable: it needs a human, and btop's most likely failure mode is **silent**.
`setTheme` leaves `theme_path` empty when `color_theme` does not resolve against
the discovered list, and applies `Default_theme` with **no error and no log
entry** (`btop_theme.cpp:465`). A theme that never loads looks identical to one
that does, except for colours.

Two machine-checkable channels exist, both verified against btop 1.4.7:

1. **Log channel.** `Theme::loadFile` logs
   `Loading theme file: <abs path>` at DEBUG (`btop_theme.cpp:397`). With
   `log_level = "DEBUG"` and an isolated `XDG_STATE_HOME`, a test asserts that
   line names *our* file. An unresolvable theme produces no such line at all.
2. **Frame channel.** Run btop on a real pty (it requires a real terminal size;
   without one it only emits errors), capture the frame, and extract every
   24-bit SGR colour from both `38;2` (fg) and `48;2` (bg). Assert a majority of
   the theme file's colours are painted **and** that none of btop's
   `Default_theme` colours appear. Measured: with our theme, 5/5 painted colours
   come from the file and 0 Default colours appear; with an unresolvable
   `color_theme`, the frame is entirely Default colours.

The harness lives at `spikes/btop-theme-prototype/assert_theme_applies.py` and is
promoted into the CSG test suite by task 2.9. Its **negative control is part of
the success criteria** (task 4.9): a verification that cannot fail proves
nothing, so the harness must exit non-zero when the theme is absent.
Stock themes carry descriptive comments, and btop's parser skips any line whose
first character is `#`. Each template emits a header (slug, source image, backend,
generation time) plus a per-gradient `# name: ramp|SEMANTIC cool->warm` marker, so
a generated theme is self-documenting when a user opens it in an editor.

## Risks

- **Palette degeneracy.** With few distinct stops, gradients can compress. The
  templates read deduplicated stops and a degenerate palette (e.g. a monochrome
  wallpaper) yields a low-contrast but still valid theme. Accepted: correctness
  is never violated, and `PaletteNormalizationService` already pads to 16.
- **Template count assertions.** `csg info` reports `templates_count` (currently
  11) and tests assert the catalog size. All such assertions must move to 14.
