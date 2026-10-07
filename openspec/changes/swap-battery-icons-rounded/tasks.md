## 1. Derive the mapping from geometry (before writing anything)

- [x] 1.1 Calibrate the cavity from the one file whose fill is provably the full
  cavity: the 100% unplugged icon. Measured fill x ∈ [113, 756], width **643**.
- [x] 1.2 Build an element-level path-bbox parser that parses each `d` string
  into per-subpath boxes, including analytic cubic/quadratic extrema so control
  points do not inflate the reading. Do NOT regex the raw file.
- [x] 1.3 Classify each path by its own measured bbox — ring (leaves the cavity
  in x), bolt (spills outside the cavity vertically), fill (inside), nub (the
  `<rect>`). Element order varies between sources, so position is not a
  discriminator.
- [x] 1.4 Establish parity: odd-numbered files carry a notch-cut **filled** ring
  (`fill="#0F0000"`) plus a bolt; even-numbered carry a **stroked** ring
  (`stroke="#0F0000" stroke-width="40"`) and no bolt. 5 + 5, exact.
- [x] 1.5 Measure all ten fill widths; record `-8`/`-9` as having **no fill path**
  (the empty icons; the numbering wraps).
- [x] 1.6 Investigate the one disagreement: `-3` reads width 266.83 = 41.50% of
  643, not 321 = 50%. Cause established as the diagonal notch clipping the fill
  (observable extent is `min(level_edge, slash_boundary)`, slash boundary =
  379.19). Level confirmed as 50% by three independent means: three of the four
  charging levels are pinned exactly by geometry and the extents are strictly
  increasing; the subpath-count + start-point fingerprint matches `master`'s own
  known-level charging templates 1:1; `master`'s 50% charging icon has the same
  single-subpath wedge. **Recorded in design.md §2, not silently accepted.**
- [x] 1.7 Confirm the derived mapping equals the table supplied in the task.
  Confirmed — all ten assignments match.

## 2. Convert the ten templates (in place, no new variants)

- [x] 2.1 Rewrite all 33 literal paint values (`black`, `#0F0000`, `#141414`,
  `#0F0F0F`) to placeholders: `{{COLOR_FOREGROUND}}` for ring, nub and fill;
  `{{COLOR_ACCENT}}` for the charging bolt. Vocabulary and idiom taken from
  `status-bar/battery/battery-100-charging/default/icon.svg`.
- [x] 2.2 Preserve every geometric attribute — `d`, `transform`,
  `stroke-width="40"`, the nub's `rx="50"`, `viewBox`, element order.
- [x] 2.3 Do not add a `rounded` style, variants, groups, or names. Do not touch
  `icons.yaml`, `icons.json`, `bar_mappings.states`, `verify_icons_samples`, or
  `plugged/default/icon.svg`.
- [x] 2.4 Do not edit anything under `dotfiles/config/ags/components/`, `bar/`,
  or `style.css`.

## 3. Verify mechanically

- [x] 3.1 Placeholder / literal census per file. **33 literals → 33 placeholders,
  0 literals remaining.** Raw grep over the ten installed templates: `#[0-9a-f]`
  = 0, `black` = 0, other named colours = 0, `rgb(` = 0.
- [x] 3.2 Geometry proof: normalise every `fill=`/`stroke=` **value** in both the
  source and the installed template, then byte-compare. Identical for all ten.
- [x] 3.3 Resolution: every placeholder name resolves through the variant → group
  → vocabulary merge. Zero unresolved.
- [x] 3.4 Drive the **real** `PlaceholderSubstitutionService` with
  `unsafe=False` (so an unmapped token raises rather than passing through) over
  all 16 battery variants. All substitute cleanly; output is well-formed XML;
  zero leftover `{{`. `system-battery-*` resolve to `foreground`, demonstrating
  the Bluetooth rows pick up the new artwork.

## 4. Confirm the untouched set

- [x] 4.1 `git diff --quiet master` on `icons.yaml`, `icons.json`,
  `icon-registry.ts`, `plugged/default/icon.svg`, `verify/vars/main.yml` and
  `test_verify_role.py` — all byte-identical. md5 of the first, second, third and
  fifth match `master` exactly.
- [x] 4.2 `bar_mappings.states` compared as a parsed YAML block against
  `master` — identical.
- [x] 4.3 The diff is exactly ten modified template files and nothing else.

## 5. Gates

- [x] 5.1 `make gates-ci` — all six gates green.
- [x] 5.2 `python3 scripts/capture-hexagonal-gate.py` — PASS, check 6 at
  33 used / 28 styled.
- [x] 5.3 `make capture-typecheck` — 0 errors in `src/gui-tools/capture-tool`
  (28 tolerated third-party errors under `/usr/share/ags/js`, machine-specific
  and pre-existing).
- [x] 5.4 `make capture-test` — 144 pass / 0 fail / 0 skipped.
- [x] 5.5 capture `pytest tests/` — 97 passed.
- [x] 5.6 `uv run --directory src/provisioning pytest tests/unit -q` —
  **0 failed / 720 passed**.
- [x] 5.7 No test or gate was weakened, disabled or skipped to reach green.
- [x] 5.8 Noted (not caused by this change): `icon-templates-renderer`'s own
  suite has 3 pre-existing failures. Confirmed pre-existing by stashing the
  template change and re-running: identical 3 failed / 283 passed on `master`'s
  templates.

## 6. Record what could not be verified

- [x] 6.1 State plainly in design.md §4 that provision could not run (`sudo`
  needs a password), so `itr render` never read the new templates and **the icons
  were not confirmed to render**.
- [x] 6.2 Record the three unverified visual judgements: the bolt's accent hue,
  the absence of a ring/fill seam on a light wallpaper or the dark-glass panel,
  and optical balance at `icon_size: 24`.
- [x] 6.3 Flag the `-3` → 50% assignment as the one judgement call worth a
  second pair of eyes before merge.