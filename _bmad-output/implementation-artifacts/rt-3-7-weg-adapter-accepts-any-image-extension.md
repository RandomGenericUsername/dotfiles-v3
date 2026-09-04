---
baseline_commit: 37945ec5427b956ed8bd816047b428ee910fa22b
---

# Story rt-3.7: WEG adapter accepts any image extension (PNG / JPG / WebP / etc.)

Status: review

## Story

As a user,
I want the runtime to accept WEG effects artifacts of any image format,
So that `wallpaper set` works regardless of the source wallpaper's
extension (PNG, JPG, WebP, etc.).

## Scope Reality (READ FIRST)

This is a **VERIFY-STEP HARD-CODING bug in the WEG adapter**, not a
WEG protocol bug. WEG (correctly) produces effect artifacts in the
same extension as the source wallpaper — `.png` for PNG sources, `.jpg`
for JPG sources, `.webp` for WebP sources, etc. The runtime's
`WegAdapter.generate` was hardcoded to look for `.png` only, so any
non-PNG wallpaper caused a spurious
`weg did not write expected PNG artifacts: ... (found 20 files, 0 png)`
error even when WEG had successfully written 20 valid JPG artifacts.

This story does NOT touch:
- WEG's output format (WEG matches source extension — correct)
- The shared-data-contract cache layout
- The WEG catalog discovery (fixed in rt-3-6)
- The `drain_work_dir` fix (fixed in rt-3.6)
- The `populate_via_staging` / cache write path

## Acceptance Criteria

1. **WEG adapter accepts any common image extension** — Given WEG
   successfully writes artifacts to the output dir with any of
   `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`, `.gif`
   extensions, the runtime's verify step finds them and produces
   `EffectsEntry.artifact_hashes`. No more spurious
   `found 20 files, 0 png` errors.

2. **JPG wallpapers work end-to-end** — Running
   `dotfiles-runtime wallpaper set /path/to/aurora.jpg` produces:
   - `cache/effects/<eh>/aurora/effect/*.jpg` populated
   - `current/effects` symlink created
   - `current.json.effects` populated with a non-null hash

3. **PNG wallpapers still work** — No regression: `.png` wallpapers
   still produce `.png` effects in the cache. (The change broadens
   the accept list; it does not narrow it.)

4. **No regressions** — Full suite green: `pytest` + `ruff check src` +
   `ruff format --check src` + `mypy --strict src` +
   `pytest tests/architecture/test_layering.py`. Baseline at the time
   of writing: 3 ruff errors, 4 mypy errors, 0 format issues, 566
   tests pass (post-rt-3.6).

## Tasks / Subtasks

- [x] Task 1: Broaden the WEG artifact verify step (AC 1-3)
  - [x] In `WegAdapter.generate` (`adapters/weg_adapter.py:423-434`),
    replace the hardcoded `.png` suffix check with a set of common
    image extensions: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`,
    `.tiff`, `.gif`
  - [x] Update the comment to reflect the new behavior (no longer
    "Verify PNG artifacts" — now "Verify image artifacts")
  - [x] Update the error message to mention image files generically
    rather than PNG specifically
  - [x] Rename the local variable `png_files` to `image_files`
    throughout the verify-and-hash block
- [x] Task 2: Quality gates (AC 4)
  - [x] `uv run --directory src/runtime pytest` — 566+ passed, 2 skipped
  - [x] `uv run --directory src/runtime ruff check src` — 3 errors
    (baseline unchanged, same as rt-3.5/rt-3.6)
  - [x] `uv run --directory src/runtime ruff format --check src` — clean
  - [x] `uv run --directory src/runtime mypy --strict src` — 4 errors
    (baseline unchanged)
  - [x] `uv run --directory src/runtime pytest tests/architecture/test_layering.py -v` — 57 passed
  - [x] Verified end-to-end on host: `.jpg` wallpaper
    (`aurora.jpg`) and `.png` wallpaper (`wave.png`) both succeed;
    `cache/effects/<eh>/` populated with the right extension;
    `current.json.effects` non-null

## Dev Notes

### Why the bug existed

The WEG adapter was written with the assumption that WEG always
produces `.png`. This is true for PNG source wallpapers, but WEG
matches the source extension (per the `WegAdapter` docstring
"image extension matches the source"). The verify step was
hardcoded to `.png` as a lazy shortcut.

The pre-existing test suite for `WegAdapter` uses mocked subprocess
that only produces `.png` artifacts, so the bug wasn't caught by
unit tests. Integration tests use a `_FakeWeg` mock, not the real
WEG adapter.

### Relationship to rt-3-6

rt-3-6 fixed the WEG catalog discovery (so the effects cache is
populated at all). rt-3-7 fixes the verify step so it accepts the
artifacts WEG actually produces for non-PNG sources. Without rt-3-6,
the catalog was never found and no effects were generated — so the
`.jpg` verify bug was masked by the upstream discovery bug.

After both fixes, `wallpaper set` works for both PNG and JPG
wallpapers end-to-end.

### Scope boundary (READ FIRST)

This story fixes only the WEG adapter's verify step. It does NOT:
- Force WEG to always produce `.png` (WEG matches source by design)
- Change the cache layout (the `cache/effects/<eh>/<stem>/` structure
  is preserved as WEG produces it; the cache layout per
  `shared-data-contract.md` says `cache/effects/<eh>/*.png` — the
  `<stem>/` subdir is a separate structural issue tracked elsewhere)
- Touch the CSG or ITR adapters

## Dev Agent Record

### Agent Model Used

OpenCode powered by Meta Muse Spark (muse-spark-1.3-contributor-free)

### Debug Log References

- Baseline rt-3.6 gates re-verified live at start: `ruff check src` = 3,
  `mypy --strict src` = 4, `ruff format --check src` clean.
- Verified end-to-end before fix: `aurora.jpg` (JPG) wallpaper
  produced `weg did not write expected PNG artifacts: ... (found 20
  files, 0 png)` despite WEG writing 20 valid JPGs.
- Verified end-to-end after fix: `aurora.jpg` succeeds;
  `cache/effects/<eh>/aurora/effect/*.jpg` populated;
  `current/effects` symlink created; `current.json.effects` non-null.
- PNG wallpapers (`wave.png`) still work after the fix.
- Post-change gates: `ruff check src` = 3 (baseline unchanged, zero
  new), `ruff format --check src` clean, `mypy --strict src` = 4
  (baseline unchanged, zero new), `test_layering.py` 57 passed.

### Completion Notes List

- ✅ Task 1: Verify step broadened to accept `.png`, `.jpg`, `.jpeg`,
  `.webp`, `.bmp`, `.tiff`, `.gif` extensions. Local variable renamed
  to `image_files` for clarity.
- ✅ Task 2: All quality gates pass with zero new violations.

### File List

- `src/runtime/src/runtime/adapters/weg_adapter.py` (modified — Task 1)
