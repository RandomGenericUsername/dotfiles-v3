---
baseline_commit: f45eb4a80537f0bb5e2097e9ce4b9e22db04f5cb
---

# Story rt-4.3: AGS runtime-only icons + ITR settings repoint

Status: ready-for-dev

## Story

As a user,
I want the bar to resolve icons exclusively through the runtime's
`current/icons/`,
So that icons always match the active palette with no stale fallback.

## Scope Reality (READ FIRST)

Two small, coupled changes (one story because they must land together —
otherwise ITR renders against a palette path that no longer has a
producer):

**1. `dotfiles/config/ags/lib/icon-registry.ts` — remove `generated/` fallback:**

```typescript
// DELETE:
const provisionPath = `${PROVISION_ICONS_DIR}/${variantEntry.output}`
if (GLib.file_test(provisionPath, GLib.FileTest.EXISTS)) return provisionPath
// DELETE the PROVISION_ICONS_DIR const if unused elsewhere
```

After: `resolve()` checks `current/icons/<output>` only, returns `null`
otherwise. Missing icons become VISIBLE (empty image) instead of
silently stale — the correct failure mode for a single-source design
(never show the wrong palette's icons).

**2. `src/provisioning/ansible/roles/settings/templates/itr-settings.toml.j2` —
repoint `color_scheme.path`:**

```toml
# BEFORE:
path = "{{ install_dir | trim }}/generated/palettes/colors.yaml"
# AFTER:
path = "{{ settings_xdg_state_home | trim }}/dotfiles/current/colors.yaml"
```

with a new role var in `settings/vars/main.yml` mirroring verify's
derivation (F4 lock + trim lock — the settings role currently has no
state-home var):

```yaml
# settings_xdg_state_home: state home honoring $XDG_STATE_HOME, same
# derivation as verify_xdg_state_home (Story 2-12). Used ONLY for the
# ITR color_scheme.path (runtime-owned current/); the role renders no
# other state paths.
settings_xdg_state_home: "{{ ansible_facts.env.XDG_STATE_HOME | default(ansible_facts.env.HOME | default(ansible_facts.user_dir) + '/.local/state', true) }}"
```

ITR runs on the host (local mode) and reads the settings through the
`~/.config/itr` symlink; the value is an absolute path the ITR process
can open.

Path need not exist at render time (ITR resolves at render time;
before first seed the file is absent and `itr render` fails loud —
correct, since nothing can render without a palette). Direct `itr`
use before first seed therefore fails with a clear missing-file
error, not a wrong-palette render — document that in the role header
comment.

## Acceptance Criteria

1. **No `generated/` reference in the registry** — `rg "generated"
   dotfiles/config/ags/lib/icon-registry.ts` returns zero hits.
2. **ITR settings point at `current/`** — rendered
   `<install>/config/itr/settings.toml` has `color_scheme.path`
   resolving (through the `~/.config/itr` symlink) to a path under
   `$XDG_STATE_HOME/dotfiles/current/colors.yaml`. No `generated/`
   substring in the rendered file.
3. **Missing icons are visible, not stale** — With no runtime cache
   entry, `registry.resolve()` returns `null` (widget shows empty),
   never a `generated/` path.
4. **Provisioning settings tests green** — settings role tests updated
   for the new template value; no other role test references the old
   `generated/palettes/colors.yaml` ITR path.

## Tasks / Subtasks

- [ ] Task 1: Strip the fallback from `icon-registry.ts` (AC 1, 3)
- [ ] Task 2: Repoint the ITR settings template (AC 2)
- [ ] Task 3: Update settings role tests (AC 4)

## Dev Notes

### Pinning sources

- Epic 4: `_bmad-output/planning-artifacts/epics-runtime-single-source.md`
- Registry: `dotfiles/config/ags/lib/icon-registry.ts:26-55`
- Template: `src/provisioning/ansible/roles/settings/templates/itr-settings.toml.j2`
- Investigation: `_bmad-output/investigation-runtime-icon-duality.md` (§AGS fallback)

### Scope boundary

Do NOT touch generation roles (rt-4-1), runtime seeder (rt-4-2), or
verify/docs (rt-4-4) in this story.

## Dev Agent Record

### Agent Model Used

_To be filled by dev-story._

### Debug Log References

_To be filled by dev-story._

### Completion Notes List

_To be filled by dev-story._

### File List

_To be filled by dev-story._
