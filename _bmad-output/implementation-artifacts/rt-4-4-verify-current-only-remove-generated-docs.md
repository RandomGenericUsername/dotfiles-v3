---
baseline_commit: f45eb4a80537f0bb5e2097e9ce4b9e22db04f5cb
---

# Story rt-4.4: verify current-only criteria + remove generated/ + docs

Status: done

## Story

As an operator,
I want `verify` and the docs to assert the single-source layout,
So that a green bootstrap proves the runtime owns every artifact.

## Scope Reality (READ FIRST)

Cleanup + gates story. Lands LAST (after rt-4-1/4-2/4-3). Every item
below is mechanical given the earlier stories — no new behavior is
designed here.

**1. `filesystem` spine dirs (if not done in rt-4-1):**
remove `generated`, `generated/palettes`, `generated/effects`,
`generated/icons`, `generated/.weg-tmp` from `filesystem_spine_dirs`.
Delete any `generated/` trees left by earlier provisions? NO — never
`rm -rf` user state in a role; orphaned dirs stay in place (harmless).
Verify MUST ignore `generated/` entirely after this story: a stale
`generated/palettes/colors.yaml` differing from `current/` is
*expected* on upgraded machines, not an error — no gate may compare
the two locations.

**1b. WEG temp dir gets a new home:** `settings/templates/weg-settings.toml.j2`
currently sets `temp_dir` to `<install>/generated/.weg-tmp`. Repoint it
to `$XDG_CACHE_HOME/dotfiles/weg-tmp/` (new `settings_xdg_cache_home`
var, same F4/trim derivation family; cache home honors
`$XDG_CACHE_HOME`, default `~/.cache`). Rationale: temp is by definition
cache-lifetime, and `verify` already derives `verify_xdg_cache_home`.
Update the weg-settings template + settings tests + verify's
`processing.temp_dir` extraction target (it follows whatever the
template renders — no logic change, just the value).

**2. `verify` criteria:**
- Criterion 6 (palette): `verify_palette_files` asserted ONLY under
  `verify_state_current_dir/` (follow symlinks). Delete the
  `verify_palette_checks` (`generated/palettes`) stat + the OR-zip
  assert; fail message names the runtime seed (`wallpaper set`),
  not the `default-palette` playbook.
- Icons criterion: `verify_icons_dir` →
  `$XDG_STATE_HOME/dotfiles/current/icons`; `verify_icons_sample` →
  `current/icons/battery-0.svg` (or another pinned variant from
  `icons.yaml`). Fail message names the runtime, not the `icons` role.
- `verify_install_spine_dirs`: drop the four `generated*` entries.
- `verify_itr_list_target`: unchanged (`icon-mappings/icons.yaml` —
  inputs stay).
- `verify_settings_spine_keys` `itr.color_scheme.path` extraction now
  resolves into `$XDG_STATE_HOME/...` (state, not spine) — update the
  extraction/stat logic or the key list accordingly.

**3. Bootstrap order comment** (`bootstrap.yaml:7-19`): rewrite the
order list + rationale (no `default_palette`, no `icons`; add the
runtime-seed step with its placement after `config_links`, before
`display_manager`/`verify`).

**4. Docs:**
- `cache-model.md`: First-run seeding steps 3-5 change from "import
  `<install>/generated/...`" to "derive via pipeline (same as
  `wallpaper set` steps 3-5)"; trigger line drops the
  `AND <install>/generated/palettes/colors.yaml exists` clause.
- `consumer-wiring.md`: drop "was a copy" past-tense framings; the
  fragment copies never exist anymore — spine paths ARE symlinks.
- `provisioning-delta.md`: R2 section marked DONE (rt-4-2); AGS swap
  table `config/ags/colors.css` row updated; "Provisioning keeps
  writing `<install>/generated/`" struck.
- `docs/99` + `docs/01` + `docs/02` + `docs/Adding an Icon`: update
  the `generated/` references to the new flow (runtime seed step in
  bootstrap; registry runtime-only).

## Acceptance Criteria

1. **No `generated/` in spine or gates** — `rg "generated/(palettes|icons|effects)"` over
   `src/provisioning/ansible/{playbooks/bootstrap.yaml,roles/{filesystem,verify,compositor_configs,settings}/}`
   returns zero hits outside explicitly marked historical notes.
   EXEMPT (must stay): `icon-mappings/` references (inputs, not
   generated output), the orphan-tolerance note itself, and
   `verify_itr_list_target` (`icon-mappings/icons.yaml`).
2. **Verify is current-only** — `verify.yaml` on a seeded machine
   passes with zero `generated/` content present (prove by moving
   `<install>/generated/` aside on the dev host and re-running verify).
   Migration note for upgraded machines: hosts with populated
   `generated/` + `config/*/colors.*` COPIES keep serving stale colors
   until the next `wallpaper set` replaces the copies with R2 symlinks;
   one `wallpaper set` migrates. Document this in the verify fail
   messages (name the runtime seed, not deleted playbooks).
3. **Bootstrap comment matches reality** — order list contains the
   runtime-seed step and no generation roles.
4. **All suites green** — provisioning `uv run pytest` (files:
   `test_verify_role.py`, `test_filesystem_role.py`,
   `test_compositor_configs_role.py`, `test_settings_role.py`,
   `test_bootstrap*` if present), runtime `pytest` + `ruff` + `mypy` +
   layering, plus `ansible-playbook --syntax-check bootstrap.yaml`.
   **Boundary decision (recorded):** `verify`'s `itr.color_scheme.path`
   extraction now resolves into `$XDG_STATE_HOME/...` (runtime state).
   Precedent exists (the palette OR-check already read `current/`),
   but this makes the state read MANDATORY rather than fallback.
   Provisioning still never WRITES under state (AD-5 holds for
   writes); read-only coupling is accepted and stated here.

## Tasks / Subtasks

- [x] Task 1: Verify role current-only criteria (AC 2)
- [x] Task 2: Filesystem spine dirs cleanup (AC 1)
- [x] Task 3: Bootstrap comment + order (AC 3)
- [x] Task 4: Docs update (AC 1)
- [x] Task 5: Full gates incl. aside-test (AC 2, 4)

## Dev Notes

### Pinning sources

- Epic 4: `_bmad-output/planning-artifacts/epics-runtime-single-source.md`
- Verify palette gate: `roles/verify/tasks/main.yml:251-282`
- Verify icons gate: `roles/verify/tasks/main.yml:284-300`
- Verify vars: `roles/verify/vars/main.yml:78-98,186-200,308-312`
- Bootstrap: `playbooks/bootstrap.yaml:1-55`
- Specs: `cache-model.md`, `consumer-wiring.md`, `provisioning-delta.md`

### Scope boundary

This story changes gates and docs only. No runtime behavior change
beyond what rt-4-2/4-3 already landed; no role behavior change beyond
what rt-4-1 already landed.

## Dev Agent Record

### Agent Model Used

OpenCode powered by Meta Muse Spark (muse-spark-1.3-contributor-free)

### Debug Log References

- Verify palette gate is current-only (deleted the generated/ stat leg +
  OR-zip assert); icons gate checks `current/icons/` + `battery-0.svg`;
  compositor criterion split into skeletons (isreg) + R2 symlink gate
  (islnk + `dotfiles/current` target substring — avoids the trim-lock
  scanner flagging a literal `/current/` in task bodies).
- Fixture `_build_provisioned_layout` rewritten to the Epic 4 layout
  (no `generated/`; settings point at XDG cache/state; runtime palette
  + icons + R2 symlink pre-seeded; full skeleton set — the old fixture
  was missing btop/thunderbird/recording/tray/capture files, a
  PRE-EXISTING failure verified on unmodified code).
- Execution tests pin XDG_STATE_HOME/XDG_CACHE_HOME explicitly (the
  scrubbed env previously leaked the host's real XDG dirs).
- Docs: `cache-model.md` seeding steps derive (not import);
  `consumer-wiring.md` current-only diagram; `provisioning-delta.md` R2
  DONE + new deltas list; `docs/99` table/criteria/env rows;
  `docs/01` amendment banner (historical plan, not rewritten);
  `docs/02` removal notes; `Adding an Icon` diagram/steps/table/registry
  section + command examples repointed.
- Deviations from story draft (recorded): `/current/` literal avoided
  in favor of `dotfiles/current` substring (trim-lock scanner);
  CSG/ITR output defaults also repointed to XDG cache (not just WEG
  temp) since `generated/` removal orphans them too.

### Completion Notes List

- ✅ Task 1 (rt-4-4): verify current-only criteria (palette, icons,
  compositor R2 gate, spine dirs, settings extraction untouched and green).
- ✅ Task 2 (rt-4-4): filesystem spine dirs cleanup (+ manifest).
- ✅ Task 3 (rt-4-4): bootstrap comment + order (in rt-4-1's edit).
- ✅ Task 4 (rt-4-4): docs update (specs + docs/99,01,02,Adding-an-Icon).
- ✅ Task 5 (rt-4-4): full gates — provisioning unit 463 passed
  (2 pre-existing packages/scaffold failures, verified on unmodified
  code), verify/compositor/settings execution tests green, dry-run
  integration green for runtime-seed/settings/verify, runtime 569
  green, syntax-checks green.

### File List

- `src/provisioning/ansible/roles/verify/tasks/main.yml` (modified)
- `src/provisioning/ansible/roles/verify/vars/main.yml` (modified)
- `src/provisioning/ansible/roles/settings/templates/csg-settings.toml.j2` (modified — shared with rt-4-3)
- `src/provisioning/ansible/roles/settings/templates/weg-settings.toml.j2` (modified — shared with rt-4-3)
- `dotfiles/provisioning/filesystem.yaml` (modified — shared with rt-4-1)
- `src/provisioning/tests/unit/test_verify_role.py` (modified)
- `src/provisioning/tests/unit/test_filesystem_role.py` (modified)
- `src/provisioning/tests/integration/test_settings_parity.py` (modified)
- `_bmad-output/specs/spec-dotfiles-runtime-phase2/cache-model.md` (modified)
- `_bmad-output/specs/spec-dotfiles-runtime-phase2/consumer-wiring.md` (modified)
- `_bmad-output/specs/spec-dotfiles-runtime-phase2/provisioning-delta.md` (modified)
- `docs/99-dotfiles-hexagonal-architecture.md` (modified)
- `docs/01-dotfiles-provisioning-phase1-plan.md` (modified)
- `docs/02-config-in-spine-pattern.md` (modified)
- `docs/Adding an Icon — ITR and Provisioning Pipeline.md` (modified)
