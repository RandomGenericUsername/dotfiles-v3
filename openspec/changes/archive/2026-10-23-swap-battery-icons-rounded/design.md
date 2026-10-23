# Design: swap-battery-icons-rounded

## 1. Calibration and method

The instruction to "measure fill width and divide by 643" is right for eight of
the ten files and wrong for one of them (`-3`), and two of the listed traps are
real. What follows is the method that was actually used, and its one failure.

### 1.1 Why a naive measurement of the raw file is wrong

Three traps, all confirmed against these files:

**(a) Regexing the whole file swamps the reading.** The ring path in every file
carries far larger x values than the fill. In `default.svg` the ring spans
x ∈ [38, 831] while the fill spans [118, 279]. Taking `max(x)` over the raw text
reports 831 for a 25% icon. Element-level parsing is mandatory.

**(b) Bézier control points overshoot the real edge.** `-6`'s fill path contains
control points at x = 733.614 and the curve genuinely reaches 756, but in
`-3` the on-curve endpoint is 379.188 while a control point sits at 382.062.
`max(x)` over a `d` string therefore over-reads by ~2.8 units.

**(c) The charging fills do not start at `M113`.** All five charging icons
express the fill as a wedge beginning at a notch hook such as
`M210.48 573.951` or `M259.48 562.701`. A `startswith("M113")` filter misses
**all five** of them. `battery-25-charging` on `master` starts at `M288.75 379`.

### 1.2 The calibration

The cavity is x ∈ [113, 756], width **643**, taken from the one file whose fill is
provably the full cavity — the 100% unplugged icon, whose fill path is a plain
rounded rectangle:

```
battery-empty-unplugged-default-6.svg
  path fill=black  x=[113.00, 756.00]  ->  width = 643.00  = 100.00% of 643
```

Every other unplugged fill starts at exactly x = 113, confirming 113 as the
cavity's left wall and 756 as its right wall.

Implied level edges: 25% → 273.75, 50% → 434.5, 75% → 595.25, 100% → 756.

### 1.3 Roles, not guesswork

Each path is classified by its own measured bounding box, never by position in
the file (element order varies between the sources):

| role | discriminator |
|---|---|
| ring | x-extent leaves the cavity (x0 < 100 or x1 > 800) |
| bolt | inside the cavity in x, but spills vertically (y0 < 300 or y3 > 680) |
| fill | entirely inside the cavity |
| nub | the `<rect>` |

### 1.4 Parity: odd = charging, even = unplugged

Confirmed on all ten, and it is exactly the claimed parity:

| file | ring paint | bolt | verdict |
|---|---|---|---|
| `default.svg`, `-2`, `-4`, `-6`, `-8` | `stroke="#0F0000" stroke-width="40"` | absent | **unplugged** |
| `-1`, `-3`, `-5`, `-7`, `-9` | `fill="#0F0000"` (notch-cut, filled) | present | **charging** |

`-8` (unplugged, stroked ring, **no fill path**) and `-9` (charging, filled ring,
bolt, **no fill path**) are the two empty icons — which is why the numbering
wraps rather than running 0…9.

### 1.5 Measured table

```
default.svg    FILL x=[118.00, 279.00]  width=161.00  = 25.04%   STROKED  no bolt   -> battery-25
-1.svg         FILL x=[118.00, 279.00]  width=161.00  = 25.04%   FILLED   bolt      -> battery-25-charging
-2.svg         FILL x=[113.00, 434.00]  width=321.00  = 49.92%   STROKED  no bolt   -> battery-50
-3.svg         FILL x=[113.00, 379.83]  width=266.83  = 41.50%   FILLED   bolt      -> battery-50-charging
-4.svg         FILL x=[113.00, 595.00]  width=482.00  = 74.96%   STROKED  no bolt   -> battery-75
-5.svg         FILL x=[113.00, 595.00]  width=482.00  = 74.96%   FILLED   bolt      -> battery-75-charging
-6.svg         FILL x=[113.00, 756.00]  width=643.00  =100.00%   STROKED  no bolt   -> battery-100
-7.svg         FILL x=[113.00, 756.00]  width=643.00  =100.00%   FILLED   bolt      -> battery-100-charging
-8.svg         NO FILL PATH                              0%        STROKED  no bolt   -> battery-0
-9.svg         NO FILL PATH                              0%        FILLED   bolt      -> battery-0-charging
```

Note the 25% pair is inset by 5 units (`[118, 279]` rather than `[113, 273.75]`);
the artwork's own padding differs, but its **width** is exactly 161.

## 2. `-3` is the anomaly, and why it is still 50%

`width ÷ 643` gives 41.50% for `-3`, not 50%. That number does not match the
table, so it is called out here rather than buried.

**Cause: the fill is clipped by the diagonal notch, not by the level.** In the
charging artwork the fill is a rectangle from the cavity's left wall to the
level edge, minus a diagonal slash. Where the slash overlaps, the fill's
measured right edge is the slash's boundary, not the level's. The observable
extent is therefore `min(level_edge, slash_boundary)`.

The slash boundary is a fixed feature of this icon family and is identical in
`-3`, `-5` and `-7`: the hook coordinates `H364.816 … 379.188 … L371.83 642`.
So:

| file | level edge | slash boundary | predicted | measured | match |
|---|---|---|---|---|---|
| `-1` | 274 (25%) | 379.19 | 274 | 279.00 | level-bound (25% inset by 5) |
| `-3` | 434.5 (50%) | 379.19 | **379.19** | **379.83** | **slash-bound** |
| `-5` | 595.25 (75%) | 379.19 | 595.25 (corner subpaths carry it past the slash) | 595.00 | level-bound |
| `-7` | 756 (100%) | 379.19 | 756 (same) | 756.00 | level-bound |

`-3` is the only charging icon whose level edge falls *inside* the slash, so it is
the only one whose width under-reports.

**Three independent reasons 50% is still correct, none of them a guess:**

1. **Three of the four charging levels are pinned exactly by geometry** — `-1` at
   161 (25% edge), `-5` at 482 (75% edge, 595 = 113 + 482), `-7` at 643 (100%
   edge, 756 = 113 + 643). The extents are strictly increasing
   (279 < 379.83 < 595 < 756) and the only unassigned level between 25% and 75%
   is 50%.

2. **Subpath count matches `master`'s known-level templates exactly.** A charging
   fill past the slash needs extra corner subpaths; one clipped by the slash
   needs none. The repo's own icons, whose levels are pinned by `icons.yaml`,
   fingerprint identically:

   | variant | level | fill start | subpaths |
   |---|---|---|---|
   | `battery-25-charging` (master) | 25% | `M288.75 379` (rect corner) | 1 |
   | `battery-50-charging` (master) | 50% | `M260.48 563.701` (slash hook) | 1 |
   | `battery-75-charging` (master) | 75% | `M260.48 563.701` | 3 |
   | `battery-100-charging` (master) | 100% | `M259.48 562.701` | 2 |
   | **`-1`** | → 25% | `M229 381` (rect corner) | 1 |
   | **`-3`** | → 50% | `M210.48 573.951` (slash hook) | 1 |
   | **`-5`** | → 75% | `M210.48 573.951` | 3 |
   | **`-7`** | → 100% | `M210.48 573.951` | 2 |

   A perfect 1:1 correspondence. The "starts at the slash hook, one subpath"
   signature is precisely how `master` distinguishes its own 50% charging icon,
   and `-3` has it.

3. **`master`'s 50% charging icon has the same missing corner piece.** `master`'s
   `battery-50-charging` is also a single-subpath wedge with no corner pieces,
   while its 75% and 100% have them. `-3` reproduces that asymmetry exactly, so
   its shape is the same "50%" the repo already ships.

Conclusion: the mapping is **confirmed**, with the caveat that `-3`'s level is
inferred from the ramp and the structural fingerprint rather than read off a
width.

## 3. The colour rewrite

### 3.1 What had to change

33 literal paint values across the ten files: `black`, `#0F0000`, `#141414`,
`#0F0F0F`. Every one became a placeholder.

| | literals | placeholders |
|---|---|---|
| before (owner's downloads) | 33 | 0 |
| after (installed templates) | **0** | **33** |

### 3.2 Which placeholder, and why the bolt differs

Convention taken from `status-bar/battery/battery-100-charging/default/icon.svg`
on `master`, which already uses exactly this vocabulary:

- ring, nub, fill, and the notch-cut body → `{{COLOR_FOREGROUND}}`
- the charging bolt → `{{COLOR_ACCENT}}`

`COLOR_ACCENT` resolves for every battery variant from the group-level mapping in
`icons.yaml` (`COLOR_ACCENT: color13`, `COLOR_FOREGROUND: color15`), so the bolt
takes the accent and everything else the foreground — the same split the existing
charging icons already use. The unplugged icons carry no bolt and therefore use
`COLOR_FOREGROUND` only, which matters because the `system-battery-*` variants
pin only that one token.

### 3.3 The near-black seam, deliberately closed

Several files used two different near-blacks for adjacent shapes — `#0F0000` for
the ring and `#141414` (in `-2`, `-3`) or `#0F0F0F` (in `-4`, `-5`) for the fill.
Collapsing both to `{{COLOR_FOREGROUND}}` removes the seam by construction, so
the ring and fill cannot drift apart when the guard retargets the token on a
light wallpaper. The rendered output confirms a single foreground value per
variant.

### 3.4 Geometry untouched

Every geometric attribute is preserved byte-for-byte: `fill-rule`, `transform`,
`stroke-width="40"`, `rx="50"` on the nub, `viewBox`, element order. Proven by
normalising every `fill=`/`stroke=` **value** to a single token in both the source
and the installed template and byte-comparing the results — identical for all ten
(verification script §2, all `True`).

## 4. What could not be verified

Templates reach the runtime through the Ansible `assets` role, which
`synchronize`s them into `<install>/icon-templates/`. `itr render` then reads
that **deployed** spine. `sudo` requires a password in this environment, so
provision could not run and the deployed templates are still the old ones.

**Verified**

- `icons.yaml` parses; all 16 `template:` paths resolve on disk.
- All 11 `bar_mappings.states` keys map to existing variant names, and those are
  exactly the names `getBatteryStateKey()` in `bar/widgets/battery.tsx` requests.
- `icons.json`'s battery variant set equals `icons.yaml`'s (16 = 16, no
  difference either way).
- Zero unfilled placeholders and zero literal colours across the ten files; every
  placeholder name resolves through the variant → group → vocabulary merge.
- Geometry byte-identical to the source modulo paint values.
- All 16 variants substitute cleanly through the **real**
  `PlaceholderSubstitutionService` with `unsafe=False` (so an unmapped token
  raises rather than passing through) and produce well-formed XML. The
  `system-battery-*` copies render to `foreground`, demonstrating the Bluetooth
  rows pick up the new artwork.
- `make gates-ci` green; capture gates green; provisioning unit suite 720 passed
  / 0 failed.

**Not verified — and not verifiable here**

1. **That they actually render.** No `itr render` against the deployed spine, so
   no `cache/icons/<hash>/*.svg` was produced or inspected.
2. **That the bolt's accent looks right.** `COLOR_ACCENT` → `color13` is
   guaranteed to resolve, but whether that hue reads correctly against the new
   artwork — and against the bar backdrop — needs eyes on a live bar.
3. **That there is no ring/fill seam** on a light wallpaper, or on the
   dark-glass panel. Collapsing the two near-blacks to one token makes a seam
   structurally unlikely, but the contrast guard's actual retargeted output on a
   light wallpaper was never rendered.
4. **Visual proportions at `icon_size: 24`.** The new artwork's cavity
   (x ∈ [113, 756] of a 1024 viewBox) differs from the old one's; whether the
   battery still optically matches its neighbours in the bar is a judgement call
   that needs the bar on screen.

The one judgement call that carries real risk, and is worth a second pair of eyes
before merge, is §2's assignment of `-3` to 50%.