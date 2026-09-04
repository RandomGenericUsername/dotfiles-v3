---
baseline_commit: f45eb4a80537f0bb5e2097e9ce4b9e22db04f5cb
---

# Story rt-4.4: verify current-only criteria + remove generated/ + docs

Status: ready-for-dev

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
`rm -rf` user state in a role; leave orphaned dirs in place (harmless)
and note it in the docs. (DECISION: orphan-tolerant, no deletion.)

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

1. **No `generated/` in spine or gates** — `rg "generated/"` over
   `src/provisioning/ansible/{playbooks,roles/{filesystem,verify,bootstrap*}}`
   + the four spec/doc files returns zero hits outside explicitly
   marked historical notes.
2. **Verify is current-only** — `verify.yaml` on a seeded machine
   passes with zero `generated/` content present (prove by moving
   `<install>/generated/` aside on the dev host and re-running verify).
3. **Bootstrap comment matches reality** — order list contains the
   runtime-seed step and no generation roles.
4. **All suites green** — provisioning `uv run pytest`, runtime
   `pytest` + `ruff` + `mypy` + layering, plus
   `ansible-playbook --syntax-check bootstrap.yaml`.

## Tasks / Subtasks

- [ ] Task 1: Verify role current-only criteria (AC 2)
- [ ] Task 2: Filesystem spine dirs cleanup (AC 1)
- [ ] Task 3: Bootstrap comment + order (AC 3)
- [ ] Task 4: Docs update (AC 1)
- [ ] Task 5: Full gates incl. aside-test (AC 2, 4)

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

_To be filled by dev-story._

### Debug Log References

_To be filled by dev-story._

### Completion Notes List

_To be filled by dev-story._

### File List

_To be filled by dev-story._
