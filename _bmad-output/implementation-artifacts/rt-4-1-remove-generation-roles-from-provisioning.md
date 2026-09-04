---
baseline_commit: f45eb4a80537f0bb5e2097e9ce4b9e22db04f5cb
---

# Story rt-4.1: remove generation roles from provisioning bootstrap

Status: ready-for-dev

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
- `default-palette.yaml` + `icons.yaml` playbooks (or leave playbooks
  as stubs that fail loud with "removed in Epic 4"? — DECISION: delete
  playbooks + remove the two `import_playbook` lines from
  `bootstrap.yaml`)
- `compositor_configs` fragment-copy tasks (the two entries in
  `compositor_configs_fragment_copies` + the stat/assert/copy/guard
  tasks that consume them; skeletons stay)

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
4. **No dangling references** — `rg "default_palette|default-palette|icons\.yaml.*playbook|generated/palettes|generated/icons" src/provisioning/ansible/roles/{bootstrap,compositor_configs,filesystem}/`
   returns zero hits outside historical comments (comments updated).
5. **Provisioning tests green** — `uv run pytest` in `src/provisioning/`
   passes; role structural tests updated (default_palette/icons role
   tests deleted; compositor_configs tests drop fragment cases;
   filesystem tests drop generated dirs).

## Tasks / Subtasks

- [ ] Task 1: Delete generation roles + playbooks (AC 1)
- [ ] Task 2: Strip fragment copies from compositor_configs (AC 2)
- [ ] Task 3: Remove generated/ from filesystem spine dirs (AC 3)
- [ ] Task 4: Update tests (AC 5)

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

_To be filled by dev-story._

### Debug Log References

_To be filled by dev-story._

### Completion Notes List

_To be filled by dev-story._

### File List

_To be filled by dev-story._
