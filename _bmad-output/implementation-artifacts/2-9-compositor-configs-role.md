---
baseline_commit: 5577a71
---

# Story 2.9: Compositor Configs Role

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Change Log

- 2026-08-12: Story created — ultimate context engine analysis completed; comprehensive developer guide created (FR-19).

## Story

As an operator,
I want a `compositor_configs` role that places skeletons and color fragments,
So that Hyprland/Waybar render with first-boot colors.

## Acceptance Criteria

1. `roles/compositor_configs/` role exists with `tasks/main.yml` (AC 1, FR-19)
2. Copies `dotfiles/config/{hypr,hyprpaper,waybar}/` skeletons to `~/.config/{hypr,hyprpaper,waybar}/` (AC 2)
3. Copies `<install>/generated/palettes/colors.conf` → `~/.config/hypr/colors.conf` (AC 3)
4. Copies `<install>/generated/palettes/colors.css` → `~/.config/waybar/colors.css` (AC 4) — NOTE: the actual source file is `colors.gtk.css` (see Dev Notes "The `colors.css` rename")
5. The skeleton files themselves never change on re-run (only the fragment files are overwrite candidates) (AC 5)
6. All tasks are idempotent (AC 6)
7. The "skeletons never change; fragments are the Phase 2 overwrite target" invariant is documented as load-bearing for Phase 2 (AC 7, FR-19)

## Tasks / Subtasks

- [ ] Create `src/provisioning/ansible/roles/compositor_configs/vars/main.yml` (AC: 1-7)
  - [ ] `compositor_configs_repo_root`: `{{ playbook_dir }}/../../../..` (mirror `assets_repo_root`/`cli_tools_repo_root` exactly — see Dev Notes "Where files live")
  - [ ] `compositor_configs_xdg_config_home`: same XDG-config-home derivation as the filesystem role's `filesystem_xdg_config_home` (honors `$XDG_CONFIG_HOME`, default `{{ ansible_facts.env.HOME }}/.config`; uses `ansible_facts.env`, NOT the deprecated top-level `ansible_env` fact) — see Dev Notes "The `~/.config` vs XDG home decision"
  - [ ] Skeleton copy list mapping the three `dotfiles/config/{hypr,hyprpaper,waybar}/` dirs → `{{ compositor_configs_xdg_config_home }}/{hypr,hyprpaper,waybar}` (AC 2)
  - [ ] Fragment copy list mapping palette files → user-config fragment targets (AC 3, 4):
      - `<install>/generated/palettes/colors.conf` → `{{ compositor_configs_xdg_config_home }}/hypr/colors.conf`
      - `<install>/generated/palettes/colors.gtk.css` → `{{ compositor_configs_xdg_config_home }}/waybar/colors.css` (RENAME — see Dev Notes "The `colors.css` rename")
  - [ ] All install-dir derived values consume the validated `{{ install_dir | trim }}` (trim lock)
- [ ] Create `src/provisioning/ansible/roles/compositor_configs/tasks/main.yml` (AC: 1-7)
  - [ ] FIRST task: the fail-loud install_dir seam assert, copied VERBATIM from the filesystem/assets/default_palette roles (AC: indirect, role contract)
  - [ ] Copy skeleton dirs: `ansible.builtin.copy` with `remote_src: true`, `src` ending with `/` (contents-into-dest), `dest` the per-compositor config dir, **`force: false`** (AC 2, 5 — see Dev Notes "Copy module semantics", the "Skeletons never change" bullet)
  - [ ] Copy fragments: `ansible.builtin.copy` `colors.conf` → hypr, `colors.gtk.css` → waybar/colors.css (AC 3, 4) — these are the ONLY overwrite candidates
  - [ ] Header comment documenting the "skeletons never change; fragments are the Phase 2 overwrite target" invariant as load-bearing (AC 7)
  - [ ] NO become/become_user anywhere (user-scoped role, mirror 2.5-2.8)
  - [ ] NO hardcoded absolute paths (everything via `{{ compositor_configs_repo_root }}` and `{{ install_dir | trim }}`)
- [ ] Create `src/provisioning/ansible/playbooks/compositor-configs.yaml` (AC: 1)
  - [ ] `hosts: localhost`, `gather_facts: true`, `roles: [compositor_configs]`, NO become, NO group_by (distro-agnostic, mirror default-palette.yaml)
- [ ] Add structural real-file tests `src/provisioning/tests/unit/test_compositor_configs_role.py` (AC: 1-7)
  - [ ] Role tree exists: `tasks/main.yml`, `vars/main.yml`
  - [ ] Tasks parse to a list of named tasks
  - [ ] First task is the fail-loud install_dir assert (verbatim form)
  - [ ] Skeleton copy tasks: three `ansible.builtin.copy` with `remote_src: true`, `src` ending `/`, sources prefixed `{{ compositor_configs_repo_root }}/dotfiles/config/<dir>/`, **`force: false`** (AC 2, 5)
  - [ ] Fragment copy tasks: exactly `colors.conf` → hypr/colors.conf and `colors.gtk.css` → waybar/colors.css (AC 3, 4 — lock the RENAME)
  - [ ] Idempotency contract: skeleton copies MUST set `force: false` and carry NO `creates:` (transfer-only-if-absent; a placed skeleton is never re-touched); fragment copies are the overwrite candidates (AC 5, 6)
  - [ ] Invariant documented: task file header mentions "skeletons never change; fragments are the Phase 2 overwrite target" (AC 7)
  - [ ] NO become/become_user anywhere
  - [ ] No hardcoded absolute paths in module bodies (trim lock)
  - [ ] vars test: required keys, XDG-config-home derivation honors `$XDG_CONFIG_HOME`, install-dir values trim-locked
  - [ ] playbook test: parses, `hosts: localhost`, `gather_facts: true`, `roles: [compositor_configs]`, no become, no group_by
- [ ] Verify full suite + lint + layering guard (AC: 6)
  - [ ] `uv run pytest` — full suite green, no regressions from the 334-pass baseline (Story 2.8)
  - [ ] `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean (mypy baseline: 10 pre-existing errors in test_default_palette_role.py + test_cli_tools_role.py — see Dev Agent Record in 2.8; new file must be clean)
  - [ ] `python tests/architecture/test_layering.py` exits 0 (standalone nicety)
  - [ ] `git status --short` shows ONLY the new role dir, playbook, and test file (plus any pre-existing dirty working-tree files from the 2.8 review findings — see Git Intelligence)

## Dev Notes

### Scope — what Story 2.9 is and is not

**IS:** the `compositor_configs` Ansible role (FR-19): copies the 2.8-authored static skeletons from `dotfiles/config/{hypr,hyprpaper,waybar}/` to `~/.config/{hypr,hyprpaper,waybar}/` and copies the 2.7-generated palette fragments into the user config (`colors.conf` → `~/.config/hypr/colors.conf`, `colors.gtk.css` → `~/.config/waybar/colors.css`). Plus its one-per-role playbook and a structural real-file test.

**IS NOT:** the `symlinks` role (2.10), the `settings` role (2.11), the `verify` role (2.12), the aggregate `bootstrap.yaml` (2.12), or any Python hexagon change. Do NOT touch `dotfiles/provisioning/*.yaml` (five manifests LOCKED in Story 2.1). Do NOT edit the skeleton files under `dotfiles/config/{hypr,hyprpaper,waybar}/` (authored in 2.8; this role only COPIES them). Do NOT modify the `default_palette` role (2.7) or its outputs. Do NOT add any `.py` under `ansible/`.

### The `colors.css` rename — the one naming trap in this story

The AC literally says "copies `<install>/generated/palettes/colors.css` → `~/.config/waybar/colors.css`". But the actual palette file produced by Story 2.7's `default_palette` role is **`colors.gtk.css`** — NOT `colors.css`. This is the 2026-08-12 review-finding correction: CSG's `css` format emits browser CSS custom properties that GTK/Waybar cannot read, so the role was switched to `gtk.css` (which emits `@define-color`), and the Waybar fragment file is now `colors.gtk.css`. The 2.8 Waybar skeleton `style.css` imports `colors.css` (the `@import "colors.css";` first line), and the verify gate (2.12, done-criterion 7) checks `~/.config/waybar/colors.css` — so the ROLE must COPY **`colors.gtk.css` → `~/.config/waybar/colors.css`** (rename-on-copy). Locking the source as `colors.gtk.css` and the dest basename as `colors.css` is load-bearing; a dev who naively reads the AC's `colors.css` source will reference a file that does not exist and the copy fails. [Sources: default_palette vars/main.yml#79-90, test_default_palette_role.py#446-457, chaining-spine.md#126, 2-8 story file]

### The `~/.config` vs XDG home decision

The ACs use `~/.config/...` shorthand. The filesystem role (2.5) already created the compositor config dirs via `filesystem_xdg_config_home` (honors `$XDG_CONFIG_HOME` with the spec default `{{ ansible_facts.env.HOME }}/.config`). This role must copy to the SAME resolved location (the actual `~/.config` when `$XDG_CONFIG_HOME` is unset, which is the default case). Therefore: **derive the target as `compositor_configs_xdg_config_home` using the identical `ansible_facts.env.XDG_CONFIG_HOME | default(ansible_facts.env.HOME + '/.config', true)` expression the filesystem role uses** — do NOT hardcode `~/.config`. Mirror the 2.5 derivation exactly (with `ansible_facts.env` — the deprecated top-level `ansible_env` fact hard-breaks on ansible-core >= 2.24, the repo-wide F4 lock). [Sources: filesystem vars/main.yml#23-31, 2-5 story file]

### The `<install>` sources must exist before the copy (fail-loud prerequisite)

The fragment copies read `<install>/generated/palettes/colors.conf` and `colors.gtk.css` — files generated by the `default_palette` role (2.7) at apply time. On the aggregate `bootstrap.yaml` chain (2.12) ordering guarantees they exist; on a DIRECT `compositor-configs.yaml` run they may not. Mirror the 2.6/2.7 direct-run-prerequisite discipline: a `stat` + `assert` pair on the two fragment sources, with a fail_msg like "run the default-palette playbook first". Under `--check`, the default_palette generate is skipped (its own `when: not ansible_check_mode` gate), so the sources are legitimately absent on a fresh target — the fragment copies AND their presence asserts must be gated `when: not ansible_check_mode` (dry-run must be dry, 2.7/2.8 discipline). The skeleton copies are NOT check-gated: the skeletons are static repo content (`remote_src: true` against `{{ compositor_configs_repo_root }}`), so `--check` reports the would-be copy without writing — safe. [Sources: default_palette tasks/main.yml#97-110, 165-183; assets tasks/main.yml#97-123]

### Copy module semantics (idempotency + check mode)

- `ansible.builtin.copy` with `remote_src: true` copies from the target (the repo checkout, since provisioning runs locally). Idempotent via checksums: a re-run with identical source content reports `ok`, satisfying NFR-1 and AC 6.
- **"Skeletons never change" (AC 5) REQUIRES `force: false` on the skeleton copies.** copy's `force` DEFAULT is `true` — meaning "replace the dest whenever content differs". With the default, a re-run would overwrite a user's hand-edited `~/.config/hypr/hyprland.conf` (or a manually-tweaked `style.css`) back to the repo skeleton the moment the two diverge. `force: false` flips copy to "only transfer if the destination does not exist", so a placed skeleton is NEVER touched by this role on any re-run — the literal, unconditional reading of AC 5 ("the skeleton files themselves never change on re-run; only the fragment files are overwrite candidates"). Do NOT set `force: true` (it is the default, and it breaks the invariant), and do NOT add `creates:` (not needed — `force: false` already guarantees no re-transfer when the file exists).
- "Fragments are the overwrite candidates" (AC 5, 7): the fragment copies are the ONLY tasks that may overwrite on palette change. copy's default `force: true` handles that: if the palette regenerates differently (FR-18 regenerate semantics, no `creates:` in 2.7), the fragment copy updates. Do NOT gate fragment copies with `creates:` either — that would freeze a stale fragment and break the Phase 2 overwrite contract.
- copy module check-mode support is FULL (the action plugin predicts `changed` without writing), which is why the skeleton copies need no gate; only the fragment copies (whose sources may not exist under --check) are gated.
- copy does NOT create `dest` parents for file sources — the filesystem role (2.5) created the `~/.config/{hypr,hyprpaper,waybar}` dirs, and this role relies on that on the bootstrap chain. On a DIRECT run, add `ansible.builtin.file state: directory` tasks (or rely on the copy `dest` dir being created when `src` is a dir — but the fragment copies target FILES inside those dirs, so the dirs must exist). Mirror the 2.6 "Ensure asset deploy targets exist" pattern: re-ensure the three config dirs first for direct-run self-containment. [Sources: assets tasks/main.yml#56-62, filesystem tasks/main.yml#41-45]

### Where files live

```
src/provisioning/ansible/
├── playbooks/
│   └── compositor-configs.yaml          ← NEW — one-per-role playbook (AC 1)
└── roles/
    └── compositor_configs/              ← NEW (AC 1)
        ├── tasks/main.yml               ← NEW (AC 1-7)
        └── vars/main.yml                ← NEW
src/provisioning/tests/unit/
    └── test_compositor_configs_role.py  ← NEW — structural real-file tests
```

- Everything lives INSIDE the ansible scaffold (unlike 2.8's repo-root skeletons). `compositor_configs_repo_root: "{{ playbook_dir }}/../../../.."` mirrors `assets_repo_root`/`cli_tools_repo_root` exactly — from `playbooks/` up to the repo root (playbooks → ansible → provisioning → src → repo).
- The skeleton sources are `{{ compositor_configs_repo_root }}/dotfiles/config/{hypr,hyprpaper,waybar}/` (trailing `/` on `src` = contents-into-dest, no nested dir — the 2.6 `assets_copies` pattern).
- Playbook filename is `compositor-configs.yaml` (hyphenated, matching the `default-palette.yaml` sibling); role dir is `compositor_configs` (underscored, matching role-dir convention). This asymmetry is intentional and mirrors the existing tree. [Source: plan §6 line 153/162]

### Check-mode / idempotency summary

| Task | Check-mode | Idempotency |
|---|---|---|
| install_dir assert | runs (harmless) | n/a |
| Ensure config dirs (`file`) | safe (native) | native |
| Copy skeletons (`copy`) | FULL support, no gate needed | `force: false` — transfer only if absent; never re-touches a placed skeleton |
| Fragment stat+assert | GATED `not ansible_check_mode` | n/a |
| Copy fragments (`copy`) | GATED `not ansible_check_mode` (sources may be absent) | checksum + force overwrite |

### Why no manifest parity

There is NO `dotfiles/provisioning/compositor-configs.yaml` manifest — the five manifests are exactly the ones locked in Story 2.1, and the plan defines no sixth. The compositor content contract lives in the repo skeleton files (2.8) + the palette fragment names (2.7), NOT in a manifest. The role's copy list is the structural mirror of that contract, locked by the structural test. Do NOT invent a manifest. [Sources: 2-8 story file "Why no fixture/manifest parity", plan §6]

### Mirror-and-adapt discipline (Epic 1 retro action item)

This role mirrors several siblings. "What differs from each mirror":
- **2.7 default_palette** (fragment consumer + install_dir seam + check-gating): 2.7 GENERATES the palette (command), 2.9 COPIES the fragments (copy). 2.9 needs NO `csg`/`weg` presence checks, NO container-engine detection, NO env overrides — those are 2.7's concerns. 2.9 inherits only: the first-task install_dir assert, the `not ansible_check_mode` gating on fragment-touching tasks, and the stat+assert direct-run prerequisite pattern.
- **2.6 assets** (copy + repo_root): 2.6 copies from `<repo>/dotfiles/assets/**` into the install spine; 2.9 copies from `<repo>/dotfiles/config/{hypr,hyprpaper,waybar}/` into `~/.config/...` (user config, NOT the install spine) and from the install spine into `~/.config/...` (fragments). `remote_src: true` + trailing-`/` src applies to the skeleton copies.
- **2.5 filesystem** (XDG config home): 2.5 CREATES the dirs; 2.9 COPIES into them. Share the exact XDG derivation, do not duplicate logic with a different result.

### Deferred work (2.8 review) not to re-open here

- "Missing/partial palette fragment at first boot has no fallback — ordering/verify is owned by 2.9 + 2.12 + 3.2/3.3" — 2.9 OWNS the fail-loud fragment-presence guard (stat+assert above); the eventual runtime fallback is a Phase 2 concern. Do not add a "default colors fallback" beyond the fail-loud assert.
- Hyprland `rgb(hex)` format / version pinning, hyprlang deprecation: deferred, NOT this role's concern (value format is emitted by 2.7/csg; version pinning is the 2.3 packages role).

## Project Structure Notes

- `src/provisioning/ansible/roles/compositor_configs/tasks/main.yml` — NEW role tasks (copy skeletons + fragments + dirs + guards).
- `src/provisioning/ansible/roles/compositor_configs/vars/main.yml` — NEW role vars (repo root, XDG home, copy lists).
- `src/provisioning/ansible/playbooks/compositor-configs.yaml` — NEW one-per-role playbook.
- `src/provisioning/tests/unit/test_compositor_configs_role.py` — NEW structural real-file tests (mirror `test_default_palette_role.py`).
- Consumed, NOT modified: `dotfiles/config/{hypr,hyprpaper,waybar}/` (2.8 skeletons), `<install>/generated/palettes/{colors.conf,colors.gtk.css,colors.yaml}` (2.7 outputs), `dotfiles/provisioning/*.yaml` (2.1 lock), `dotfiles/assets/**`, `src/provisioning/src/**` (Python hexagon untouched).
- No new dependencies. No Python outside the test file.

## Testing Requirements

- Full gates: `uv run pytest` (334-pass baseline from Story 2.8 — see Git Intelligence), `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src tests` (new file must be mypy-clean; 10 pre-existing baseline errors remain in test_default_palette_role.py/test_cli_tools_role.py — do NOT chase them), `python tests/architecture/test_layering.py` (standalone nicety).
- New `src/provisioning/tests/unit/test_compositor_configs_role.py` (see Tasks/Subtasks): mirror `test_default_palette_role.py`'s `_find_ansible_dir()` walk-up resolver + `_module_key`/`_module`/`_module_text`/`_creates_value` helpers. Assert:
  - role tree, tasks parse, first task is the verbatim install_dir assert
  - exactly 3 skeleton copy tasks with `remote_src: true`, trailing-`/` `src`, `src` prefixed `{{ compositor_configs_repo_root }}/dotfiles/config/`, and **`force: false`** (the `force: false` assert is what locks AC 5 — without it a dev could silently fall back to copy's default `force: true` and clobber a user's edits)
  - fragment copy pair LOCKED: source `colors.conf`→dest hypr/colors.conf, source `colors.gtk.css`→dest waybar/colors.css (the rename)
  - fragment copies carry NO `creates:` and are gated `when: not ansible_check_mode`
  - fragment presence stat+assert pair (both gated `when: not ansible_check_mode`)
  - invariant string present in tasks/main.yml header ("skeletons never change" / "fragments are the Phase 2 overwrite target")
  - no become/become_user anywhere; no hardcoded absolute paths (trim lock)
  - vars: required keys, `compositor_configs_xdg_config_home` honors `XDG_CONFIG_HOME` (via ansible_facts.env), install-dir derived values use `{{ install_dir | trim }}`
  - playbook: parses, hosts localhost, gather_facts true, roles [compositor_configs], no become, no group_by

## Previous Story Intelligence

### Story 2.8 — Compositor Skeleton Configs (DONE 2026-08-12, the immediate predecessor)
- Authored the SOURCE this role copies: `dotfiles/config/hypr/hyprland.conf` (first line `source = ~/.config/hypr/colors.conf`), `dotfiles/config/waybar/style.css` (first line `@import "colors.css";`) + `config` (JSONC bar), `dotfiles/config/hyprpaper/hyprpaper.conf` (flat static). The structural test `test_compositor_skeleton_configs.py` locks those exact strings — this role's copies must make them TRUE on the machine (fragments land at the exact paths the skeletons reference). [Source: 2-8-compositor-skeleton-configs.md]
- Locked decision: skeletons are STATIC, NO `.j2`/`.tpl` suffix, "the skeleton only sources the fragment, never inlines colors". This role must not change them, only copy.
- Review finding 2026-08-12 (waybar fragment): the pre-2.8 `@colorN` refs matched no csg format; the fragment is now emitted as `gtk.css` (naming `@define-color color_00..15`, refs `@color_00`/`@color_07`/`@color_10` + accent `@color_01`) and copied by this role as `~/.config/waybar/colors.css`. This is WHY the copy source is `colors.gtk.css`, not `colors.css`.
- Deferred entries from 2.8 review: "Missing/partial palette fragment at first boot has no fallback — ordering/verify is owned by 2.9" — 2.9 OWNS the fail-loud fragment-presence guard.

### Story 2.7 — Default Palette Role (the fragment producer)
- Emits `<install>/generated/palettes/colors.conf` (Hyprland `conf` format), `colors.gtk.css` (Waybar `gtk.css` format — NOT `colors.css`), `colors.yaml` (ITR) via `csg generate -f conf -f gtk.css -f yaml` in CONTAINER mode. These are the fragment sources 2.9 copies. [Source: 2-7-default-palette-role.md, default_palette/tasks/main.yml]
- Establishes the direct-run-prerequisite discipline 2.9 mirrors: first-task install_dir assert (verbatim), `when: not ansible_check_mode` gating on command tasks, stat+assert presence pairs, no become, no hardcoded absolute paths (trim lock).

### Story 2.5 — Filesystem Role (the dir creator)
- Creates `~/.config/{hypr,hyprpaper,waybar}/` via `filesystem_xdg_config_home` (honors `$XDG_CONFIG_HOME`, default `{{ ansible_facts.env.HOME }}/.config`, `ansible_facts.env` NOT `ansible_env`). This role copies INTO those dirs — must use the identical derivation. [Source: filesystem/vars/main.yml#23-31]

### Story 2.6 — Assets Role (the copy pattern mirror)
- `assets_repo_root: "{{ playbook_dir }}/../../../.."` + `remote_src: true` + trailing-`/` src (contents-into-dest) + "Ensure deploy targets exist" dir tasks — the copy mechanics 2.9 reuses. [Source: assets/vars/main.yml#15-19, assets/tasks/main.yml#56-62]

### Epic 1 retrospective (2026-08-08) — action item touching this story
- "Mirror-and-adapt discipline": explicit "what differs from the mirror" checklist (addressed in Dev Notes).

## Git Intelligence

- Current HEAD baseline: `5577a71` (`feat: implement story 2.8 compositor skeleton configs`, 2026-08-12 14:02). Working tree is DIRTY — the 2.8 REVIEW FINDINGS are uncommitted (13 modified files: `dotfiles/config/waybar/{config,style.css}`, `default_palette/{tasks,vars}/main.yml`, `test_default_palette_role.py`, `test_compositor_skeleton_configs.py`, specs/plan/sprint-status/deferred-work docs). **This story's fragment source naming (`colors.gtk.css` → `colors.css`) DEPENDS on those uncommitted 2.8-review changes being present in the tree** — they are (verified). Do NOT commit this story's files while discarding them; do NOT "fix" the 2.7 palette back to `colors.css`. If you must preserve a clean baseline, `git stash` the review findings is NOT safe (this story needs them) — leave the dirty tree as-is and only stage/add your own files.
- The 334-pass baseline is Story 2.8's final state (`+13 skeleton tests` over the 280-pass 2.7 baseline; 2.8's own completion note records `334 passed`).
- Commit flow pattern (follow it): `chore: create story 2.9 compositor configs role` (this story) → `feat: implement story 2.9 ...` → `fix: apply ... code review findings` → `chore: mark story 2.9 ... done`. Recent history: 2.8 (`59f293e`/`5577a71`), 2.7 (`8d8a3b8`/`8a371c1`/`8be9fc7`/`521fa7d`), 2.6 (`117e5e3`/`a6a74c8`/`8d8a3b8`).
- This story adds ONLY: `src/provisioning/ansible/roles/compositor_configs/**`, `src/provisioning/ansible/playbooks/compositor-configs.yaml`, `src/provisioning/tests/unit/test_compositor_configs_role.py`. Verify with `git status --short` that nothing else moved.

## Latest Tech Information

- ansible-core 2.21.2 is the installed/runtime version (verified 2026-08-12 via `uv run ansible --version`); pyproject requires `ansible-core>=2.16`. Collections: community.general 13.2.0, ansible.posix 2.2.2, kewlfft.aur 0.13.0 (pinned in requirements.yml). No new collections needed — `ansible.builtin.copy`/`file`/`stat`/`assert` are core.
- `ansible.builtin.copy`: check_mode support is FULL (action plugin predicts changed without writing) → skeleton copies need no `not ansible_check_mode` gate. `remote_src: true` copies from the target node (the local repo checkout — provisioning runs locally). Idempotent via checksums. `force: true` (default) replaces when content differs — the mechanism that makes fragments the overwrite candidates. Does NOT create `dest` parents for file sources → ensure the config dirs first. [Source: ansible.builtin.copy module docs, verified 2026-08-12]
- F4 lock (repo-wide): read env via `ansible_facts.env`, never the deprecated top-level `ansible_env` fact (INJECT_FACTS_AS_VARS hard-breaks on ansible-core >= 2.24). The XDG derivation must use `ansible_facts.env.XDG_CONFIG_HOME` / `ansible_facts.env.HOME`.
- `gather_facts: true` is REQUIRED on the playbook (vars derive from `ansible_facts.env.HOME` and the fragment copies interpolate `ansible_facts.env`).

## References

- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#416-431] — Story 2.9 ACs (compositor configs role)
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#40] — FR-19 Compositor Configs Role
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#250-256] — FR-19 PRD detail (skeleton never changes; fragments overwrite candidates; idempotent)
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/chaining-spine.md#119-129] — compositor color-fragment provenance table (colors.conf → `~/.config/hypr/colors.conf`; `colors.gtk.css` → `~/.config/waybar/colors.css`; skeletons never change)
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#46] — compositor color fragments (source/import lines)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#153,162] — plan §6: `compositor-configs.yaml` playbook + `compositor_configs/` role tree
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#203-206] — compositor color-fragment contract (fragments overwrite; skeleton never changes)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#246] — done-criterion 7 (compositor configs placed; `~/.config/hypr/colors.conf` and `~/.config/waybar/colors.css` present)
- [Source: src/provisioning/ansible/roles/default_palette/vars/main.yml#79-90] — the `gtk.css` → `~/.config/waybar/colors.css` rename contract (review finding 2026-08-12)
- [Source: src/provisioning/ansible/roles/filesystem/vars/main.yml#23-31] — `filesystem_xdg_config_home` derivation to mirror as `compositor_configs_xdg_config_home`
- [Source: src/provisioning/ansible/roles/assets/vars/main.yml#15-19] — `assets_repo_root` derivation to mirror as `compositor_configs_repo_root`
- [Source: src/provisioning/ansible/roles/default_palette/tasks/main.yml#64-70] — the verbatim first-task install_dir assert to copy
- [Source: src/provisioning/ansible/roles/assets/tasks/main.yml#56-62] — "Ensure deploy targets exist" dir-ensure pattern
- [Source: src/provisioning/tests/unit/test_default_palette_role.py] — the structural-test pattern to mirror (walk-up resolver, module helpers, check-gating asserts)
- [Source: _bmad-output/implementation-artifacts/deferred-work.md#205-209] — 2.8 deferred entries (fragment-ordering owned by 2.9; Hyprland version/hyprlang deferred)
- [Source: _bmad-output/implementation-artifacts/2-8-compositor-skeleton-configs.md] — skeletons authored in 2.8; the `gtk.css` review finding; the `<install>` bake decision
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml#74] — story 2-9-compositor-configs-role status (backlog → ready-for-dev this run)

## Dev Agent Record

### Agent Model Used

opencode (deepseek-v4-flash)

### Debug Log References

- Working tree baseline is dirty with the uncommitted 2.8 review findings (13 files). The fragment-copy source naming (`colors.gtk.css`) depends on them — they are present and load-bearing. Do NOT reset/stash/checkout them.
- Pre-existing mypy baseline: `uv run mypy src tests` reports 10 errors in `tests/unit/test_default_palette_role.py` and `tests/unit/test_cli_tools_role.py` — present at baseline commit `5577a71`, NOT introduced by this story. The new `test_compositor_configs_role.py` must be mypy-clean.

### Completion Notes List

- Created Story 2.9 Compositor Configs Role context: `compositor_configs` role (copy skeletons + fragments), `compositor-configs.yaml` playbook, structural tests.
- Locked the `colors.css` rename: fragment copy source is `colors.gtk.css` (2.7 output), dest basename `colors.css` (skeleton import + done-criterion 7) — the AC's literal `colors.css` source is a stale reference.
- Locked XDG-config-home derivation mirror (2.5) for the copy destinations; `ansible_facts.env` (F4 lock).
- Scope guards: no manifest (no sixth manifest — parity lives in the copy-list ↔ skeleton/fragment-name structural test), no Python hexagon changes, no skeleton edits, no `default_palette` changes.
- Status → ready-for-dev.

### File List

- `src/provisioning/ansible/roles/compositor_configs/tasks/main.yml` (NEW)
- `src/provisioning/ansible/roles/compositor_configs/vars/main.yml` (NEW)
- `src/provisioning/ansible/playbooks/compositor-configs.yaml` (NEW)
- `src/provisioning/tests/unit/test_compositor_configs_role.py` (NEW)
- `_bmad-output/implementation-artifacts/2-9-compositor-configs-role.md` (this story)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (status update)
