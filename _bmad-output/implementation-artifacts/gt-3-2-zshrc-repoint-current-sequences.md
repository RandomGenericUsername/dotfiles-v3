---
baseline_commit: 104e11f
---

# Story 3.2: zshrc repoint to current/colors.sequences

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want every new shell themed from the runtime's current palette,
So that my terminal stops reading the orphaned pre-Epic-4 `generated/` tree.

## Acceptance Criteria

### Verbatim contract (epics-gtk-theming.md, Story 3.2)

**Given** `dotfiles/config/zsh/.zshrc.j2:30` cats `{{COLOR_SCHEME_OUTPUT_DIR}}/colors.sequences`
**When** the template is repointed to the state root (`$XDG_STATE_HOME/dotfiles/current/colors.sequences`)
**Then** rendered `.zshrc` cats the current pointer (absent until first seed → harmless backgrounded cat)
**And** the `COLOR_SCHEME_OUTPUT_DIR` template var is retired or repurposed with no dangling references
**And** provisioning verify/CLI-parity tests updated; a live-shell test sources the new `.zshrc` and reads the correct palette

### Operational sub-ACs (dev contract — derived from the verbatim block + investigation §1 P3, §4 contract change 4, and the sibling-role path-resolution precedent)

1. **Given** `dotfiles/config/zsh/.zshrc.j2:30` renders the cat line, **When** the template is repointed, **Then** line 30 becomes `(cat "{{COLOR_SCHEME_CURRENT_DIR}}/colors.sequences" &)` where `COLOR_SCHEME_CURRENT_DIR` is passed by the render task as `{{ zsh_config_state_current_dir }}` — the rendered `.zshrc` contains a STATIC ABSOLUTE path `<XDG_STATE_HOME>/dotfiles/current/colors.sequences` resolved at provisioning time (NOT a literal `$XDG_STATE_HOME` in the rendered file — every other template var in this role resolves to a real provisioned path: `STARSHIP_CONFIG`, `OH_MY_ZSH_DIR`, …; mirror of the settings role's `itr-settings.toml.j2` pattern `{{ settings_xdg_state_home | trim }}/dotfiles/current/colors.yaml`) (AC: verbatim "repointed to the state root" + "rendered `.zshrc` cats the current pointer").

2. **Given** the sibling roles all resolve the runtime's state root identically, **When** `zsh_config` needs the current dir, **Then** `roles/zsh_config/vars/main.yml` gains `zsh_config_xdg_state_home` with the EXACT shared derivation `"{{ ansible_facts.env.XDG_STATE_HOME | default(ansible_facts.env.HOME | default(ansible_facts.user_dir) + '/.local/state', true) }}"` (mirror of `verify_xdg_state_home`, `filesystem_xdg_state_home`, `compositor_configs_xdg_state_home`, `settings_xdg_state_home`, `gui_tools_xdg_state_home` — F4 lock: `ansible_facts.env.*`, never the deprecated `ansible_env`) and a derived `zsh_config_state_current_dir: "{{ zsh_config_xdg_state_home | trim }}/dotfiles/current"` (trim lock, mirror of `verify_state_current_dir` and `compositor_configs_state_current_dir`; AD-5: the state root is ALWAYS `<XDG_STATE_HOME>/dotfiles/`) — one XDG read per role, no cross-role var consumption (AC: verbatim "$XDG_STATE_HOME/dotfiles/current/colors.sequences").

3. **Given** `COLOR_SCHEME_OUTPUT_DIR` is defined ONLY in `roles/zsh_config/tasks/main.yml:51` and consumed ONLY by `.zshrc.j2:30` (grep-verified at 104e11f: no other role, var file, test, or verify task references it), **When** the repoint lands, **Then** the var is RETIRED entirely — deleted from the render task's vars block along with the stale header comment ("Needs the palette (settings/default_palette) for COLOR_SCHEME_OUTPUT_DIR" — the role has no palette dependency anymore; bootstrap.yaml has imported no `default_palette` playbook since Epic 4) — "retired", not "repurposed": the old name asserts a provisioning OUTPUT dir, which is the exact inverted semantics this story kills (AC: verbatim "the `COLOR_SCHEME_OUTPUT_DIR` template var is retired or repurposed with no dangling references" — pinned: retired).

4. **Given** the current pointer is absent until the first runtime seed/reconcile (gt-2-1/gt-2-2 landed; `current/colors.sequences` is the csg `sequences` format — ST-terminated OSC lines with trailing LFs, safe to cat into the terminal), **When** a shell starts pre-seed, **Then** the backgrounded cat of a missing file is harmless — the pinned contract is the BARE backgrounded cat with NO existence guard: investigation §4 contract change 4 pins `.zshrc` contract: `cat "$XDG_STATE_HOME/dotfiles/current/colors.sequences" &` (absent until seed → harmless backgrounded cat) and the epics AC repeats it. A `[ -e ] &&` guard was considered and REJECTED: it deviates from the pinned contract byte-shape for a purely cosmetic gain (one transient stderr line from the subshell pre-seed) — pinned: no guard (AC: verbatim "absent until first seed → harmless backgrounded cat").

5. **Given** verify's done-criterion 12 gates the rendered `.zshrc` (`roles/verify/tasks/main.yml` "Check rendered zshrc wires starship and the color scheme", grep `-E "starship init|colors.sequences"` over `{{ verify_xdg_config_home }}/zsh/.zshrc`), **When** the repoint lands, **Then** the grep's sequences alternative is TIGHTENED to `current/colors\.sequences` so verify fails loud if the cat ever regresses to the orphaned `generated/palettes/` tree (the name-only pattern would stay green through a regression — it greps a substring); the header comment listing criterion 12 (line ~35) and the assert fail_msg gain the state-root wording. The gate's pre-existing OR-semantics laxness (grep passes if EITHER alternative matches any line) is pre-existing behavior — NOT fixed here (out of scope; the fixture always contains both lines) (AC: verbatim "provisioning verify/CLI-parity tests updated").

6. **Given** the two role test suites, **When** the repoint lands, **Then** (i) `test_zsh_config_role.py`'s execution test (`test_playbook_renders_zshrc_with_all_vars`) drops the `<install>/generated/palettes/` fixture, sets `XDG_STATE_HOME` explicitly in the ansible env (the derivation reads `ansible_facts.env` — an ambient host value would silently win), pre-creates `<state>/dotfiles/current/colors.sequences`, and asserts the rendered `.zshrc` cats exactly `<state>/dotfiles/current/colors.sequences` with NO `generated/palettes` anywhere; (ii) NEW structural tests mirror the sibling-role precedents: `zsh_config_state_current_dir` derives from `zsh_config_xdg_state_home | trim` (mirror `test_verify_role.py::test_state_current_dir_derived_from_verify_xdg_state_home`), `zsh_config_xdg_state_home` carries the shared `ansible_facts.env.XDG_STATE_HOME` derivation (mirror `test_compositor_configs_role.py::test_xdg_state_home_mirrors_verify_derivation`), an Epic-4 tripwire — no `generated/palettes` in tasks, vars, or template (mirror `test_compositor_configs_role.py`'s tripwire), and `TestZshConfigVars._REQUIRED_KEYS` grows the two new vars; (iii) `test_render_task_defines_all_template_vars` auto-enforces the rename (its `\{\{([A-Z_]+)\}\}` scan fails loud on any undefined template var) — zero edits expected there; (iv) `test_verify_role.py::_build_provisioned_layout`'s `.zshrc` fixture (the `(cat "<INSTALL>/generated/palettes/colors.sequences" &)` line) is rewritten to the state-root cat (`<STATE>/dotfiles/current/colors.sequences`) so the tightened criterion-12 grep passes (AC: verbatim "provisioning verify/CLI-parity tests updated").

7. **Given** the documentation set, **When** grep-driven, **Then** NO doc edits are in scope: grep for `colors.sequences` across `docs/` returns ZERO hits (verified at 104e11f); the `generated/palettes` references in `docs/01-…phase1-plan.md` and the phase-1 specs describe the deleted CSG output chain generally (Epic-4-stale prose) and no doc claims `.zshrc` reads `generated/palettes/colors.sequences` — the full contract/doc reconciliation (shared-data-contract.md change 4, consumer-wiring.md chains, docs/99, ARCHITECTURE-SPINE) is gt-4-2. The orphaned `~/.local/share/dotfiles/generated/` tree itself is also untouched (investigation §6: "orphan stays ignored by every gate") (boundary pin).

8. **Given** the machine (provisioning apply run + at least one runtime seed), **When** the live-shell acceptance test runs, **Then** the recorded procedure in the Dev Agent Record passes: (a) `grep -n "colors.sequences" ~/.config/zsh/.zshrc` shows exactly one cat line under `<state>/dotfiles/current/`; (b) the pointed-at artifact is the csg sequences format (OSC lines, ST-terminated); (c) a NEW terminal (or `zsh -i -c 'true'` + relaunch) applies the current wallpaper palette to the terminal — byte-consistent with what gt-2-3's `TerminalColorApplier` writes to `/dev/tty` (both read the same artifact: the "single source of truth shared with new shells" deferred note in gt-2-3 closes here); (d) pre-seed behavior: with the pointer absent the backgrounded cat errors harmlessly at shell start (pinned contract) (AC: verbatim "a live-shell test sources the new `.zshrc` and reads the correct palette").

## Tasks / Subtasks

- [x] Task 1 — template repoint (AC: 1, 3, 4)
  - [x] `dotfiles/config/zsh/.zshrc.j2:30`: `(cat "{{COLOR_SCHEME_OUTPUT_DIR}}/colors.sequences" &)` → `(cat "{{COLOR_SCHEME_CURRENT_DIR}}/colors.sequences" &)`; extend the two-line comment above it with the state-root provenance (runtime-owned `current/` pointer, gt-2-2 seeder/reconcile flip it; provisioning renders the absolute path at apply time).
  - [x] NO guard added — bare backgrounded cat per pinned contract (sub-AC 4).
- [x] Task 2 — zsh_config vars (AC: 2)
  - [x] `src/provisioning/ansible/roles/zsh_config/vars/main.yml`: add `zsh_config_xdg_state_home` (exact shared derivation string) with a comment mirroring the sibling roles' ("the state home the runtime owns… identical derivation to verify_xdg_state_home / filesystem_xdg_state_home; F4 lock: ansible_facts.env, NOT ansible_env") and `zsh_config_state_current_dir: "{{ zsh_config_xdg_state_home | trim }}/dotfiles/current"` with the AD-5 + trim-lock comment (mirror `verify_state_current_dir`).
- [x] Task 3 — zsh_config tasks (AC: 1, 3)
  - [x] `src/provisioning/ansible/roles/zsh_config/tasks/main.yml` render-task vars: `COLOR_SCHEME_OUTPUT_DIR: "{{ install_dir | trim }}/generated/palettes"` → `COLOR_SCHEME_CURRENT_DIR: "{{ zsh_config_state_current_dir }}"`.
  - [x] Same file: header comment line ("Needs the palette (settings/default_palette) for COLOR_SCHEME_OUTPUT_DIR") replaced — the role's template vars now resolve spine paths, distro plugin paths, and the runtime state-root current dir; no palette dependency.
- [x] Task 4 — verify criterion 12 (AC: 5)
  - [x] `src/provisioning/ansible/roles/verify/tasks/main.yml`: grep argv pattern `"starship init|colors.sequences"` → `"starship init|current/colors\.sequences"`; update the criterion-12 line in the header checklist comment (~line 35) and the assert fail_msg (~line 682) to the state-root wording (expected `starship init` and a cat of `<state>/dotfiles/current/colors.sequences`); keep command gating (`changed_when: false`, `failed_when: false`, `when: not ansible_check_mode`) and OR-semantics untouched.
- [x] Task 5 — tests (AC: 6)
  - [x] `src/provisioning/tests/unit/test_zsh_config_role.py`: execution test — remove the `(install / "generated" / "palettes")` fixture writes, `env["XDG_STATE_HOME"] = str(root / "state")` (explicit — never ambient), pre-create `<state>/dotfiles/current/colors.sequences`, assert rendered text contains `<state>/dotfiles/current/colors.sequences` and NOT `generated/palettes`; NEW structural tests per sub-AC 6(ii) (state-home derivation mirror, current-dir trim lock, generated/palettes tripwire over tasks+vars+template, `_REQUIRED_KEYS` += the two vars).
  - [x] `src/provisioning/tests/unit/test_verify_role.py`: `_build_provisioned_layout` `.zshrc` fixture line → `(cat "<STATE>/dotfiles/current/colors.sequences" &)` (the fixture's `<INSTALL>`/`<STATE>` placeholders must track whatever install/state dirs the fixture builds — mirror how the fixture derives other paths); confirm the criterion-12 gate tests (if any assert the grep argv) stay green or gain the tightened pattern.
  - [x] VERIFY ONLY (expected green, touch only if an assertion exists): `test_render_task_defines_all_template_vars` (regex-driven, auto-tracks the rename), `tests/integration/test_ansible_dryrun.py` (template is check-safe; pattern-only grep change), `tests/integration/test_apply_verify_container.py` (container sets `XDG_STATE_HOME=/scratch/state`; rendered cat contains `current/colors.sequences` → tightened grep matches; its `generated/palettes/colors.conf` manipulations exercise criterion 6, unrelated), `test_bootstrap_playbook.py` (import order unchanged).
- [x] Task 6 — gates + sanity greps (AC: 3, 5)
  - [x] Record provisioning gate baselines BEFORE coding (gt-3-1/gt-2-1 stash procedure): `uv run --directory src/provisioning pytest -q`, `ruff check .`, `ruff format --check .`, `mypy src` (bare `mypy` errors — pre-existing invocation quirk, use `mypy src`); post-implementation EXACTLY at baseline, zero new violations.
  - [x] Sanity greps: `grep -rn "COLOR_SCHEME_OUTPUT_DIR" src/ dotfiles/` → ZERO hits (retired, no dangling references); `grep -rn "generated/palettes" src/provisioning/ansible/roles/zsh_config/ src/provisioning/tests/unit/test_zsh_config_role.py dotfiles/config/zsh/` → ZERO hits; `grep -rn "zsh_config_xdg_state_home\|zsh_config_state_current_dir" src/provisioning/ansible/` → only zsh_config vars/tasks.
- [x] Task 7 — live-shell acceptance test (AC: 8)
  - [x] Execute the sub-AC 8 procedure on this machine (apply + seed already landed) and record the results verbatim in the Dev Agent Record; a pre-seed spot-check is optional (temporarily point XDG_STATE_HOME at an empty dir in a throwaway shell to observe the harmless backgrounded cat — do NOT delete the real `current/` artifact).

## Dev Notes

### Scope boundary — this story is a one-line repoint plus its verification web

Story gt-3-2 flips the shell's palette source from the orphaned provisioning-era `generated/palettes/` tree to the runtime-owned `current/` pointer. It does **NOT** implement:

- **Runtime changes** — zero. `current/colors.sequences` exists after seed/reconcile (gt-2-1 artifact set + gt-2-2 pointers; `TerminalColorApplier` already reads the same artifact per gt-2-3). Nothing in `src/runtime` or csg is touched.
- **The `generated/` orphan cleanup** — `~/.local/share/dotfiles/generated/` stays on disk, ignored (investigation §6 mitigation row); no deletion task, no verify criterion about it.
- **Contract/doc reconciliation** — `shared-data-contract.md` (§4 contract change 4: the `.zshrc` contract line), `consumer-wiring.md` (terminal chain), docs/99, ARCHITECTURE-SPINE are gt-4-2. This story changes only provisioning code + tests (AC 7 boundary).
- **AGS/GTK consumers** — gt-3-1 (done) owns the GTK spine dirs; gt-4-1 owns AGS/icme polish.

### Design decision 1 — static absolute path in the rendered `.zshrc`, not a `$XDG_STATE_HOME` literal

The epics AC phrase "$XDG_STATE_HOME/dotfiles/current/colors.sequences" describes WHERE the pointer lives, not what the rendered file must literally contain. The repo's provisioning convention resolves every template var to a real absolute path at apply time (`STARSHIP_CONFIG`, `OH_MY_ZSH_DIR`, the settings role's `path = "{{ settings_xdg_state_home | trim }}/dotfiles/current/colors.yaml"` in itr-settings.toml.j2). A literal `$XDG_STATE_HOME` in `.zshrc` would re-resolve at SHELL start from the shell's environment — a second, divergent source of truth (an interactive shell with a different XDG_STATE_HOME than the provisioning run would cat a different tree). Static resolution keeps provisioning as the single authority for the path, and the runtime remains the single authority for the artifact CONTENT (symlink flip). The `zsh_config_xdg_state_home` var uses the exact shared derivation string so all six roles agree byte-for-byte on the state root.

### Design decision 2 — retire `COLOR_SCHEME_OUTPUT_DIR`, don't repoint it

The epics allow "retired or repurposed — pick one and pin". Pinned: RETIRED. The name's semantics ("output dir" — where provisioning emits artifacts) are precisely what Epic 4 inverted (runtime owns derived artifacts; provisioning consumes). Repointing the var to `…/dotfiles/current` would leave a lying name in the render task and a "scheme output" concept in the role's vocabulary. The new name `COLOR_SCHEME_CURRENT_DIR` states what it is: the dir holding the current palette. Consumers enumerated by grep at 104e11f: definition `roles/zsh_config/tasks/main.yml:51`, header comment `:16`, consumption `.zshrc.j2:30` — plus historical prose in epics/investigation/old story docs (never touched). No settings role, group_vars, verify var, or other test references it, so retirement is a two-file edit + comment.

### Design decision 3 — no existence guard on the cat (pinned contract byte-shape)

Investigation §4 contract change 4 pins the exact rendered line shape: `cat "$XDG_STATE_HOME/dotfiles/current/colors.sequences" &` with the parenthetical "absent until seed → harmless backgrounded cat". A `[ -e ] &&` guard would be cleaner stderr hygiene pre-seed but deviates from the pinned contract for zero functional gain (the failure mode — one transient subshell stderr line at first shell after provisioning, before the first `wallpaper set` — is accepted by both planning docs). If a future story wants the guard, it is a one-line contract amendment, not this story's call.

### Design decision 4 — verify's grep must pin the PATH, not the filename

Criterion 12's current pattern `starship init|colors.sequences` survives the repoint untouched (substring match), which means verify would NOT catch a regression to `generated/palettes/colors.sequences` — the exact defect class this epic kills. Tightening the alternative to `current/colors\.sequences` makes the state-root path a verified invariant while keeping the gate's shape (command + rc assert, check-gated). The gate's OR-semantics (either alternative matching any line passes) is pre-existing laxness — the fixture always satisfies both — and is deliberately not restructured here (two-grep restructuring churns the fixture and gate tests for no story-relevant gain; noted for a future hardening pass).

### Verify-role impact analysis (grep-driven, at 104e11f)

- `roles/verify/tasks/main.yml:665-685` — the criterion-12 gate (grep + assert). Only the argv pattern + comment/fail_msg wording change.
- `roles/verify/vars/main.yml` — NO changes: `verify_state_current_dir` already derives `<state>/dotfiles/current` for criterion 6; criterion 12 reads the .zshrc through `verify_xdg_config_home`, unchanged. No new verify list vars → no vacuous-pass guard edits, no `_REQUIRED_KEYS` edits on the verify side.
- `test_verify_role.py:1687-1690` — the `.zshrc` fixture is the ONE hardcoded content assertion feeding criterion 12; it must be rewritten (sub-AC 6.iv) or the tightened grep fails the whole verify execution test.
- Criterion 6's `generated/palettes/ OR current/` acceptance (verify vars comment ~line 52, container test ~373-414) concerns `colors.conf`, not sequences — untouched.

### Runtime state facts (what the dev can rely on)

- `~/.local/state/dotfiles/current/colors.sequences` EXISTS after seed/reconcile (gt-2-1/gt-2-2 landed, verified on-machine 2026-09-07); format = csg `sequences` (ST-terminated OSC lines, trailing LFs — safe to cat raw into the terminal, same payload gt-2-3's applier writes to `/dev/tty`).
- `~/.local/share/dotfiles/generated/` still exists (orphaned; `.zshrc` currently cats `generated/palettes/colors.sequences` from it — investigation §1 P3 evidence).
- The rendered `.zshrc` lives at spine `<install>/config/zsh/.zshrc`, linked from `~/.config/zsh/.zshrc` (ZDOTDIR wiring); a new shell reads it at startup only — palette changes require a NEW shell (documented relaunch-pickup class, NFR-5).

### Previous story intelligence (gt-3-1, done) + git intelligence

- gt-3-1's discipline to replicate: record gate baselines BEFORE coding (`pytest -q` / `ruff check` / `ruff format --check` / `mypy src`), post-implementation exactly at baseline; known pre-existing failures (4: test_settings_parity container/CSG integration x2, test_ansible_scaffold, test_packages_role), pre-existing ruff state (3 E501 in tests, 10 unformatted files), `--syntax-check` quirk on `packages.yaml` (needs inventory — pre-existing, unrelated).
- gt-3-1's deviation-5 lesson (check-mode can conflict with real machine state) does NOT apply here: the template module is natively check-safe and the only verify change is a grep pattern (already check-gated).
- gt-2-3 deferred the "single source of truth shared with new shells" claim to THIS story (its doc note: `.zshrc.j2:30` repoint is gt-3-2) — after this story the applier and new shells read the identical artifact.
- Recent commits (worktree `feat/gtk-theming-consumer`): `104e11f` fix: auto-commit code review findings; `9e70ab8` style: gt-3-1 ruff-format collapse; `ddcbf2b` chore(bmad): sprint-status story_location corrected to worktree path; `5ecb7e0` feat(provisioning): gt-3-1 migrate-then-symlink. Convention: `feat(provisioning): …` with `baseline_commit` frontmatter (this story: `104e11f`); story files in the WORKTREE `_bmad-output/implementation-artifacts/` (story_location now correct).
- Sprint-status precedent: gt-epic-3 is already `in-progress` (flipped at gt-3-1 creation) — no epic transition this run.

### Architecture compliance (what the implementation must respect)

| Invariant | Application here |
|---|---|
| §11 boundary (AD-5/AD-15) | Provisioning now REFERENCES the state root in a rendered consumer config but still never WRITES under `state_root` — the rendered cat is a read; the `current/` pointers are runtime writes (gt-2-2) |
| Single source of truth (Epic 4 / FR-5) | `.zshrc` reads ONLY the runtime `current/` pointer; the orphaned `generated/` tree loses its last consumer reference in provisioning-rendered configs |
| F4 lock (`ansible_facts.env.*`) | `zsh_config_xdg_state_home` uses the non-deprecated env-fact derivation — hard-breaks on ansible-core >= 2.24 if violated |
| Trim lock | `zsh_config_state_current_dir` embeds `| trim` exactly once at the state-home derivation; downstream consumption is the derived var |
| NFR-3 distro isolation / NFR-1 ansible-as-authority | No become; template module check-safe; no new task types — the render task only swaps one var value |
| NFR-4 (no cache/hash changes) | Nothing touches runtime cache keys or layouts |

### Testing standards summary

- Runner: `uv run --directory src/provisioning pytest -q` (integration tests skip cleanly when `ansible-playbook`/`podman`/`sudo` are absent — record the skip baseline; expected 3 skips).
- Structural-test conventions to mirror: YAML task parsing with `_TASK_KEYWORDS`/`_module_key` (test_zsh_config_role.py already has the harness — extend, don't reinvent); derivation-mirror asserts compare EXACT template strings; tripwire tests assert substring absence with a why-fail message; count asserts derive from the data, never literals.
- Execution tests run the REAL `zsh-config.yaml` playbook against a temp spine with `ANSIBLE_CONFIG` pointed at the scaffold `ansible.cfg`; XDG_STATE_HOME must be set EXPLICITLY in the env dict (ambient host values leak through `os.environ` copies — the new current-dir derivation makes this test env-sensitive for the first time).
- The render task is check-safe — `test_ansible_dryrun.py`'s `--check` sweep must stay green with zero changes.

### Project Structure Notes

- Blast radius (grep-driven at 104e11f): `COLOR_SCHEME_OUTPUT_DIR` → exactly `.zshrc.j2:30` + `roles/zsh_config/tasks/main.yml:{16,51}` (+ historical planning docs, untouched); `colors.sequences` in provisioning → the same two files + verify criterion-12 gate + `test_verify_role.py:1689` fixture + `test_zsh_config_role.py:{214,256}`; `generated/palettes` in zsh_config/tests → the fixtures named in Task 5 only.
- The `.zshrc.j2` is a REPO-CONFIG template (`zsh_config_template_root` = repo root), not role-internal — edits land in `dotfiles/config/zsh/`, consumed via the `template` module.
- No new playbook, role, var file, or bootstrap-order change; the story is 4 source-file edits + 2 test-file edits, no doc edits.
- `roles/zsh_config/` has only `tasks/` + `vars/` (no meta/defaults) — all new vars go in `vars/main.yml` alongside the existing ones.

### References

- Epics: `_bmad-output/planning-artifacts/epics-gtk-theming.md` — Story 3.2 (verbatim AC block), FR-5, Epic 3 overview, NFR-5 (relaunch pickup)
- Investigation: `_bmad-output/planning-artifacts/gtk-theming-investigation.md` — §1 P3 (the orphaned `generated/` problem: `.zshrc` cats a tree Epic 4 deleted), §2 provisioning row ("zsh_config repoints the cat → `current/colors.sequences`"), §4 contract change 4 (the pinned `.zshrc` contract line), §6 (orphan-stays-ignored mitigation)
- Predecessors: `_bmad-output/implementation-artifacts/gt-2-1-palette-artifact-set-growth.md` + `gt-2-2-iconsumerpathspec-declarative-pointers.md` (the `current/colors.sequences` artifact + pointer machinery), `gt-2-3-terminalcolorapplier-reads-artifact.md` (the deferred shared-source-of-truth note closing here), `gt-3-1-gtk-config-dirs-spine-config-links.md` (gate-baseline discipline, sibling structural-test conventions)
- Path-resolution precedents: `src/provisioning/ansible/roles/settings/templates/itr-settings.toml.j2` (`{{ settings_xdg_state_home | trim }}/dotfiles/current/colors.yaml`), `roles/verify/vars/main.yml` (`verify_xdg_state_home` + `verify_state_current_dir`), `roles/compositor_configs/vars/main.yml` (`compositor_configs_state_current_dir`), `roles/{filesystem,gui_tools}/vars/main.yml` (identical state-home derivation strings)
- Provisioning code: `dotfiles/config/zsh/.zshrc.j2`, `src/provisioning/ansible/roles/zsh_config/{tasks/main.yml,vars/main.yml}`, `roles/verify/tasks/main.yml` (criterion-12 gate ~665-685, header checklist ~35), `playbooks/{zsh-config,bootstrap}.yaml` (order: zsh-config before config_links, unchanged)
- Tests: `src/provisioning/tests/unit/test_zsh_config_role.py` (harness + execution test), `test_verify_role.py` (`_build_provisioned_layout` fixture ~1687), `test_compositor_configs_role.py` (derivation-mirror + tripwire precedents ~265, ~351), `tests/integration/{test_ansible_dryrun.py,test_apply_verify_container.py}` (verify-only)

## Dev Agent Record

### Agent Model Used

opencode-go/glm-5.3-flash (Claude Code agent harness), fresh context, 2026-09-07

### Debug Log References

- Baselines recorded BEFORE coding (git stash discipline not needed — clean tree at `0a7081e`, story scaffolding committed first):
  - `pytest -q` full: **4 failed / 564 passed / 3 skipped** (pre-existing: test_settings_parity x2 integration, test_ansible_scaffold, test_packages_role — exactly the gt-3-1-known 4)
  - `ruff check .`: 3 errors (E501 — test_compositor_configs_role.py:191,597; test_config_copies_role.py:492)
  - `ruff format --check .`: 10 files would be reformatted
  - `mypy src`: Success, 17 files
- RED phase confirmed: 5 targeted test failures against the unmodified source (ansible-playbook present, execution test ran the real playbook).
- GREEN-phase fix 1: YAML scanner error — `"starship init|current/colors\.sequences"` in a double-quoted YAML scalar is an invalid escape (`\.`); switched to single quotes (backslash literal, regex intact).
- GREEN-phase fix 2: the new criterion-12 fail_msg mentioned `generated/palettes/` and tripped the pre-existing tripwire `test_criterion_6_checks_current_only` ("generated/palettes must not appear in parsed task data"); fail_msg reworded to "the orphaned provisioning-era tree" (header-comment mentions are safe — comments don't parse into task data).
- ruff-format found one non-canonical assert in my new tripwire test; `ruff format tests/unit/test_zsh_config_role.py` applied → format baseline restored (10 files), ruff check clean, tests green.
- Full post-gates: full suite **exactly at baseline** (4 pre-existing failures), ruff/mypy at baseline, `--syntax-check` green for zsh-config.yaml + verify.yaml; bootstrap.yaml dies at packages.yaml `hosts: "{{ os_family }}"` (pre-existing inventory-var quirk; passes fully with `-e os_family=arch`).

### Completion Notes List

- **Template repoint** (`.zshrc.j2`): line 30 now `(cat "{{COLOR_SCHEME_CURRENT_DIR}}/colors.sequences" &)` — a STATIC ABSOLUTE state-root path rendered at apply time (no `$XDG_STATE_HOME` literal); comment block extended with the state-root provenance; NO existence guard added (pinned byte-shape).
- **Var retirement**: `COLOR_SCHEME_OUTPUT_DIR` deleted from the render-task vars + header comment (retired, not repurposed); `zsh_config` vars gained `zsh_config_xdg_state_home` (exact shared derivation string, F4 lock) + `zsh_config_state_current_dir` (`| trim`, AD-5, one XDG read per role). Sanity greps: zero functional `COLOR_SCHEME_OUTPUT_DIR` / `generated/palettes` references — the only hits are the NEW tripwire test's own negative assertions (mirrors test_compositor_configs_role.py's tripwire precedent) and gitignored pycache.
- **Verify criterion 12 tightened**: grep argv → `'starship init|current/colors\.sequences'` (pin the PATH, not the filename); header checklist + fail_msg carry the state-root wording; command gating (changed_when/failed_when/check-gate) and OR-semantics untouched.
- **Tests**: execution test now sets `XDG_STATE_HOME` explicitly in the ansible env (ambient values would silently win via `ansible_facts.env`), pre-creates `<state>/dotfiles/current/colors.sequences`, asserts the exact cat line and NO `generated/palettes`; 3 new structural tests (derivation mirror, trim lock, Epic-4 tripwire over tasks+vars+template); `_REQUIRED_KEYS` grew the two vars; `test_render_task_defines_all_template_vars` auto-tracked the rename (zero edits, as predicted); verify fixture `.zshrc` rewritten to `(cat "<STATE>/dotfiles/current/colors.sequences" &)` (placeholder convention preserved — criterion 12 grep only pattern-matches).
- **Live-shell acceptance test (sub-AC 8) — EXECUTED on this machine**, which required converging stale machine state first (the story's "apply + seed already landed" premise was factually stale at `~/.config/zsh/.zshrc` ago-24 render + pre-gt-2-1 cache entries; recorded verbatim):
  - Machine convergence (provisioning apply of 3 idempotent role playbooks from this worktree): zsh-config.yaml (rendered new .zshrc, ok=6 changed=1 failed=0), assets.yaml (ok=12 changed=1 — deployed `colors.adw.css.j2` into the spine's csg-templates, closing the derive-vs-adapter template-set divergence that previously made `wallpaper set` fail loud on `output_dir hash mismatch`), config-links.yaml (ok=101 changed=10 failed=0 — ~/.config/zsh is now the spine symlink).
  - Toolchain: machine's uv-installed `csg` lacked `adw.css` (pre-gt-1-1) → reinstalled from this worktree (`uv tool install --force src/cli-tools/color-scheme-generator`); the container images (`csg-pywal-podman:latest` etc.) contained the old backend → rebuilt via `csg install --container-engine podman --source-root <worktree>` (all 4 images: built).
  - Seed: `uv run --directory src/runtime dotfiles-runtime wallpaper set ~/.local/share/dotfiles/wallpapers/default.png` — derive/cache/swap SUCCEEDED (new palette entry e5e310aa… incl. colors.sequences; current/ pointers flipped); reload surfaced 2 expected failures from the non-interactive CLI context (HyprpaperReloader: "Invalid monitor" — no Hyprland session in the tool shell; TerminalColorApplier: "/dev/tty: No such device or address" — no controlling tty in the sandboxed shell). The artifact + pointer mechanics were unaffected (swap precedes reload).
  - (a) `grep -n "colors.sequences" ~/.config/zsh/.zshrc` → exactly ONE line: `33:(cat "/home/inumaki/.local/state/dotfiles/current/colors.sequences" &)`.
  - (b) artifact shape: ST-terminated OSC lines with trailing LFs (od: `033 ] 4 ; 0 ; # 0b0b1a 033 \ \n` … ends `033 ] 1 2 ; # c2c2c5 033 \`), 306 bytes — csg `sequences` format, safe to cat raw.
  - (c) byte-consistency: ran a REAL zsh (`script -qec 'zsh -i -c "sleep 2"'`) so it sources the new .zshrc under a pty; captured the backgrounded cat's TTY stream and verified all 19 OSC units of `current/colors.sequences` appear VERBATIM in the captured stream (python byte-level check) — the shell themes from exactly the bytes TerminalColorApplier writes (it writes the artifact unmodified to /dev/tty; both read the same file — gt-2-3's deferred "single source of truth shared with new shells" closed).
  - (d) pre-seed: threw-away state root (`/tmp/opencode/empty-state/…`), template-rendered cat pointed at the absent pointer → backgrounded subshell printed `cat: …: No such file or directory` while the shell continued normally (`echo SHELL_OK` printed, rc=0) — harmless, per pinned contract.

### File List

- dotfiles/config/zsh/.zshrc.j2
- src/provisioning/ansible/roles/zsh_config/tasks/main.yml
- src/provisioning/ansible/roles/zsh_config/vars/main.yml
- src/provisioning/ansible/roles/verify/tasks/main.yml
- src/provisioning/tests/unit/test_zsh_config_role.py
- src/provisioning/tests/unit/test_verify_role.py

### Change Log

- 2026-09-07: gt-3-2 implemented — zshrc repointed to the runtime state-root `current/colors.sequences` (static absolute path), `COLOR_SCHEME_OUTPUT_DIR` retired, verify criterion-12 grep tightened to `current/colors\.sequences`, role/verify tests updated + 3 new structural tests; full provisioning suite exactly at the 4 pre-existing-failure baseline; live-shell AC-8 procedure executed on-machine (machine first converged from a stale pre-gt-2-1 state via idempotent provisioning applies + csg reinstall + container image rebuilds).
