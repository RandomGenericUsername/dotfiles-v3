---
baseline_commit: da4f78e08d8d3846dbbb3c67fa5156cd98ec5bf5
---

# Story rt-3-8: first-run seed looks for the wallpaper at the assets-role path

Status: review

## Story

As a user,
I want a freshly provisioned machine to seed its initial desktop state automatically,
So that I never perform manual seeding steps after bootstrap.

## Scope Reality (READ FIRST)

This is a **path bug in the first-run seed entry point**, not an
architectural change. The provisioning is correct: the assets role
(Story 2-6, Task 1) unpacks `wallpapers.tar.gz` to
`<install>/wallpapers/` including `default.png`, and asserts its
presence. The `cache-model.md` (First-run seeding, step 1) pins the
source: `Hash <install>/wallpapers/default.png → wh`.

The bug is in TWO places in the runtime that look for the wallpaper
at a path the provisioning does NOT create:

- `src/runtime/src/runtime/application/seed_cache.py:145`:
  `default_png = generated_dir / "default.png"` where
  `generated_dir = self._install_spine / "generated"`
- `src/runtime/src/runtime/cli/main.py:93` (the pre-validate guard):
  `default_png = install_spine / "generated" / "default.png"`

The story that authored these paths (rt-1-11 first-run-self-seeding,
Story Tasks §50.2-3, §Task-2 line 91) hardcodes
`install_spine/generated/default.png`, but no provisioning role
writes `default.png` under `generated/`. The assets role (Story 2-6,
Tasks §58-64, AC 2/11) unpacks the tarball to
`<install>/wallpapers/` and asserts `{{ install_dir }}/wallpapers/default.png`.

Symptom on a provisioned host:
```text
$ dotfiles-runtime wallpaper set ~/.local/share/dotfiles/wallpapers/wave.png
seed skipped: provisioning output not found
  (/home/inumaki/.local/share/dotfiles/generated/default.png);
  run provisioning to enable first-run seeding
```

Even on a freshly provisioned machine (where `default.png` IS at
`<install>/wallpapers/default.png`), the seed never runs because the
guard checks a path that doesn't exist.

This story does NOT touch:
- The `DerivationPipeline` (correct — re-derives palette/effects/icons
  via CSG/WEG/ITR subprocess calls)
- The `<install>/generated/` pre-rendered palette/effects/icons
  (provisioning's `default_palette` / `icons` roles — still used for
  the verify criteria and the AGS `IconRegistry` fallback; the
  architectural change to remove them is a separate epic)
- The first-run seed flow (load → mutual-exclusion → derive → save);
  only the entry *precondition* (where to find `default.png`) changes
- The CSG / WEG / ITR adapters' discovery (rt-3.5 / rt-3.6)
- The AGS `IconRegistry` `generated/` fallback (separate change)

## Acceptance Criteria

1. **Seed looks for `default.png` at the assets-role path** — Given
   `<install>/wallpapers/default.png` exists (the actual provisioning
   output, Story 2-6), `SeedCacheUseCase.run()` proceeds past the
   precondition instead of raising `RuntimeError("default wallpaper
   not found: <install>/generated/default.png")`. The guard no longer
   references `<install>/generated/` for the wallpaper.

2. **CLI pre-validate guard matches** — Given
   `<install>/wallpapers/default.png` exists,
   `_run_seed_if_needed()` does NOT log
   `"seed skipped: provisioning output not found"` and instead
   proceeds to construct the use case. If the file is truly absent
   (provisioning didn't run), it still skips quietly with a warning
   that names the correct path.

3. **Tests use the correct provisioning path** — All `seed_cache`
   test fixtures that build a fake `install_spine` create
   `<install>/wallpapers/default.png` (not
   `<install>/generated/default.png`). The error-message assertions
   match the new wording.

4. **No regressions** — Full suite green: `pytest` + `ruff check src` +
   `ruff format --check src` + `mypy --strict src` +
   `pytest tests/architecture/test_layering.py`. Baseline at the time
   of writing: 3 ruff errors, 4 mypy errors, 0 format issues, 566
   tests pass (post-rt-3.7).

## Tasks / Subtasks

- [x] Task 1: Fix `SeedCacheUseCase.run()` precondition (AC 1)
  - [x] In `application/seed_cache.py` (the `# 2. Verify provisioning
    output exists` block): replace
    `generated_dir = self._install_spine / "generated"` +
    `default_png = generated_dir / "default.png"` with
    `wallpapers_dir = self._install_spine / "wallpapers"` +
    `default_png = wallpapers_dir / "default.png"`. Remove the
    `generated/` dir check (it's not where the wallpaper is).
  - [x] Update the error message to name the correct path and to
    reference the assets role (Story 2-6) as the producer.
  - [x] Update the `run()` docstring (`2. Verify install_spine/...`
    step) to name the assets-role path.
- [x] Task 2: Fix CLI pre-validate guard (AC 2)
  - [x] In `cli/main.py` (`_run_seed_if_needed`): replace
    `default_png = install_spine / "generated" / "default.png"` with
    `default_png = install_spine / "wallpapers" / "default.png"`.
  - [x] Update the comment to reference Story 2-6 AC 2.
- [x] Task 3: Update test fixtures (AC 3)
  - [x] `src/runtime/tests/unit/test_seed_cache.py` `_make_use_case` /
    `_setup_spine` helper: create
    `<install>/wallpapers/default.png` instead of
    `<install>/generated/default.png`. Update the "raises when
    missing" test to create the parent `wallpapers/` dir and to
    match the new `"default wallpaper not found"` error text.
  - [x] `src/runtime/tests/integration/test_seed_cache_integration.py`
    `_setup` helper: same change.
  - [x] `src/runtime/tests/integration/test_reconcile_integration.py`
    `_setup` helper: same change.
  - [x] `src/runtime/tests/integration/test_apply_wallpaper_integration.py`
    `_setup` helper: same change.
  - [x] `src/runtime/tests/integration/test_crash_recovery_integration.py`
    `_setup` helper: same change.
- [x] Task 4: Quality gates (AC 4)
  - [x] `uv run --directory src/runtime pytest` — 566 passed, 2 skipped
  - [x] `uv run --directory src/runtime ruff check src` — 3 errors
    (baseline unchanged)
  - [x] `uv run --directory src/runtime ruff format --check src` — clean
  - [x] `uv run --directory src/runtime mypy --strict src` — 4 errors
    (baseline unchanged)
  - [x] `uv run --directory src/runtime pytest tests/architecture/test_layering.py -v` — 57 passed

## Dev Notes

### Pinning sources (cite in code comments)

- Provisioning: Story 2-6 (assets role), Tasks §58-64 (the `unarchive`
  task unpacks to `<install>/wallpapers/`; the stat+assert pair
  targets `<install>/wallpapers/default.png`), AC 2 ("`dotfiles/assets/...
  wallpapers.tar.gz` unpacks to `<install>/wallpapers/` including
  `default.png`"), AC 11 (`default.png` stat+assert, gated
  `when: not ansible_check_mode`).
- Provisioning: Story 2-12 (verify role) criterion 4 — stat+assert
  pair for `{{ install_dir }}/wallpapers/default.png` (assert gated
  `when: not ansible_check_mode`).
- Architecture: `cache-model.md` First-run seeding step 1:
  "`Hash <install>/wallpapers/default.png`".
- Domain: `src/provisioning/src/provisioning/domain/enums.py:100-101`
  (`AssetKind.ICON_TEMPLATE.spine_segment() == "icon-templates"`,
  `AssetKind.ICON_MAPPING.spine_segment() == "icon-mappings"` — the
  assets role's other paths, same file).

### Why the bug existed

Story 1.11 (rt-1-11 first-run-self-seeding, commit `d953a29`) authored
`seed_cache.py` with Tasks §50.2-3 ("Verify `install_spine /
"generated"` exists") and Task-2 line 91 ("Copying
`install_spine/generated/default.png` into `cache/wallpapers/<wh>/wallpaper.png`").

The author conflated two distinct provisioning outputs:
- `default.png` (the wallpaper SOURCE, deployed by the assets role
  via `unarchive` to `<install>/wallpapers/`)
- `generated/palettes/colors.*` (the pre-rendered PALETTE,
  generated by the `default_palette` role via `csg generate` into
  `<install>/generated/palettes/`)

The seed then uses `DerivationPipeline.ensure_palette()` (line 248),
which RE-DERIVES the palette via CSG anyway — the
`<install>/generated/palettes/` pre-render is never actually read by
the seed. The `generated/` dir check (lines 138-143) was a stale
precondition from an earlier design where the seed would IMPORT
pre-rendered artifacts instead of RE-DERIVING them.

The spec (`cache-model.md` steps 3-5) also says "import" (from
generated), but the implementation (Story 1.11) re-derives. The
re-derive approach is what was actually shipped, and it produces
correct cache entry hashes (matching the same WEG/ITR hash formula
the runtime uses elsewhere). So the `generated/` check was dead
weight even before this fix.

### Scope boundary (READ FIRST)

This story fixes only the precondition (where to find `default.png`).
It does NOT:
- Change the rest of the seed flow (load → mutex → derive → save)
- Remove the `default_palette` / `icons` provisioning roles
  (the architectural duality change is a separate epic)
- Change the `<install>/generated/` verify criteria
  (Story 2-12 criterion 6 — separate change)
- Change the AGS `IconRegistry` `generated/` fallback
  (separate change)

## Dev Agent Record

### Agent Model Used

OpenCode powered by Meta Muse Spark (muse-spark-1.3-contributor-free)

### Debug Log References

- Baseline rt-3.7 gates re-verified live at start: `ruff check src` = 3,
  `mypy --strict src` = 4, `ruff format --check src` clean.
- Verified end-to-end before fix:
  `seed skipped: provisioning output not found
  (/home/inumaki/.local/share/dotfiles/generated/default.png)`
  on a provisioned host (where `default.png` exists at
  `<install>/wallpapers/default.png`).
- Post-change end-to-end (on a host with existing `current.json`, the
  seed is a no-op so the change is verified by the full test suite
  and by manual inspection of the new guard path).
- 5 test files updated (1 unit + 4 integration) to create
  `<install>/wallpapers/default.png` in their fake install spines.
- Post-change gates: `ruff check src` = 3 (baseline unchanged, zero
  new), `ruff format --check src` clean, `mypy --strict src` = 4
  (baseline unchanged, zero new), `test_layering.py` 57 passed.

### Completion Notes List

- ✅ Task 1: `seed_cache.py` precondition rewritten to look for
  `<install>/wallpapers/default.png` (the actual assets-role output).
  The `generated/` dir check was removed (not where the wallpaper is).
  Error message names the correct path + the assets role.
- ✅ Task 2: CLI `_run_seed_if_needed()` pre-validate guard updated to
  the same path.
- ✅ Task 3: 5 test files updated (their fake install spines now
  create the wallpaper at the correct path).
- ✅ Task 4: All quality gates pass with zero new violations.

### File List

- `src/runtime/src/runtime/application/seed_cache.py` (modified — Task 1)
- `src/runtime/src/runtime/cli/main.py` (modified — Task 2)
- `src/runtime/tests/unit/test_seed_cache.py` (modified — Task 3)
- `src/runtime/tests/integration/test_seed_cache_integration.py` (modified — Task 3)
- `src/runtime/tests/integration/test_reconcile_integration.py` (modified — Task 3)
- `src/runtime/tests/integration/test_apply_wallpaper_integration.py` (modified — Task 3)
- `src/runtime/tests/integration/test_crash_recovery_integration.py` (modified — Task 3)
