---
baseline_commit: 521fa7d
---

# Story 2.8: Compositor Skeleton Configs

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Change Log

- 2026-08-12: Story created — ultimate context engine analysis completed; comprehensive developer guide created (FR-23).

## Story

As an operator,
I want static skeleton compositor configs in the repo,
So that the compositor_configs role has source files to place.

## Acceptance Criteria

1. `dotfiles/config/hypr/hyprland.conf` exists and its FIRST line is `source = ~/.config/hypr/colors.conf` (AC 1, FR-23)
2. `dotfiles/config/waybar/style.css` exists and its FIRST line is `@import "colors.css";` (AC 2, FR-23)
3. `dotfiles/config/waybar/config` exists — the plan's "static config + style.css" for Waybar (AC 2, plan §6) — a minimal Waybar JSONC bar config that references `colors.css`
4. `dotfiles/config/hyprpaper/hyprpaper.conf` exists and is flat static pointing at the default wallpaper path (AC 3, FR-23): `preload = ~/.local/share/dotfiles/wallpapers/default.png` + `wallpaper = ,~/.local/share/dotfiles/wallpapers/default.png` (default install path baked in — see Dev Notes "The `<install>` bake decision")
5. Existing `dotfiles/config/{nvim,starship,wlogout,zsh}/` dirs are unchanged (AC 4, FR-23) — AND `dotfiles/config/icon-template-color-scheme-mappings/` (also present) is unchanged
6. No other story's files are touched: `dotfiles/provisioning/*.yaml` (locked Story 2.1), `src/provisioning/ansible/**` (roles are 2.2-2.7 + later), `src/provisioning/src/**` (Python hexagon), `docs/`, `scripts/`

## Tasks / Subtasks

- [ ] Create `dotfiles/config/hypr/` with `hyprland.conf` (AC: 1)
  - [ ] First line: `source = ~/.config/hypr/colors.conf` (verbatim; the file is symlinked/copied by later stories, so the source must match the `~/.config/hypr/colors.conf` fragment target from Story 2.7/2.9)
  - [ ] Remainder: a minimal-but-valid Hyprland skeleton (see Dev Notes "Skeleton content guidance") — do NOT reference colors before the `source` line
- [ ] Create `dotfiles/config/waybar/` with `style.css` and `config` (AC: 2, 3)
  - [ ] `style.css` first line: `@import "colors.css";` (verbatim; imports the Story 2.7-emitted Waybar fragment copied by 2.9)
  - [ ] `config`: minimal Waybar JSONC bar config (see Dev Notes "Skeleton content guidance")
- [ ] Create `dotfiles/config/hyprpaper/` with `hyprpaper.conf` (AC: 4)
  - [ ] Flat static: `preload = ~/.local/share/dotfiles/wallpapers/default.png` and `wallpaper = ,~/.local/share/dotfiles/wallpapers/default.png` (default install path baked in — the ONLY value determinable at authoring time)
  - [ ] No templating, no placeholders, no `<install>` literal — the file must be truly static (see Dev Notes "The `<install>` bake decision")
- [ ] Add structural real-file tests `src/provisioning/tests/unit/test_compositor_skeleton_configs.py` (AC: 1-6)
  - [ ] Walk-up repo-root resolver (`_find_repo_root()`), mirroring `_find_ansible_dir()` but anchored on `dotfiles/config/hypr/hyprland.conf`
  - [ ] `hypr/hyprland.conf` exists and first line == `source = ~/.config/hypr/colors.conf` (AC 1)
  - [ ] `waybar/style.css` exists and first line == `@import "colors.css";` (AC 2)
  - [ ] `waybar/config` exists (AC 3)
  - [ ] `hyprpaper/hyprpaper.conf` exists and contains both the `preload = ~/.local/share/dotfiles/wallpapers/default.png` and `wallpaper = ,~/.local/share/dotfiles/wallpapers/default.png` lines (AC 4) — assert the two exact strings, not a regex, so a future path change is a loud test failure
  - [ ] Existing dirs still contain their known files: `nvim/init.lua`, `starship/starship.toml`, `wlogout/layout`, `wlogout/style.css.tpl`, `zsh/.zshrc.j2`, and at least one `icon-template-color-scheme-mappings/*.yaml` (AC 5 — locks "unchanged" at the file-presence level without freezing a future story's legitimate additions)
  - [ ] No `.j2`/`.tpl`/`.j2`-style placeholder suffix on the three new skeleton files (they are STATIC, unlike zsh `.j2` / wlogout `.tpl`)
- [ ] Verify full suite + lint + layering guard (AC: 6)
  - [ ] `uv run pytest` — full suite green, nothing regresses from the 280-pass baseline (Story 2.7)
  - [ ] `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean
  - [ ] `python tests/architecture/test_layering.py` exits 0 (standalone nicety)
  - [ ] `git status --short` shows ONLY new skeleton files + the new test file (AC 6)

## Dev Notes

### Scope — what Story 2.8 is and is not

**IS:** authoring the three static skeleton dirs under `dotfiles/config/` — `hypr/`, `hyprpaper/`, `waybar/` (FR-23) — plus structural real-file tests locking the ACs. It is the SOURCE for Story 2.9's `compositor_configs` role, which copies these skeletons to `~/.config/{hypr,hyprpaper,waybar}/` and is the destination the done-criterion-7 symlink/fragment checks assume.

**IS NOT:** the `compositor_configs` role (Story 2.9), the `symlinks` role (2.10), the `settings` role (2.11), the `verify` role (2.12), the aggregate `bootstrap.yaml` (2.12), or any Ansible content. Do NOT author roles, playbooks, or `tasks/main.yml`. Do NOT touch `dotfiles/provisioning/*.yaml` — the five manifests are LOCKED in Story 2.1 (this story is purely additive under `dotfiles/config/`). Do NOT add any `.py` under `ansible/`. Do NOT modify `dotfiles/assets/**`.

### The `<install>` bake decision — the one real design tension in this story

The AC says the Hyprpaper skeleton "is flat static pointing at `<install>/wallpapers/default.png`", and the chaining-spine calls it "baked into flat static `hyprpaper.conf`". Two readings were possible:

1. **Static file with the DEFAULT install path baked in** — `$XDG_DATA_HOME/dotfiles/` defaults to `~/.local/share/dotfiles/` (SPEC.md line 72, chaining-spine line 7). The skeleton is authored ONCE with that default literal, because that is the only value determinable at authoring time.
2. **A template/placeholder** (e.g. `hyprpaper.conf.j2` with `{{ install_dir }}`) that Story 2.9 renders at apply time.

**Locked decision: reading 1 (literal static file).** Rationale:
- The plan (§6 tree) names the file `hyprpaper.conf` — NOT `hyprpaper.conf.j2` — and calls it "flat static" three separate times (plan §6, chaining-spine line 127/129, SPEC line 46). The repo's templated configs are explicitly suffixed (zsh `.zshrc.j2`, wlogout `style.css.tpl`); a static file is NOT suffixed.
- Story 2.9's AC says the role "copies `dotfiles/config/{hypr,hyprpaper,waybar}/` skeletons to `~/.config/...`" — a `copy` semantic, not a `template` semantic. A `.j2` source would force Story 2.9 to render, contradicting "copies skeletons" and the "skeletons never change" invariant.
- Phase 2 is explicitly the overwrite/re-bake layer ("Phase 2 rewrites only when the wallpaper actually changes"; "writing derived colors into the Hyprland/Hyprpaper/Waybar templates provisioning just placed" is deferred to Phase 2 — plan §12). A non-default `install_dir` that needs re-baking is a Phase 2 concern, not this story's.
- **Consequence to record in the file:** the skeleton is correct only for the DEFAULT install path. If a user provisions with a non-default `$XDG_DATA_HOME`, Hyprpaper will point at the default location until Phase 2 re-bakes. This is accepted (SPEC-ratified), not a bug to fix in 2.8. Do NOT "helpfully" template it.

**Do NOT leave a literal `<install>` placeholder** in the file. The `<install>` notation in the AC/SPEC is documentation shorthand for "the install dir"; a raw `<install>` string in a Hyprpaper config would be a broken path (Hyprpaper would treat `<install>` as a literal directory name). The test must assert the concrete `~/.local/share/dotfiles/...` strings so a dangling placeholder can never pass.

### Skeleton content guidance

The skeletons are FIRST-BOOT MINIMAL — functional enough that Story 2.9's placement + Story 3.2/3.3's integration checks pass, but deliberately thin (Phase 2 owns rich theming). Author reasonable, idiomatic content; the ACs only pin the header lines and the Hyprpaper path, and the tests lock those. Do not gold-plate.

- **`hypr/hyprland.conf`**: first line `source = ~/.config/hypr/colors.conf`, then a minimal valid Hyprland config — at minimum: a `monitor` line, a couple of `general`/`decoration` settings that consume the sourced vars (e.g. `col.active_border` referencing a `$color` var), and an `exec-once` for `hyprpaper`. Reference variables defined by `colors.conf` (the Story 2.7 fragment exposes `$background/$foreground/$cursor/$accent/$color0..15`). The sourced fragment is a SEPARATE file (copied by 2.9 to `~/.config/hypr/colors.conf`) — the skeleton only `source`s it, never inlines colors.
- **`waybar/style.css`**: first line `@import "colors.css";`, then minimal CSS using a couple of `@colorN` variables (matching the wlogout `.tpl` variable naming idiom, e.g. `@color16`/`@color10`).
- **`waybar/config`**: minimal Waybar JSONC (a bar with a clock + a couple of modules) — the plan §6 calls out "static config + style.css" for Waybar, so both files belong in the dir. JSONC (comments allowed) is standard Waybar.
- **`hyprpaper/hyprpaper.conf`**: exactly two functional lines — `preload = ~/.local/share/dotfiles/wallpapers/default.png` and `wallpaper = ,~/.local/share/dotfiles/wallpapers/default.png` (empty monitor selector applies to all monitors; keep the comma). Add a short header comment explaining the baked default path and the Phase 2 re-bake note.

### Where files live (locked by plan §6)

```
dotfiles/config/
├── hypr/
│   └── hyprland.conf                      ← NEW — first line `source = ~/.config/hypr/colors.conf`
├── hyprpaper/
│   └── hyprpaper.conf                     ← NEW — flat static, default wallpaper path baked
├── waybar/
│   ├── config                             ← NEW — minimal JSONC bar
│   └── style.css                          ← NEW — first line `@import "colors.css";`
├── icon-template-color-scheme-mappings/   ← existing — UNCHANGED
├── nvim/                                  ← existing — UNCHANGED
├── starship/                              ← existing — UNCHANGED
├── wlogout/                               ← existing — UNCHANGED
└── zsh/                                   ← existing — UNCHANGED
```

- Everything lives OUTSIDE the Python hexagon — static YAML-free content, never scanned by `tests/architecture/test_layering.py`. **No `.py` file goes under `dotfiles/config/`.** The only Python added is the structural test under `src/provisioning/tests/unit/`.
- Naming: skeleton dirs are exactly `hypr` / `hyprpaper` / `waybar` (no dash, no `.config` suffix) — they mirror the `~/.config/{hypr,hyprpaper,waybar}` targets Story 2.9 copies to and Story 2.5's filesystem role creates. Do not rename.
- The `symlinks.yaml` header comment ("hypr/hyprpaper/waybar are NOT listed — those dirs land in Story 2.8") is a NAVIGATION NOTE, not an instruction: it means the dirs come into existence here. Whether/how they join `symlinks.yaml` is Story 2.10's call (symlinks role reads that manifest). Do NOT edit `symlinks.yaml` in this story.

### Check-mode / idempotency

Not applicable — this story authors static repo content, not Ansible tasks. No `--check` gating, no `creates:`, no run-state. The "idempotent" discipline here is: re-running the story's test suite is deterministic, and the files are inert until a later role copies them.

### Why no fixture/manifest parity

Stories 2.3-2.6 had `dotfiles/provisioning/*.yaml` manifests that their roles consumed (manifest-parity tests). Skeleton configs have NO manifest — there is no `dotfiles/provisioning/compositor.yaml`, and plan §6 defines no such manifest (the manifests are exactly the five locked in 2.1). The skeleton contract is enforced by the structural test asserting the exact header/path strings, not by manifest parity. Do NOT invent a sixth manifest.

### Mirror-and-adapt discipline (Epic 1 retro action item)

This story mirrors the Story 2.1 "repo-content" pattern (author repo files + real-file tests). "What differs from the mirror": 2.1's manifests are consumed by `YamlManifestReader` and tested through it; these skeletons have NO Python consumer in Phase 1, so the tests are pure structural real-file assertions (existence + exact first-line/path strings) rather than reader-parsing tests. State this in the test module docstring so a reviewer doesn't "fix" the test to go through a reader that doesn't exist.

## Project Structure Notes

- `dotfiles/config/hypr/hyprland.conf` — NEW static skeleton.
- `dotfiles/config/hyprpaper/hyprpaper.conf` — NEW static skeleton.
- `dotfiles/config/waybar/config` — NEW static skeleton.
- `dotfiles/config/waybar/style.css` — NEW static skeleton.
- `src/provisioning/tests/unit/test_compositor_skeleton_configs.py` — NEW structural real-file tests.
- Unchanged: `dotfiles/config/{nvim,starship,wlogout,zsh,icon-template-color-scheme-mappings}/`, `dotfiles/provisioning/*.yaml`, `dotfiles/assets/**`, `src/provisioning/ansible/**`, `src/provisioning/src/**` (Python hexagon untouched), `docs/`, `scripts/`.
- No new dependencies. No Ansible content. No `.py` under `dotfiles/` or `ansible/`.

## Testing Requirements

- Full gates: `uv run pytest` (280-pass baseline from Story 2.7 — see Git Intelligence), `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src tests`, `python tests/architecture/test_layering.py` (standalone nicety).
- New `src/provisioning/tests/unit/test_compositor_skeleton_configs.py` (see Tasks/Subtasks): repo-root walk-up resolver anchored on `dotfiles/config/hypr/hyprland.conf` (mirror `_find_ansible_dir()`; fail loudly at import if the tree is missing); exact-string first-line assertions for `hyprland.conf` and `style.css`; `waybar/config` existence; exact-string `preload`/`wallpaper` lines in `hyprpaper.conf` (rejecting a raw `<install>` placeholder); existing-dir known-file presence checks; a "no template suffix" check on the three new files.
- The test lives in `src/provisioning/tests/unit/` (with the sibling role tests) — it does NOT require the ansible tree; the walk-up is anchored on the repo-root `dotfiles/config/` marker, not on `pyproject.toml`+`ansible/` (that anchor would fail: the config skeleton lives at repo root, not under `src/provisioning`).

## Previous Story Intelligence

### Story 2.7 — Default Palette Role (the immediate predecessor; DONE 2026-08-12)
- Emits the fragments these skeletons consume: `csg generate -f conf -f css -f yaml` → `<install>/generated/palettes/colors.conf` (Hyprland), `colors.css` (Waybar), `colors.yaml` (ITR). 2.9 copies `colors.conf` → `~/.config/hypr/colors.conf` and `colors.css` → `~/.config/waybar/colors.css`. [Source: 2-7-default-palette-role.md, roles/default_palette/tasks/main.yml]
- `$accent == $color1` Hyprland contract — the sourced fragment exposes `$color0..15`, which the Hyprland skeleton may reference.
- The "skeletons never change; fragments are the Phase 2 overwrite target" invariant (Story 2.9 AC) — the skeletons authored here MUST be static (2.8 ships the source), and the fragment FILES are the only overwrite candidates (2.9's job).

### Story 2.1 — Declarative Manifests (the "repo-content" mirror)
- Locked `dotfiles/provisioning/*.yaml` — do NOT touch in this story. [Source: 2-1-declarative-manifests.md, sprint-status.yaml 2-1 status]
- Real-repo-file test pattern (anchor on repo, assert exact content) — the structural-test ancestor of what 2.8 does for skeletons. [Source: tests/unit/adapters/test_yaml_manifest_reader.py]

### Story 2.5 — Filesystem Role
- Creates `~/.config/{hypr,hyprpaper,waybar}/` dirs on the target — the destination 2.9 copies these skeletons into. No 2.8 dependency, but confirms the target dir names exactly match these dir names. [Source: roles/filesystem/vars/main.yml]

### Story 2.6 — Assets Role
- Unpacks `default.png` to `<install>/wallpapers/` — the file the baked Hyprpaper path points at. The default path `~/.local/share/dotfiles/wallpapers/default.png` resolves to the spine the filesystem role (2.5) + assets role (2.6) create, under the DEFAULT `$XDG_DATA_HOME`. [Source: roles/assets/tasks/main.yml]

### Epic 1 retrospective (2026-08-08) — action item touching this story
- **"Mirror-and-adapt discipline"** — when copying sibling patterns, add an explicit "what differs from the mirror" checklist. Addressed in Dev Notes.

## Git Intelligence

- Current HEAD baseline: `521fa7d` (`fix: auto-commit code review findings (post-generate verify)`). Working tree is CLEAN (verified 2026-08-12) — no uncommitted work to preserve; 2.7 fully landed (commits `8a371c1` → `521fa7d`).
- The 280-pass baseline is from Story 2.7's final "P2 (post-generate verification)" state (2.7 said "280 tests green" on 2026-08-12 after the container-mode + P2 passes; 2.7's `309 passed` line predates the P2 refactor that removed 29 tests).
- Commit flow pattern (follow it): `chore: create story 2.8 compositor skeleton configs` (this story) → `feat: implement story 2.8 ...` → `fix: apply ... code review findings` → `chore: mark story 2.8 ... done`. Recent history: 2.7 (`8d8a3b8`/`8a371c1`/`8be9fc7`/`521fa7d`), 2.6 (`117e5e3`/`a6a74c8`/`8d8a3b8`), 2.5 (`5325c8e`/`f95aa59`/`4f7f755`), 2.4 (`d074371`/`13086b1`/`ec95944`).
- This story touches ONLY files under `dotfiles/config/{hypr,hyprpaper,waybar}/` + the new test file — verify with `git status --short` that nothing else moved (AC 6).

## Latest Tech Information

- No new libraries/frameworks — pure static content. The only "runtime" consumers are Hyprland/Waybar/Hyprpaper themselves (installed by Story 2.3's packages role), and no tool invocation happens in this story.
- Hyprland config: `source = <path>` merges another config file; the fragment target `~/.config/hypr/colors.conf` must exist at runtime (2.9 copies it). Variable references (`$background`, `$color1`, etc.) resolve from sourced fragments.
- Waybar CSS: `@import "colors.css";` must be the first statement to be valid CSS. Waybar config files use JSONC (comments + trailing commas tolerated).
- Hyprpaper: config lines are `preload = <path>` and `wallpaper = [monitor],[path]`; an empty monitor selector applies to all outputs. `~` is expanded by Hyprpaper when reading the file (the standard user-config location idiom). The default install spine is `$XDG_DATA_HOME/dotfiles/` → `~/.local/share/dotfiles/` (SPEC.md line 72).
- Deferred-work entries from 2.7 (2026-08-12): none block this story — they are role/task concerns (uv bin-dir chain, `gather_facts` at 2.12, install-dir type guard, WEG container-mode in assets role, engine pre-flight). Ignore for 2.8.

## References

- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#401-414] — Story 2.8 ACs (compositor skeleton configs)
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#44] — FR-23 Compositor Skeleton Configs
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#281-286] — FR-23 PRD detail (skeleton contents + "existing dirs unchanged")
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#46] — compositor color fragments (Hyprland skeleton `source = ~/.config/hypr/colors.conf`; Waybar `@import "colors.css";`; Hyprpaper flat static pointing at `<install>/wallpapers/default.png`)
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#72] — `$XDG_DATA_HOME` defaults to `~/.local/share`
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/chaining-spine.md#121-129] — fragment provenance table + "flat static `hyprpaper.conf`"; skeletons never change
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#197-201] — plan §6 `dotfiles/config/` tree (hypr/hyprpaper/waybar NEW; existing dirs unchanged)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#204-206] — compositor color-fragment contract (fragments overwrite; skeleton never changes)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#246] — done-criterion 7 (compositor configs placed; `colors.conf`/`colors.css` present)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#285] — plan §11 step 9 (add the three skeleton dirs)
- [Source: _bmad-output/planning-artifacts/implementation-readiness-report-2026-08-03.md#216] — Story 2.8 authored as repo-content story (precedes role story 2.9)
- [Source: src/provisioning/tests/unit/test_default_palette_role.py#14-27] — `_find_ansible_dir()` walk-up pattern to mirror as `_find_repo_root()`
- [Source: dotfiles/config/zsh/.zshrc.j2, dotfiles/config/wlogout/style.css.tpl] — the repo's TEMPLATE suffix convention (`.j2`/`.tpl`) the static skeletons must NOT use
- [Source: dotfiles/provisioning/symlinks.yaml#1-5] — header note: hypr/hyprpaper/waybar "land in Story 2.8"; do NOT edit this file here (Story 2.10)
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml#73] — story 2-8-compositor-skeleton-configs status (backlog → ready-for-dev this run)

## Dev Agent Record

### Agent Model Used

opencode (deepseek-v4-flash)

### Debug Log References

### Completion Notes List

- Created Story 2.8 Compositor Skeleton Configs context: `dotfiles/config/{hypr,hyprpaper,waybar}/` static skeletons + `tests/unit/test_compositor_skeleton_configs.py`.
- Locked the `<install>` bake decision: literal default-path static file (`~/.local/share/dotfiles/wallpapers/default.png`), NOT a template — per plan/chaining-spine "flat static" + Story 2.9 "copies" semantics; Phase 2 owns re-bake.
- Locked the exact header contracts: `source = ~/.config/hypr/colors.conf` and `@import "colors.css";` first lines; Waybar dir ships both `config` + `style.css` (plan §6).
- Scope guards: no `dotfiles/provisioning/*.yaml` edits (Story 2.1 lock), no Ansible content (2.9+), no Python hexagon changes, existing config dirs unchanged (AC 4/5).
- Status → ready-for-dev.

### File List

- `dotfiles/config/hypr/hyprland.conf` (NEW)
- `dotfiles/config/hyprpaper/hyprpaper.conf` (NEW)
- `dotfiles/config/waybar/config` (NEW)
- `dotfiles/config/waybar/style.css` (NEW)
- `src/provisioning/tests/unit/test_compositor_skeleton_configs.py` (NEW)
- `_bmad-output/implementation-artifacts/2-8-compositor-skeleton-configs.md` (this story)
