---
baseline_commit: 7dc11e63110f27fa029f8a037f46a367c7630e47
---
# Story 1.12: Provisioning don't-clobber guard

Status: done

## Story

As a user,
I want provisioning re-applies to respect runtime-owned consumer symlinks,
so that my configured wallpaper survives a `dotfiles-provision apply` re-run.

## Acceptance Criteria

1. **Given** `<install>/config/hypr/colors.conf` and/or `<install>/config/ags/colors.css` are already runtime symlinks (symlinks resolving into `$XDG_STATE_HOME/dotfiles/current/`), **When** the `compositor_configs` role runs again (fragment-copy task), **Then** those runtime symlinks are left untouched — no file is written over them. (AC 1, FR-9, R3, AD-17)

2. **Given** a fresh machine (destination paths absent, or present as plain copies that are NOT runtime symlinks), **When** `compositor_configs` runs, **Then** the palette fragments are still copied as before — Phase-1 overwrite behavior is unchanged for every non-runtime-owned destination. (AC 2, provisioning-delta "What does NOT change")

3. **Given** the `config_copies` role runs and a palette-format symlink (`colors.conf`/`colors.css`/`colors.gtk.css`/`colors.yaml` — e.g. a runtime-owned symlink resolving into `state_root/current/`) exists inside a managed copy destination (`<install>/config/{nvim,starship,wlogout,zsh}/`), **When** the copy task would overwrite it, **Then** provisioning fails loud with a clear message instead of silently clobbering (none of the four entries contain colors files today; the guard is an invariant tripwire that flags ANY palette-format symlink, since provisioning never creates such links). (AC 3, FR-9)

4. **Given** `dotfiles-provision verify` runs on a post-runtime machine, **When** done-criterion 6 is evaluated, **Then** it passes if each palette file (`colors.conf`, `colors.yaml`, `colors.gtk.css`) is present as a regular file under `<install>/generated/palettes/` (pre-runtime) **OR** present via `$XDG_STATE_HOME/dotfiles/current/<file>` resolving to a regular file (post-runtime). Criterion 6 must no longer hard-fail on a machine where the runtime consumed the palette. (AC 4, FR-9, provisioning-delta §deltas item 2)

5. **Given** the hexagonal/boundary rules (AD-5, NFR-1), **When** the guard is added, **Then** provisioning only READS `state_root` (stat/classify — never writes under `$XDG_STATE_HOME/dotfiles/`), all existing role conventions hold (fail-loud asserts first, no `become`, no hardcoded absolute paths, non-deprecated env-fact vars, check-gated state asserts), and the structural test suites stay green. (AC 5)

## Tasks / Subtasks

- [x] Task 1 — `compositor_configs`: classify fragment destinations before copying (AC: 1, 2, 5)
  - [x] In `src/provisioning/ansible/roles/compositor_configs/vars/main.yml` add the state vars, mirroring the existing non-deprecated env-fact pattern (`verify_xdg_state_home`, `filesystem_xdg_state_home`):
    ```yaml
    compositor_configs_xdg_state_home: "{{ ansible_facts.env.XDG_STATE_HOME | default(ansible_facts.env.HOME | default(ansible_facts.user_dir) + '/.local/state', true) }}"
    compositor_configs_state_current_dir: "{{ compositor_configs_xdg_state_home | trim }}/dotfiles/current"
    ```
  - [x] In `src/provisioning/ansible/roles/compositor_configs/tasks/main.yml`, immediately BEFORE the "Place palette color fragments" task (currently L92-98), add a classification pass — stat each fragment dest with `follow: false` (read-only, safe ungated so `plan`/`--check` predicts correctly):
    ```yaml
    - name: Classify palette fragment destinations (runtime-symlink guard)
      ansible.builtin.stat:
        path: "{{ item.dest }}"
        follow: false
      loop: "{{ compositor_configs_fragment_copies }}"
      register: compositor_configs_fragment_stats
    ```
  - [x] Define "runtime symlink" classification (protected) exactly as: `stat.exists AND stat.islnk AND (stat.lnk_target is match('^' ~ compositor_configs_state_current_dir) or '/current/' in stat.lnk_target)`. The `'/current/' in` fallback covers seeder-written relative targets; `stat.follow: false` is mandatory — a plain `stat` (default `follow: true`) resolves through to the cache artifact and hides the link.
  - [x] Modify the "Place palette color fragments" copy task to skip protected destinations per item:
    ```yaml
    - name: Place palette color fragments
      ansible.builtin.copy:
        src: "{{ item.source }}"
        dest: "{{ item.dest }}"
        remote_src: true
      loop: "{{ compositor_configs_fragment_copies }}"
      loop_control:
        index_var: compositor_configs_frag_idx
      when:
        - not ansible_check_mode
        - not (compositor_configs_fragment_stats.results[compositor_configs_frag_idx].stat.exists
               and compositor_configs_fragment_stats.results[compositor_configs_frag_idx].stat.islnk
               and (compositor_configs_fragment_stats.results[compositor_configs_frag_idx].stat.lnk_target | default('') is match('^' ~ compositor_configs_state_current_dir)
                    or '/current/' in (compositor_configs_fragment_stats.results[compositor_configs_frag_idx].stat.lnk_target | default(''))))
    ```
    Use a named registered var for the classification expression (e.g. a `set_fact` of per-item `compositor_configs_frag_is_runtime_link` booleans built from the registered loop) if the inline expression becomes unreadable — prefer one readable boolean over a 9-line `when`. NOTE: the copy task's `when` becomes a LIST (check-gate + guard condition) — this breaks the exact-string test assertion (see Task 4 MUST-UPDATE items).
  - [x] Update the role's invariant header comment (the one `test_invariant_documented_in_task_header` checks): fragments are now "overwrite UNLESS the destination is a runtime symlink into state_root/current (don't-clobber guard, Story 1.12)".
  - [x] The existing fragment-source stat+assert pair (L75-90) stays unchanged. Rationale: `bootstrap.yaml` runs `default_palette` BEFORE `compositor_configs` (bootstrap.yaml L46-47), so sources exist on every apply; provisioning keeps writing `<install>/generated/palettes/` post-runtime (AD-17 "Phase-1 behavior unchanged"), so a missing source is a genuine failure in every reachable state. Do NOT add a runtime-link exemption here.

- [x] Task 2 — `config_copies`: fail-loud tripwire for runtime symlinks inside managed dirs (AC: 3, 5)
  - [x] In `src/provisioning/ansible/roles/config_copies/vars/main.yml`: NO new state vars — the tripwire is deliberately broader than a target-match (any palette-format symlink inside a managed copy destination fails loud; provisioning never creates such links, so this catches runtime ones and any other drift).
  - [x] In `src/provisioning/ansible/roles/config_copies/tasks/main.yml`, before the "Copy configs into the config-in-spine home" task (L107-112), add an ungated `ansible.builtin.find` over each managed dest dir:
    ```yaml
    - name: Find palette-format symlinks inside managed copy destinations
      ansible.builtin.find:
        paths: "{{ config_copies_spine_config_dir }}/{{ item.target }}"
        file_type: link
        recurse: true
        patterns: "{{ config_copies_guard_patterns }}"
      loop: "{{ config_copies_entries }}"
      register: config_copies_runtime_link_scan
    ```
    with `config_copies_guard_patterns: ["colors.conf", "colors.css", "colors.gtk.css", "colors.yaml"]` in vars. Then assert (check-gated, fail-loud, with a vacuous-pass guard so skipped/empty results can't fake a pass):
    ```yaml
    - name: Assert no palette symlinks would be clobbered
      ansible.builtin.assert:
        that:
          - config_copies_runtime_link_scan.results | length == config_copies_entries | length
          - config_copies_runtime_link_scan.results | map(attribute='files', default=[]) | flatten | length == 0
        fail_msg: >-
          palette-format symlink(s) found inside config_copies managed destinations —
          the recursive copy (force: true) would clobber them. Runtime consumer flips
          target compositor_configs paths only; investigate before re-applying.
      when: not ansible_check_mode
    ```
    Rationale: a dir-copy cannot skip individual files, and excluding a whole dir would freeze a stale copy (explicitly rejected by the role's own design comment at tasks L39-45). Fail-loud is the only honest option; today this can never fire (no colors files under nvim/starship/wlogout/zsh) — it is a tripwire for future drift.
  - [x] Document the guard in the role's task header comment alongside the existing "NOT force: false" design note.

- [x] Task 3 — `verify`: relax done-criterion 6 (AC: 4, 5)
  - [x] In `src/provisioning/ansible/roles/verify/tasks/main.yml` (criterion 6 block, L232-247) and `vars/main.yml` (L173-176 `verify_palette_files`): change the assert from "all three files are `isreg` under `<install>/generated/palettes/`" to "for each file, isreg under generated/palettes/ OR isreg at `<verify_xdg_state_home>/dotfiles/current/<file>`". Reuse the EXISTING `verify_xdg_state_home` var (verify vars L48) — derive `verify_state_current_dir` from it; do not introduce a second XDG resolution.
  - [x] Stat both candidate paths per file with default `follow: true` so a healthy runtime symlink chain (`current/colors.conf → cache/palettes/<ph>/colors.conf`) resolves to `isreg` and passes. A DANGLING runtime symlink (broken cache entry) correctly fails — the filesystem is authority (NFR-3) and verify must signal broken state.
  - [x] Update the fail_msg to enumerate both accepted locations.
  - [x] Keep the relaxed assert check-gated (`when: not ansible_check_mode`) and use UNIQUE register names for any new stat loop — `test_every_state_assert_is_check_gated` (test_verify_role.py:462-483) enforces the gate on every state assert beyond the four seam asserts, and per-test register uniqueness is an existing convention (test_verify_role.py:231-232).
  - [x] Keep criterion 7 (`verify_compositor_fragments` stat at tasks L418-436) UNCHANGED: default `stat` follows symlinks, so a post-runtime `<install>/config/hypr/colors.conf → current/colors.conf → cache/...` still stats `isreg`. Do not relax criterion 7 (the provisioning-delta pins only criterion 6 as relaxed).
  - [x] Update the done-criteria map comment in the verify tasks header (criterion 6 wording: "generated OR current palette presence").

- [x] Task 4 — Tests: extend structural + integration suites (AC: 1, 2, 3, 4, 5)
  - [x] `src/provisioning/tests/unit/test_compositor_configs_role.py`:
    - [x] Add: guard classification stat-task contract (`follow: false`, loops `compositor_configs_fragment_copies`, register `compositor_configs_fragment_stats`, UNGATED — no `when`).
    - [x] Add: fragment copy task carries the per-item skip — `when` is now a LIST (`not ansible_check_mode` + guard condition).
    - [x] **MUST UPDATE** `test_fragment_sources_stat_plus_assert_pair` (L303-313): it collects EVERY stat task looping `compositor_configs_fragment_copies` and asserts per-task `register == "compositor_configs_fragment_check"` + `when == "not ansible_check_mode"` — the new classification task fails BOTH assertions. Scope its collection to register `compositor_configs_fragment_check` (the source pair) and cover the classification task via the new contract test above.
    - [x] **MUST UPDATE** `test_fragment_copies_carry_no_creates_and_are_check_gated` (L281-299): it asserts exact string equality `task.get("when") == "not ansible_check_mode"` (L292) — a list `when` fails this. Update to assert the `when` LIST contains the check-gate item AND the guard condition; keep the no-`creates:` assertion.
    - [x] Update: `test_invariant_documented_in_task_header` for the new guard wording.
    - [x] Update: `test_vars_use_non_deprecated_env_fact` coverage if it enumerates vars — new `XDG_STATE_HOME` var must use the same non-deprecated env-fact pattern.
  - [x] `src/provisioning/tests/unit/test_config_copies_role.py`:
    - [x] Add: find-task contract test (ungated, `file_type: link`, `recurse: true`, loops entries, patterns from vars).
    - [x] Add: assert-task contract test (fail-loud message, check-gated).
    - [x] Add: vars parity — `config_copies_guard_patterns` locked to the four colors filenames.
  - [x] `src/provisioning/tests/unit/test_verify_role.py`:
    - [x] Update: `test_palette_files_match_chain_formats` / criterion-6 locks for the OR-acceptance.
    - [x] Add: verify vars expose `verify_state_current_dir` derived from `verify_xdg_state_home` (no duplicate XDG resolution).
    - [x] Add: criterion-6 stat/assert block references both paths.
  - [x] Integration `test_playbook_executes_and_places_skeletons_and_fragments` (in `test_compositor_configs_role.py`):
    - [x] Fresh-machine path: keep existing assertions (both fragments land as regular files).
    - [x] Add a scenario: pre-create `<install>/config/ags/colors.css` as a symlink into a fake `<tmp>/state/dotfiles/current/colors.gtk.css` (export `XDG_STATE_HOME=<tmp>/state` in the playbook-run env), re-run the playbook, assert the symlink is UNCHANGED (`islnk`, same target) and the other fragment (`hypr/colors.conf`, absent) is still copied fresh.
  - [x] Extend `src/provisioning/tests/integration/test_apply_verify_container.py` — `_run_env()` already exports `XDG_STATE_HOME: /scratch/state` (L122); use it. Add a post-runtime criterion-6 scenario: after apply, create `/scratch/state/dotfiles/current/colors.conf` as a regular file, DELETE `generated/palettes/colors.conf`, re-run verify — it must pass via the `current/` leg with everything else green. And a pre-runtime negative: `generated/palettes/colors.conf` missing AND no `current/` file → criterion 6 fails.
  - [x] Full green gate (mirrors Story 1.11's):
    ```bash
    uv run --directory src/provisioning pytest -q
    uv run --directory src/provisioning ruff check src/provisioning
    uv run --directory src/provisioning ruff format --check src/provisioning
    uv run --directory src/provisioning mypy --strict src/provisioning
    ```

## Dev Notes

### Scope boundary — provisioning-side only

This story changes ONLY `src/provisioning/` (Ansible roles + tests). It does NOT touch `src/runtime/`. The seeder (Story 1.11, done) already creates the runtime symlinks inside state_root; the *consumer-path flip* (`<install>/config/hypr/colors.conf` → `current/colors.conf`, `<install>/config/ags/colors.css` → `current/colors.gtk.css`) is performed by the runtime seeder / a later `IDesktopConfigWriter` adapter (port exists, no adapter yet) — this story just makes provisioning STOP DESTROYING those links once they exist. Hyprpaper conf and ITR `settings.toml [color_scheme] path` rewrites are runtime-side (provisioning-delta table rows 3-4) — out of scope here.

### Where the clobber actually happens (verified in code)

| Hazard | File | Current behavior |
|---|---|---|
| `compositor_configs` fragment copies | `src/provisioning/ansible/roles/compositor_configs/tasks/main.yml` L92-98 + vars L111-113 | `ansible.builtin.copy` with NO `force:` key → Ansible default `force: true` → **unconditional overwrite on every apply**, over a runtime symlink this replaces the link with a stale plain copy |
| `config_copies` recursive dir copies | `src/provisioning/ansible/roles/config_copies/tasks/main.yml` L107-112 | dir→dir copy, default force + checksum idempotency; would clobber any runtime symlink nested inside — none exist today (entries: nvim/starship/wlogout/zsh) |
| `config_links` backup guard | `roles/config_links/tasks/_link_one.yml` L33-82 | classifies only top-level `~/.config/<name>` nodes — blind to symlinks INSIDE managed dirs; no change needed (it never writes colors files) |

The two fragment copies are: `generated/palettes/colors.conf` → `<install>/config/hypr/colors.conf` and `generated/palettes/colors.gtk.css` → `<install>/config/ags/colors.css` (note the RENAME — locked by `test_fragment_copy_pair_locks_the_rename`; keep it exactly).

### Ansible module semantics the dev must not get wrong

- `ansible.builtin.copy` / `template` default `force: true` — omitting `force:` does NOT mean "don't overwrite".
- `force: false` on a directory src with a pre-existing dest dir is a SILENT NO-OP (review finding 2026-08-12, recorded in config_copies tasks L39-45) — this is why the guard is skip-per-item (compositor_configs, per-file fragments) or fail-loud (config_copies, dir copies), never `force: false`.
- `ansible.builtin.stat` defaults `follow: true` — `islnk` is ALWAYS false unless `follow: false` is set. `stat.lnk_target` is the RAW target string (not resolved), so match on prefix/substring, and `| default('')` it (absent key when not a link).
- `ansible.builtin.find` with `file_type: link` reports `files` entries with `islnk`; use `| map(attribute='files', default=[]) | flatten` over registered loop results (missing `default=` breaks on skipped/empty results).
- In check mode, `register` on skipped tasks yields `skipped: true` results with no `stat` — index into results defensively if the classification pass could skip (it must NOT be check-gated precisely so this can't happen).

### XDG / path resolution pattern (reuse, don't reinvent)

Provisioning never reads state_root today; derive it exactly like the existing vars: `ansible_facts.env.XDG_STATE_HOME | default(HOME-derived, true)`. Precedents: `verify_xdg_state_home` (`roles/verify/vars/main.yml` L48), `filesystem_xdg_state_home` (`roles/filesystem/vars/main.yml` L24). Structural tests enforce the non-deprecated env-fact pattern (`test_vars_use_non_deprecated_env_fact` in both role test files) — copy their shape. State root is ALWAYS `<XDG_STATE_HOME>/dotfiles/` with `current/` inside it (AD-5); the seeder writes ABSOLUTE symlink targets (Story 1.11 review remediation: "absolute path resolution") but keep the `'/current/' in` substring fallback for defense.

### Boundary rules (AD-5 / AD-11 / AD-15)

- Provisioning READS `state_root` for classification only — zero writes under `$XDG_STATE_HOME/dotfiles/` ever.
- Provisioning keeps writing `<install>/generated/palettes/` unconditionally (the seed source, FR-5 depends on it) and keeps its pre-runtime copies — Phase-1 behavior otherwise unchanged (provisioning-delta §"What does NOT change").
- No runtime knowledge leaks into provisioning: guard classifies by symlink-target geometry, not by reading `current.json` or importing runtime code.

### Known asymmetries and deliberate deviations (do not "fix")

- **Check-mode asymmetry between the two roles is intentional:** the `compositor_configs` fragment copy is check-gated (`when: not ansible_check_mode` — sources are legitimately absent under `--check`), while the `config_copies` copy task is NOT gated and never may be (`test_copy_task_contract` asserts `task.get("when") is None`, test_config_copies_role.py:371-373). Preserve both; do not harmonize.
- **AC 1 is a forward-guard:** the consumer-path flip adapter (`IDesktopConfigWriter`) does not exist yet (port only, no adapter, seeder only repoints `state_root/current/*`), so no production runtime symlink exists today. Tests exercise the guard synthetically (pre-created symlinks in fixtures).
- **AC 4 is a deliberate generalization of the spec text:** provisioning-delta/consumer-wiring name only `colors.yaml` in the OR-relaxation; this story relaxes all three palette files, matching AD-17's generic "generated OR current" and the epics' "palette presence" wording. Recorded here so the deviation is a decision, not an oversight.

### Previous story intelligence (Story 1.11 review findings that apply here)

- Structural tests in this repo LOCK exact task shapes (names, force keys, when-gates, loop vars) — expect to update `test_fragment_copies_carry_no_creates_and_are_check_gated`-adjacent locks and the invariant-header test, and add locks for the new guard tasks. Do not weaken existing locks silently.
- Absolute-vs-relative path handling bit Story 1.11 (dangling symlinks from relative XDG values) — always `| trim` install_dir-style vars and derive state paths from the resolved home.
- Integration tests here execute REAL `ansible-playbook` against temp `HOME`/`XDG_CONFIG_HOME`/`install_dir` when ansible is installed — the runtime-symlink scenario test must export `XDG_STATE_HOME` into that env too.
- Fail-loud over silent-skip is the house style for invariant violations (all roles open with fail-loud asserts); the config_copies tripwire follows it.

### Git intelligence (recent work)

`7dc11e6` HEAD; Story 1.11 landed at `d953a29` (seeder + SeedCacheUseCase + CLI hook); `b520776`/`94be1df` (GloView workspace provisioning) are unrelated to this story but touched `dotfiles/config/hypr/` — do not revert or disturb those skeleton files; the guard work touches only role tasks/vars/tests, never the skeleton configs.

### Testing standards summary

- Runner: `uv run --directory src/provisioning pytest` (unit tests parse real role YAML; integration tests run real ansible when available — they skip gracefully if `ansible-playbook` is absent, keep that skip pattern).
- Lint/type: `ruff check`, `ruff format --check`, `mypy --strict` on `src/provisioning`.
- Layering test (`tests/architecture/test_layering.py`) untouched — no Python hexagon code changes (pure Ansible role deltas), but keep it green.
- Assertion style for the new tests: structural contract tests assert exact task attributes (follow:false, when-clause, loop vars, registered names); integration tests assert filesystem outcomes (islnk + target unchanged after re-run).

### Project Structure Notes

- All changes are confined to `src/provisioning/ansible/roles/{compositor_configs,config_copies,verify}/{tasks,vars}/main.yml` and `src/provisioning/tests/unit/{test_compositor_configs_role,test_config_copies_role,test_verify_role}.py` + the two integration test files.
- No manifest changes (`dotfiles/provisioning/*.yaml` untouched — the guard is role-internal, and Ansible does not read manifests; parity tests stay valid).
- No playbooks changed (bootstrap.yaml ordering already runs compositor-configs before config-copies; guard is inside the roles).

### References

- Epics: `_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md` — Story 1.12 ACs; Implementation notes R2/R3 (consumer flip owned by seeder; don't-clobber guard)
- Architecture spine: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md` — AD-5 (state_root ownership), AD-6 (swap), AD-11 (seeding), AD-17 (consumer wiring + "verify criterion 6 relaxes to generated OR current" + "compositor_configs/config_copies add a don't-clobber guard" — verbatim story mandate)
- Shared data contract: same folder `shared-data-contract.md` — Swap sequence (what the seeder already wrote)
- Specs: `_bmad-output/specs/spec-dotfiles-runtime-phase2/provisioning-delta.md` (deltas 1-3 + boundary rule) and `consumer-wiring.md` (the exact consumer-path chains and the provisioning deltas list)
- Previous story: `_bmad-output/implementation-artifacts/rt-1-11-first-run-self-seeding.md` — seeder symlink targets (`adapters/seeder.py` `repoint_current_symlinks`), absolute-path remediation, review process lessons
- Provisioning code: `src/provisioning/ansible/roles/compositor_configs/tasks/main.yml` (fragment copies L92-98, source asserts L75-90), `vars/main.yml` (fragment list L111-113, spine dirs L33-64), `src/provisioning/ansible/roles/config_copies/tasks/main.yml` (copy L107-112, design note L39-45, dest-isdir resolve pair L114-132), `src/provisioning/ansible/roles/verify/tasks/main.yml` (criterion 6 L232-247, criterion 7 L418-436, header L8-35), `vars/main.yml` (`verify_palette_files` L173-176, `verify_xdg_state_home` L48, `verify_compositor_fragments` L226-228)

## Dev Agent Record

### Agent Model Used

opencode-go/glm-5.3-flash (GLM, Z.ai)

### Debug Log References

- Full suite (excl. container file): 560 passed, 5 failed (ALL 5 pre-existing at baseline 7dc11e6, verified via git worktree), 1 skipped
- Container file: 1 passed (packages --check yay proof), 2 skipped (documented honest gate: no nested engine inside the disposable target)
- ruff check / ruff format --check / mypy --strict on src/provisioning: all green

### Completion Notes List

- **Task 1 (compositor_configs):** added `compositor_configs_xdg_state_home` + `compositor_configs_state_current_dir` vars (verbatim story derivation, F4-lock env-fact pattern, trim lock); added the ungated `follow: false` destination-classification stat registering `compositor_configs_fragment_stats`; the fragment copy now loops with `loop_control.index_var: compositor_configs_frag_idx` and a LIST `when` (check-gate + inline per-item guard: exists AND islnk AND (lnk_target matches `^<state>/dotfiles/current` OR contains `/current/`), `| default('')`-defended). Fragment-source stat+assert pair untouched. Header documents the guard.
- **Task 2 (config_copies):** added `config_copies_guard_patterns` (locked to the four colors filenames) and the ungated `find` scan (`file_type: link`, `recurse: true`) + check-gated fail-loud assert (results-parity vacuous-pass guard + `map(attribute='files', default=[]) | flatten | length == 0`) before the copy. No new state vars beyond the patterns list. Header documents the tripwire.
- **Task 3 (verify):** criterion 6 now stats BOTH locations — generated/palettes/<file> (register `verify_palette_checks`, unchanged shape) and `<verify_state_current_dir>/<file>` (new register `verify_palette_current_checks`) — with ONE check-gated assert doing a per-file OR via `zip` + `map(attribute='stat.isreg', default=false)` + `map('max') | select`. fail_msg enumerates both accepted locations. `verify_state_current_dir` derives from the EXISTING `verify_xdg_state_home` (no second XDG read). Criterion 7 untouched. Done-criteria header map updated ("generated OR current").
- **DELIBERATE DEVIATION (recorded decision, not an oversight):** the story's Task 3 said to stat the current-dir leg with "default `follow: true`". The installed ansible-core's `ansible.builtin.stat` argument spec has `follow=dict(type='bool', default=False)` — the default does NOT follow, so a healthy runtime symlink chain reported `isreg: false` and the first runtime test failed. Fixed by setting `follow: true` EXPLICITLY on the current-dir stat task (matches the story's stated INTENT: the healthy chain must resolve to isreg while a dangling link fails); structural lock updated accordingly. Same latent hazard exists for criterion 7's stat (out of scope, untouched, noted for review).
- **Pre-existing baseline failures (NOT introduced by this story; verified failing identically at baseline 7dc11e6 via git worktree):** test_settings_parity.py::TestSpineChain::test_itr_color_scheme_path_points_to_csg_palette, test_settings_parity.py::TestPhase2InvocationContract::test_csg_honors_spine_templates_over_bundled (spine-marker missing from real csg output), test_yaml_manifest_reader.py::test_packages_manifest_has_verified_set (manifest set drifted), test_bootstrap_playbook.py::test_parses_as_list_of_import_playbook_entries + test_imports_in_exact_dependency_order. All outside this story's changed areas (settings/csg, packages manifest, aggregate playbook); fixing them is separate-scope work. Also fixed within a story-touched test file: the pre-existing skeleton-count failure (21 → 22: gloview.lua was added to compositor_configs_skeleton_files by the GloView commit without updating the test — skeletons are repo-authoritative, test aligned).
- **Container integration:** new `test_criterion_6_accepts_runtime_current_palette_in_container` stages the post-runtime state via `_Target.exec_sh` (new helper) + `verify_raw` (refactor of verify), asserting the current-leg pass and the neither-location failure. Skipped honestly on this host-class (no nested engine in the disposable target); the packages --check proof ran green.

### Change Log

- 2026-08-31: Story 1.12 implemented — compositor_configs don't-clobber skip-guard (AC 1/2), config_copies fail-loud palette-symlink tripwire (AC 3), verify criterion 6 relaxed to generated-OR-current (AC 4); structural + integration suites extended; 5 pre-existing baseline failures documented as out-of-scope.

### File List

- src/provisioning/ansible/roles/compositor_configs/tasks/main.yml
- src/provisioning/ansible/roles/compositor_configs/vars/main.yml
- src/provisioning/ansible/roles/config_copies/tasks/main.yml
- src/provisioning/ansible/roles/config_copies/vars/main.yml
- src/provisioning/ansible/roles/verify/tasks/main.yml
- src/provisioning/ansible/roles/verify/vars/main.yml
- src/provisioning/tests/unit/test_compositor_configs_role.py
- src/provisioning/tests/unit/test_config_copies_role.py
- src/provisioning/tests/unit/test_verify_role.py
- src/provisioning/tests/integration/test_apply_verify_container.py

