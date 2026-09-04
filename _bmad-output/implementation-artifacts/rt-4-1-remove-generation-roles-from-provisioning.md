---
baseline_commit: f45eb4a80537f0bb5e2097e9ce4b9e22db04f5cb
---

# Story rt-4.1: remove generation roles from provisioning bootstrap

Status: done

## Story

As an operator,
I want provisioning to deploy inputs only (no palette/icons generation),
So that the runtime is the single source of truth and bootstrap never
produces stale `generated/` artifacts.

## Scope Reality (READ FIRST)

This story deletes provisioning-side generation. It does NOT change
the runtime, AGS, or settings templates (those are rt-4-2 / rt-4-3).
After this story alone, a fresh bootstrap has NO palette/icons until
the runtime seed runs — that gap is closed by rt-4-2 landing in the
same commit window (see Epic 4 ordering).

**Delete / retire:**
- `src/provisioning/ansible/roles/default_palette/` (entire role —
  `csg generate` into `generated/palettes/`)
- `src/provisioning/ansible/roles/icons/` (entire role —
  `itr render` into `generated/icons/`)
- `default-palette.yaml` + `icons.yaml` playbooks: DELETE both files
  (verified: only `bootstrap.yaml` imports them; the provisioning
  Python CLI only references `bootstrap.yaml`).
- `compositor_configs` fragment-copy tasks (the two entries in
  `compositor_configs_fragment_copies` + the stat/assert/copy/guard
  tasks that consume them; skeletons stay)

**Add (the bootstrap seed invocation — closes the fresh-machine gap):**
- New `runtime-seed.yaml` playbook (single task): runs
  `dotfiles-runtime wallpaper set <install>/wallpapers/default.png`
  via `ansible.builtin.command`, gated `when: not ansible_check_mode`
  (dry-run must be dry — command tasks skip under `--check`).
  `install_dir` seam assert first (verbatim sibling pattern).
  Placement in `bootstrap.yaml`: after `config-links.yaml`, before
  `display-manager.yaml` (needs `assets` outputs + `settings` ITR
  config + `config_links` symlinks; must precede `verify`).
- **Atomicity gate: rt-4-1 must NOT merge without rt-4-2.** Landing
  rt-4-1 alone leaves fresh bootstraps with no palette at all (worse
  than stale). The two stories share one commit window.

**Keep (inputs only):**
- `assets` role (wallpapers, icon-templates, icon-mappings,
  csg-templates, weg-effects catalog) — unchanged
- `filesystem` role (spine dirs) — REMOVE `generated`, `generated/*`
  from `filesystem_spine_dirs` (they must no longer be created)
- `settings` role — unchanged in this story (ITR template repoint is rt-4-3)

## Acceptance Criteria

1. **Bootstrap has no generation steps** — `bootstrap.yaml` contains
   no `default-palette.yaml` / `icons.yaml` imports. The dependency
   comment block is updated (no `default_palette` in the order list).
2. **Fragment copies are gone** — `compositor_configs_fragment_copies`
   is empty/absent; no task in the role references
   `generated/palettes/`; the dont-clobber guard + classification stat
   for fragments are removed (nothing left to guard — R2 symlinks are
   owned by the runtime, rt-4-2).
3. **Filesystem spine has no `generated/`** — `filesystem_spine_dirs`
   contains no `generated*` entries; a fresh `filesystem.yaml` run
   creates no `generated/` tree.
4. **No dangling references** — `rg "default_palette|default-palette"` over
   `src/provisioning/ansible/{playbooks,roles/{bootstrap,compositor_configs,filesystem,verify},tests}/`
   returns zero hits outside explicitly marked historical notes.
   `rg "generated/palettes|generated/icons"` over
   `playbooks/bootstrap.yaml`, `compositor_configs/{tasks,vars}/`,
   `filesystem/vars/` returns zero hits. EXEMPT (must stay):
   `compositor_configs` reading `icon-mappings/icons.yaml` (inputs, not
   generated output), `verify` vars/tasks (updated in rt-4-4, not here).
5. **Provisioning tests green** — `uv run pytest` in `src/provisioning/`
   passes. Files touched: DELETE `tests/unit/test_default_palette_role.py`
   + `tests/unit/test_icons_role.py`; UPDATE `test_compositor_configs_role.py`
   (drop fragment cases), `test_filesystem_role.py` (drop generated dirs),
   `test_verify_role.py` ONLY where it asserts removed roles (criterion 6/10
   rework itself is rt-4-4); ADD `test_bootstrap` order test for the seed
   step placement + check-gating.

## Tasks / Subtasks

- [x] Task 1: Delete generation roles + playbooks (AC 1)
- [x] Task 2: Add runtime-seed playbook + bootstrap order (AC 1)
- [x] Task 3: Strip fragment copies from compositor_configs (AC 2)
- [x] Task 4: Remove generated/ from filesystem spine dirs (AC 3)
- [x] Task 5: Update tests (AC 5)

## Dev Notes

### Pinning sources

- Epic 4: `_bmad-output/planning-artifacts/epics-runtime-single-source.md`
- Investigation: `_bmad-output/investigation-runtime-icon-duality.md`
- Bootstrap order: `src/provisioning/ansible/playbooks/bootstrap.yaml:7-9`
- Fragment copies: `compositor_configs/vars/main.yml:154-166`
- Verify palette gate (updated in rt-4-4, not here)

### Scope boundary

Do NOT touch `verify` (rt-4-4), `settings` templates (rt-4-3),
runtime (rt-4-2), or AGS (rt-4-3) in this story.

## Dev Agent Record

### Agent Model Used

OpenCode powered by Meta Muse Spark (muse-spark-1.3-contributor-free)

### Debug Log References

- Deleted `roles/default_palette/`, `roles/icons/`,
  `playbooks/default-palette.yaml`, `playbooks/icons.yaml` via `git rm`;
  verified the provisioning Python CLI only references `bootstrap.yaml`.
- Added `playbooks/runtime-seed.yaml` (single check-gated
  `dotfiles-runtime wallpaper set <install>/wallpapers/default.png`
  task + install_dir seam assert); placed after `config-links.yaml`,
  before `display-manager.yaml` in `bootstrap.yaml` with updated order
  comment.
- `bootstrap.yaml` import count 15 → 14 (tests updated).
- Compositor execution tests exposed a PRE-EXISTING failure (temp HOME
  lacks `.local/bin` for the bin-scripts copy task; fails on unmodified
  code too) — fixed the test env (create the dir) so the role is
  actually exercised; both execution tests now pass.
- Full provisioning unit suite: 463 passed, 2 pre-existing failures
  (`test_ansible_scaffold` debian set, `test_packages_role` distro
  branching — fail on unmodified code in 0.13s, unrelated).

### Completion Notes List

- ✅ Task 1 (rt-4-1): generation roles + playbooks deleted.
- ✅ Task 2 (rt-4-1): runtime-seed playbook + bootstrap order added.
- ✅ Task 3 (rt-4-1): fragment copies stripped from compositor_configs
  (tasks + vars + header comments).
- ✅ Task 4 (rt-4-1): generated/ removed from filesystem spine + manifest.
- ✅ Task 5 (rt-4-1): tests updated (bootstrap order/count, compositor
  fragment→hands-off tests, filesystem manifest parity, dryrun list).

### File List

- `src/provisioning/ansible/playbooks/bootstrap.yaml` (modified)
- `src/provisioning/ansible/playbooks/runtime-seed.yaml` (created)
- `src/provisioning/ansible/playbooks/default-palette.yaml` (deleted)
- `src/provisioning/ansible/roles/icons/` (deleted)
- `src/provisioning/ansible/roles/default_palette/` (deleted)
- `src/provisioning/ansible/playbooks/icons.yaml` (deleted)
- `src/provisioning/ansible/roles/compositor_configs/tasks/main.yml` (modified)
- `src/provisioning/ansible/roles/compositor_configs/vars/main.yml` (modified)
- `src/provisioning/ansible/roles/filesystem/vars/main.yml` (modified)
- `dotfiles/provisioning/filesystem.yaml` (modified)
- `src/provisioning/tests/unit/test_bootstrap_playbook.py` (modified)
- `src/provisioning/tests/unit/test_compositor_configs_role.py` (modified)
- `src/provisioning/tests/unit/test_filesystem_role.py` (modified)
- `src/provisioning/tests/integration/test_ansible_dryrun.py` (modified)
- `src/provisioning/tests/unit/test_default_palette_role.py` (deleted)
- `src/provisioning/tests/unit/test_icons_role.py` (deleted)
- `src/provisioning/tests/integration/test_settings_parity.py` (modified — generated/ fixture dirs removed)
