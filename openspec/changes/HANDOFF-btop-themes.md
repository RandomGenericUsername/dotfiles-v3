# btop theme integration — handoff

Three changes, ordered. Together they make the wallpaper palette reach btop.

| # | change | layer | blocked by |
|---|---|---|---|
| 1 | `add-csg-btop-theme-formats` | CSG | — |
| 2 | `add-runtime-btop-theme-artifacts` | runtime | 1 |
| 3 | `provision-btop-config` | provisioning | 1, 2 |

`change 1` adds three formats to CSG. `change 2` makes the runtime request and
expose them. `change 3` puts them where btop can find them and selects one.

Follows the kitty precedent (`add-csg-kitty-color-format` →
`add-runtime-kitty-terminal-reload` → `provision-kitty-color-config`).

## The three themes

A difficulty dial, not a feature list. They differ **only** in which gradients are
forced to a semantic cool→warm ramp; every other assignment is byte-identical.

| theme | semantic gradients | character |
|---|---|---|
| `csg-minimal` | none | pure wallpaper luminance ramp; wallpaper-faithful |
| `csg-balanced` | `temp`, `cached` | temperature and power read as hot |
| `csg-full` | `temp`, `cached`, `cpu` | also CPU/GPU load; loudest |

`color_theme` defaults to `csg-minimal.theme` on first provision.

## Two things that will bite an implementer

**1. Template and enum member are one atomic unit.** `TemplateCatalogService.derive`
(`domain/services.py:82-101`) raises `TemplatesValidationError` for any
`colors.*.j2` not in `ColorFormat` — a template without its enum member breaks
`csg` **entirely**, not just the new format. Ship each variant as one step.

Corollary: **no shared `.j2` partial is possible.** Any extra `.j2` in the
templates dir is catalog-scanned, so a `colors.btop-base.j2` would parse as format
`btop-base` and hard-fail. The three templates are fully self-contained.

**2. The contract schema update must land in the same commit as the runtime change.**
`contracts/schemas/meta.schema.json:47-67` declares `artifact_hashes` with
`additionalProperties: false` and a closed `required` list. Runtime-without-schema
makes every new `meta.json` fail `make contracts-check`; schema-without-runtime
makes every existing `meta.json` fail the stricter `required`. Either order breaks
the build, in opposite directions.

## Findings that shaped the design

Full evidence, with source citations, in
`spikes/btop-theme-prototype/FINDINGS.md`. The load-bearing ones:

**btop's gradient key names misrepresent what they paint.** Traced every
`Theme::g()` call site in `btop_draw.cpp`:

- `cached` is **power draw** (CPU watts, GPU power, P-state) — *not* cache.
- `available` is **disk I/O activity** — *not* free memory.
- `cpu` has **6 call sites** (CPU meter, GPU utilisation + meter, per-core
  graphs, encode/decode meters, battery). Highest-leverage key; this is why
  `csg-full` is a large jump.
- `temp` is scaled `temp * 100 / temp_max` — **relative**, so "warmer" means
  "closer to this machine's ceiling" and the reading survives a wallpaper change.
  This is what makes semantic heat safe for `temp` specifically.

**`colors[]` is a luminance ramp, not an ANSI palette.** Every backend sorts
ascending by `sum(rgb)` (`pywal_generator.py:74`, `custom_generator.py:78`,
`wallust_generator.py:108`). A conventional `color0`→`main_bg` mapping produces
garbage. The live palette also yields only **9 distinct** colors across 16 slots,
so templates address deduplicated adjacent stops.

**Every emitted line must start at column 0.** btop treats `#` as a comment only at
offset 0; leading whitespace before `[` makes the parser skip forward and mangle
the line (`btop_theme.cpp:399-406`). CSG renders with `trim_blocks`/
`lstrip_blocks`, so an indented loop body is a real risk.

**Symlinks work.** `updateThemes` (`:430-442`) filters on
`file.path().extension() == ".theme"` (lexical — reads the link's own name) and
`access(path, R_OK)` (follows the chain). btop never canonicalizes, so the full
3-hop chain spine → `current/` → content-addressed cache is invisible to it.
Verified against a real chain.

**btop cannot be given an absolute theme path.** `setTheme` (`:451-471`) matches
`color_theme` only against themes discovered at startup; an absolute path outside
those directories silently falls back to `Default_theme`. Hence consumer pointers
into `~/.config/btop/themes/`, not a kitty-style `include`.

**`save_config_on_exit = false` is mandatory, not cosmetic.** It defaults `true`
(`:379`) and `Config::write()` truncates the file on exit (`:836-845`). Through
the spine symlink, the default would let btop overwrite the provisioning-owned,
git-tracked `btop.conf` and put UI changes into version control.

## Verification is fully machine-checkable — do not eyeball anything

The obvious check ("launch btop, confirm it looks themed") is **not** acceptable,
because btop's primary failure mode is silent: when `color_theme` does not resolve
against the discovered themes, `setTheme` applies `Default_theme` with no error and
no log line (`btop_theme.cpp:465`). A theme that never loaded looks exactly like one
that did.

Two assertion channels are proven against btop 1.4.7 and live in
`spikes/btop-theme-prototype/assert_theme_applies.py`:

1. **Log** — with `log_level = "DEBUG"`, btop emits
   `Loading theme file: <abs path>` (`btop_theme.cpp:397`). Assert that line names
   *our* file. An unresolvable theme produces no such line.
2. **Frame** — run btop on a real pty (it needs a real terminal size), extract every
   24-bit SGR colour from both `38;2` and `48;2`, and assert the theme's colours
   dominate with **zero** `Default_theme` colours present. Measured: our theme →
   5/5 frame colours from the file, 0 Default; unresolvable theme → frame entirely
   Default colours.

Run it as:

```
python3 spikes/btop-theme-prototype/assert_theme_applies.py \
  --theme-dir <rendered dir> \
  --themes colors.btop-minimal.theme colors.btop-balanced.theme colors.btop-full.theme
```

**Every change's acceptance criteria are exit codes, not observations.** The harness
has a negative control as part of the success criteria: a verification that cannot
fail proves nothing, so it must exit non-zero when the theme is absent. Two bugs
found while building it are worth not repeating — it crashed instead of failing
cleanly on a missing file, and it reported success on an exception.

Notable non-visual assertions:
- **`save_config_on_exit`** is proven by hashing `btop.conf`, running btop to
  termination, and asserting the hash is unchanged — this is what proves btop did
  not truncate the spine-owned file through the symlink.
- **Discoverability** is asserted with btop's own predicates (`.theme` extension +
  `access(R_OK)` + resolves into a cache entry), so no btop run is needed.
- The runtime change needs no host at all: assert the `--format` argv, the
  `PALETTE_ARTIFACT_NAMES` membership, `resolve().is_relative_to(entry_dir)` for
  each `current/` symlink, and schema round-trip — all against a temp state root.

## Reload: deliberately deferred

btop resolves its theme once at startup and exposes no reload signal. A running
instance keeps its colours until relaunch. Restarting a foreground TUI on every
wallpaper change is a UX decision deferred to a later change; `Gtk4AppReloader` is
the likely template for it.

## Out of scope

**btop as a palette source.** Deriving a `ColorScheme` from an existing `.theme`
file is a separate change (the user was explicit). It fits the architecture — a
`Backend` enum member plus a `PaletteGenerator` port implementation — but it must
reduce 48 semantic keys to the 16-slot `ColorScheme` contract, most likely by
luminance-sorting like the image backends. Build it against the templates proven
by change 1.

## Gates

```
uv run --directory src/cli-tools/color-scheme-generator pytest
uv run --directory src/runtime pytest
uv run --directory src/provisioning pytest
python tests/architecture/test_layering.py
make contracts-check
```
