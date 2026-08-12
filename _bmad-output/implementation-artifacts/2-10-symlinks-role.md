---
baseline_commit: fb0c979
---

# Story 2.10: Symlinks Role

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Change Log

- 2026-08-12: Story created — ultimate context engine analysis completed; comprehensive developer guide created (FR-20).
- 2026-08-12: Story implemented — `symlinks` role + playbook + 18 structural/parity/runtime tests; suite 355 → 373 green.

## Story

As an operator,
I want a `symlinks` role that links repo configs into `~/.config/`,
So that my dotfiles live in the repo and are referenced by the machine.

## Acceptance Criteria

1. `roles/symlinks/` role exists with `tasks/main.yml` (AC 1, FR-20)
2. Every entry in `dotfiles/provisioning/symlinks.yaml` is created as a symlink from repo `dotfiles/config/*` to `~/.config/*` (AC 2, FR-20)
3. Broken or missing targets are reported as failures (AC 3)
4. Re-runs are idempotent — existing symlinks are left unchanged (AC 4, FR-20, NFR-1)

## Tasks / Subtasks

- [x] Create `src/provisioning/ansible/roles/symlinks/vars/main.yml` (AC: 1-4)
  - [x] Open with the standard header comment: `# Symlinks role vars (Story 2.10).` + role-description + `# Mirror-and-adapt discipline (Epic 1 retro action item)` block itemizing what differs from each mirror (mirror `compositor_configs/vars/main.yml` header shape)
  - [x] `symlinks_repo_root`: `{{ playbook_dir }}/../../../..` (mirror `assets_repo_root`/`compositor_configs_repo_root` exactly — see Dev Notes "Where files live")
  - [x] `symlinks_xdg_config_home`: same XDG-config-home derivation as the filesystem role's `filesystem_xdg_config_home` (honors `$XDG_CONFIG_HOME`, default `{{ ansible_facts.env.HOME | default(ansible_facts.user_dir) + '/.config' }}`; uses `ansible_facts.env`, NOT the deprecated top-level `ansible_env` fact — F4 lock) — see Dev Notes "The `~/.config` vs XDG home decision"
  - [x] `symlinks_links`: list of `{name, target}` dicts mirroring `dotfiles/provisioning/symlinks.yaml` entries EXACTLY (see Dev Notes "Mirroring the locked manifest") — currently:
      - `{ name: nvim, target: nvim }`
      - `{ name: starship, target: starship }`
      - `{ name: wlogout, target: wlogout }`
      - `{ name: zsh, target: zsh }`
  - [x] NO hardcoded absolute paths; NO install_dir-derived values (this role consumes no install_dir — see Dev Notes "Why there is NO install_dir assert")
- [x] Create `src/provisioning/ansible/roles/symlinks/tasks/main.yml` (AC: 1-4)
  - [x] FIRST task: the fail-loud SOURCE-PRESENCE stat+assert pair (NOT the install_dir assert — see Dev Notes "Why there is NO install_dir assert"), ungated (sources are static repo content):
      - stat each `{{ symlinks_repo_root }}/dotfiles/config/{{ item.name }}` with `follow: true`, register `symlinks_source_check`
      - assert `symlinks_source_check.results | selectattr('stat.exists') | list | length == symlinks_links | length`, fail_msg naming the repo source dirs
  - [x] `Ensure XDG config home exists`: `ansible.builtin.file` `state: directory` on `{{ symlinks_xdg_config_home }}` (AC 2 — direct-run self-containment; file module does NOT create link-dest parents; ungated — natively check-safe; mirror 2.6/2.9 "Ensure ... dirs exist")
  - [x] Create symlinks: `ansible.builtin.file` `state: link`, `src: "{{ symlinks_repo_root }}/dotfiles/config/{{ item.name }}"` (ABSOLUTE path — relative srcs resolve relative to the link file), `dest: "{{ symlinks_xdg_config_home }}/{{ item.target }}"`, **`force: false`**, `loop: "{{ symlinks_links }}"` (AC 2, 3, 4 — see Dev Notes "file module `state: link` semantics"). NO `creates:`, NO `when: not ansible_check_mode` gate (native full check-mode support — verified)
  - [x] Resolve check stat+assert pair (AC 3, done-criterion 9 — see Dev Notes "The fail-loud layers"), BOTH gated `when: not ansible_check_mode`:
      - stat each `{{ symlinks_xdg_config_home }}/{{ item.target }}` with `follow: false`, register `symlinks_dest_check_link`; assert `... | selectattr('stat.islnk') | list | length == symlinks_links | length`
      - stat each dest with `follow: true`, register `symlinks_dest_check_resolved`; assert `... | selectattr('stat.exists') | list | length == symlinks_links | length` (a dangling link reports `exists: false` when followed)
  - [x] Header comment documenting the scope + the fail-loud contract (see Dev Notes "Scope")
  - [x] NO become/become_user anywhere (user-scoped role, mirror 2.5-2.9)
  - [x] NO hardcoded absolute paths (everything via `{{ symlinks_repo_root }}` and `{{ symlinks_xdg_config_home }}`)
- [x] Create `src/provisioning/ansible/playbooks/symlinks.yaml` (AC: 1)
  - [x] Open with the standard explanatory comment block (mirror `compositor-configs.yaml`): one-per-role playbook; user-scoped (NO become); distro-agnostic (NO group_by — role consumes no group_vars); why `gather_facts: true` is REQUIRED (vars derive from `ansible_facts.env.HOME`/`XDG_CONFIG_HOME`)
  - [x] `hosts: localhost`, `gather_facts: true`, `roles: [symlinks]`, NO become, NO group_by
- [x] Add structural real-file tests `src/provisioning/tests/unit/test_symlinks_role.py` (AC: 1-4)
  - [x] Role tree exists: `tasks/main.yml`, `vars/main.yml`
  - [x] Tasks parse to a list of named tasks
  - [x] First task is the fail-loud SOURCE stat (asserts `stat` on `dotfiles/config/`) — and explicitly NOT the install_dir assert
  - [x] Source stat+assert pair: both loop `symlinks_links`, assert on derived count (`selectattr('stat.exists') | list | length == symlinks_links | length`, no hardcoded literal)
  - [x] Symlink creation task: `ansible.builtin.file` with `state: link`, `src` prefixed `{{ symlinks_repo_root }}/dotfiles/config/`, `dest` prefixed `{{ symlinks_xdg_config_home }}/`, **`force: false`**, loop over `symlinks_links`, NO `creates:`, NOT check-gated (AC 2, 4 — the `force: false` assert locks AC 4's no-clobber contract)
  - [x] Resolve check pair: follow:false stat + assert `islnk`, follow:true stat + assert `exists`, all four tasks gated `when: not ansible_check_mode` (AC 3)
  - [x] XDG-home dir-ensure task: `state: directory`, ungated
  - [x] NO become/become_user anywhere
  - [x] No hardcoded absolute paths in module bodies (trim lock)
  - [x] vars test: required keys (`symlinks_repo_root`, `symlinks_xdg_config_home`, `symlinks_links`), `symlinks_repo_root` mirrors assets exactly, `symlinks_xdg_config_home` honors `$XDG_CONFIG_HOME` via `ansible_facts.env` + F4 lock (assert NO `{{ ansible_env.` present)
  - [x] **Parity test**: `symlinks_links` `(name, target)` pairs EXACTLY equal the parsed `dotfiles/provisioning/symlinks.yaml` `entries` (cli_tools-style set equality — see Dev Notes "Mirroring the locked manifest")
  - [x] Playbook test: parses, `hosts: localhost`, `gather_facts: true`, `roles: [symlinks]`, no become, no group_by
  - [x] `ansible-playbook --syntax-check` exits 0 (skip if ansible-playbook absent)
  - [x] **Runtime execution test** `test_playbook_executes_and_creates_symlinks`: temp `HOME` + `XDG_CONFIG_HOME`, run the real playbook with `ANSIBLE_CONFIG`, assert each `xdg/<target>` `os.path.islink` is True, `os.path.exists` is True (resolves), and `os.readlink` points at the real repo `dotfiles/config/<name>` (see Dev Notes "The runtime execution test")
- [x] Verify full suite + lint + layering guard (AC: 4)
  - [x] `uv run pytest` — full suite green, no regressions from the 355-pass baseline (Story 2.9 + review fixes)
  - [x] `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean (mypy baseline: 10 pre-existing errors in test_default_palette_role.py + test_cli_tools_role.py — new file must be clean)
  - [x] `python tests/architecture/test_layering.py` exits 0 (standalone nicety)
  - [x] `git status --short` shows ONLY the new role dir, playbook, and test file

## Dev Notes

### Scope — what Story 2.10 is and is not

**IS:** the `symlinks` Ansible role (FR-20): reads the DECLARATIVE manifest contract (`dotfiles/provisioning/symlinks.yaml`, locked in Story 2.1), mirrored into the role's vars, and creates one symlink per entry from repo `dotfiles/config/<name>` → `~/.config/<target>`. Plus its one-per-role playbook and a structural real-file test (incl. a parity lock and a runtime execution test).

**IS NOT:** the `compositor_configs` role (2.9 — it COPIES the hypr/hyprpaper/waybar skeletons+fragments; those dirs are deliberately NOT symlinked), the `settings` role (2.11), the `verify` role or aggregate `bootstrap.yaml` (2.12), or any Python hexagon change. Do NOT touch `dotfiles/provisioning/*.yaml` (five manifests LOCKED in Story 2.1 — the reader test `test_symlinks_manifest_lists_only_existing_dirs` forbids hypr/hyprpaper/waybar entries). Do NOT add any `.py` under `ansible/`. Do NOT modify the repo `dotfiles/config/` tree (plan §6: "existing dirs unchanged" — the role only reads it).

### The four entries, and why hypr/hyprpaper/waybar are NOT here

The manifest (and therefore `symlinks_links`) contains EXACTLY four entries — the only EXISTING config dirs, per plan §2: `nvim`, `starship`, `wlogout`, `zsh`. The hypr/hyprpaper/waybar skeletons are produced by Story 2.8 and PLACED BY COPY in Story 2.9 (`compositor_configs` role) — they are NOT symlinks. The `icon-template-color-scheme-mappings/` dir is an ASSET deployed to `<install>/icon-mappings/` (Story 2.6), NOT a symlink. Do NOT add any of these to `symlinks_links` — the parity test and the reader test both lock the set to the four. [Source: dotfiles/provisioning/symlinks.yaml, yaml_manifest_reader.py, 2-1-declarative-manifests.md, test_yaml_manifest_reader.py#215-236]

### Mirroring the locked manifest (Ansible does NOT read manifests)

Ansible roles do NOT read `dotfiles/provisioning/*.yaml` — each role mirrors its manifest into `vars/main.yml` and a structural parity test locks them together (single source of truth). For `symlinks_links`, the parity form is the cli_tools exact-match: `{tuple(e.items()) for e in symlinks_links} == {tuple(e.items()) for e in parsed_manifest_entries}` on `(name, target)`. The `name` field is the repo source dir under `dotfiles/config/`; `target` is the `~/.config/` component. Current data has `name == target` for all four — do NOT assume they must be equal, and do NOT assume they must differ. [Source: cli_tools/vars/main.yml, test_cli_tools_role.py#381, dotfiles/provisioning/symlinks.yaml]

### Where files live

```
src/provisioning/ansible/
├── playbooks/
│   └── symlinks.yaml                  ← NEW — one-per-role playbook (AC 1)
└── roles/
    └── symlinks/                      ← NEW (AC 1)
        ├── tasks/main.yml             ← NEW (AC 1-4)
        └── vars/main.yml              ← NEW
src/provisioning/tests/unit/
    └── test_symlinks_role.py          ← NEW — structural real-file tests
```

- Everything lives INSIDE the ansible scaffold. `symlinks_repo_root: "{{ playbook_dir }}/../../../.."` mirrors `assets_repo_root`/`compositor_configs_repo_root` exactly — from `playbooks/` up to the repo root (playbooks → ansible → provisioning → src → repo). [Source: assets/vars/main.yml#15-19]
- The repo source for each entry is `{{ symlinks_repo_root }}/dotfiles/config/<name>` (a DIRECTORY — the file module links it as-is; no trailing-`/`).
- The machine target is `{{ symlinks_xdg_config_home }}/<target>` (a path directly under the config home — the dir-ensure task only needs to create the config home itself).

### The `~/.config` vs XDG home decision

The ACs and FR-20 use `~/.config/...` shorthand. The filesystem role (2.5) already created the XDG config dirs via `filesystem_xdg_config_home`. This role must link to the SAME resolved location (the actual `~/.config` when `$XDG_CONFIG_HOME` is unset, the default). Therefore: **derive `symlinks_xdg_config_home` with the IDENTICAL `ansible_facts.env.XDG_CONFIG_HOME | default(ansible_facts.env.HOME | default(ansible_facts.user_dir) + '/.config', true)` expression the filesystem role uses** — do NOT hardcode `~/.config`. Use `ansible_facts.env`, NOT the deprecated top-level `ansible_env` fact (hard-breaks on ansible-core >= 2.24 — the repo-wide F4 lock). `gather_facts: true` on the playbook is REQUIRED for `ansible_facts.env` to be populated. [Sources: filesystem/vars/main.yml#23-31, 2-5 story file, 2-9 story file "The ~/.config vs XDG home decision"]

### Why there is NO install_dir assert

Every spine-touching role (2.5/2.6/2.7/2.9) opens with the verbatim `install_dir` seam assert. The `symlinks` role consumes NO install_dir — its sources are the static repo tree (`dotfiles/config/`) and its targets are under the XDG config home; nothing derives from `<install>` (unlike `cli_tools` and `packages`, which also correctly omit it). The FIRST task is instead the fail-loud **source-presence** stat+assert (prevents creating dangling links against a missing repo dir). Do NOT copy the install_dir assert into this role; do NOT alias install_dir into a var. [Source: cli_tools/tasks/main.yml, packages/tasks/main.yml]

### file module `state: link` semantics (verified empirically, ansible-core 2.20.3)

- `ansible.builtin.file` with `state: link` creates/updates the symlink at `dest` pointing at `src`. Natively idempotent: a correct re-run reports `ok`/`changed: false` — satisfies AC 4's "existing symlinks are left unchanged" for correct links (NFR-1: Ansible is the state authority).
- **`src` is an ABSOLUTE path to the repo source.** The module accepts a non-existing `src` (creating a DANGLING link silently) and relative `src` is resolved relative to the LINK FILE, not the playbook — so an absolute `{{ symlinks_repo_root }}/dotfiles/config/...` is mandatory. THIS is why the source-presence stat+assert precedes the create (the module will NOT fail on a missing source).
- **`force: false` is load-bearing (AC 3).** With `force: false` (the default) the module FAILS loudly instead of converting:
  - dest exists as a real DIRECTORY → `refusing to convert from directory to symlink` (verified)
  - dest exists as a real FILE → `refusing to convert from file to symlink` (verified)
  - a pre-existing symlink pointing at a DIFFERENT src IS replaced (create-or-change semantics — desired-state authority), self-healing stale/broken links rather than erroring.
  Do NOT set `force: true` — that would clobber a pre-existing regular file, violating AC 3's report-failures contract and NFR-8's spine containment. Do NOT add `creates:` — `state: link` is module-level idempotent.
- **Check-mode support is FULL** (verified: `--check` on a fresh target reports `changed` and writes nothing). The create task needs NO `when: not ansible_check_mode` gate — mirror the 2.9 dir-ensure discipline. [Source: ansible.builtin.file module docs; verified 2026-08-12 against ansible-core 2.20.3]

### The fail-loud layers (AC 3)

Three independent guards make "broken or missing targets reported as failures" concrete:

1. **Missing repo source** — source stat+assert (ungated, static content): if `dotfiles/config/<name>` is absent, abort BEFORE creating a dangling link, with a fail_msg naming the dir.
2. **Conflicting dest** — the `file` module with `force: false` fails loudly on a real dir/file at the dest (see above). Never silently clobber.
3. **Broken (dangling) or missing link after apply** — the resolve-check stat+assert pair (gated `when: not ansible_check_mode`, since dests are absent on a fresh target under `--check`). **stat semantics (verified): the stat module does NOT follow links by default — `follow` must be EXPLICIT.** With `follow: false` a dangling link reports `exists: true, islnk: true`; with `follow: true` a dangling link reports `exists: false`. Hence TWO stat loops:
   - `follow: false` → assert `selectattr('stat.islnk')` count == entries (proves it is a symlink, not a copy);
   - `follow: true` → assert `selectattr('stat.exists')` count == entries (proves it resolves — done-criterion 9).
   Both asserts use the derived `| length` count, NEVER a hardcoded literal. [Sources: done-criterion 9 (docs/01-dotfiles-provisioning-phase1-plan.md#248), 2.12 verify AC "symlinks resolved"; verified 2026-08-12]

### Check-mode / idempotency summary

| Task | Check-mode | Idempotency |
|---|---|---|
| Source stat+assert | ungated (static repo content; stat is read-only) | n/a |
| Ensure XDG config home (`file` directory) | safe (native) | native |
| Create symlinks (`file` link) | FULL support, no gate needed (verified) | `force: false` — correct links untouched; wrong links replaced; real dir/file fails |
| Resolve stat+assert (both loops) | GATED `not ansible_check_mode` (dests absent on fresh target under --check) | n/a |

### Playbook naming

Playbook filename `symlinks.yaml`; role dir `symlinks/`. This is single-word so there is NO underscore/hyphen asymmetry (unlike `compositor-configs.yaml` vs `compositor_configs`). **Note the name collision (intentional):** `dotfiles/provisioning/symlinks.yaml` is the declarative MANIFEST (2.1 lock); `src/provisioning/ansible/playbooks/symlinks.yaml` is this story's PLAYBOOK. The role reads the manifest's contract only through the mirrored `symlinks_links` var + parity test — it never opens the manifest at runtime. Do not confuse the two files. [Source: docs/01-dotfiles-provisioning-phase1-plan.md#154,194]

### The runtime execution test

Mirror 2.9's `test_playbook_executes_and_places_skeletons_and_fragments` (the 2026-08-12 review-finding regression guard — the structural tests alone could not catch silent no-ops): create `tempfile.TemporaryDirectory()`, `home`/`xdg`/subdirs, set `env["HOME"]`, `env["XDG_CONFIG_HOME"]`, `env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")`, run `ansible-playbook playbooks/symlinks.yaml`, assert for each manifest entry:
- `(xdg / target).is_symlink()` is True;
- `(xdg / target).exists()` is True (resolves — the repo source is real, so no dangling);
- `os.readlink(xdg / target)` resolves to the real `_REPO_ROOT / "dotfiles" / "config" / name`.
Because `symlinks_repo_root` derives from `playbook_dir`, the role links the REAL repo sources into the temp XDG home — no fixtures needed. Re-running the playbook must be a no-op (`changed: false` recap) to lock AC 4 at runtime. [Source: test_compositor_configs_role.py#470-523]

### Mirror-and-adapt discipline (Epic 1 retro action item)

This role mirrors several siblings. "What differs from each mirror":
- **2.5 filesystem** (XDG config home): 2.5 CREATES the config dirs; 2.10 LINKS INTO them. Share the exact XDG derivation (`ansible_facts.env`, F4 lock); do not duplicate logic with a different result.
- **2.9 compositor_configs** (dir-ensure + check-gating + runtime exec test): 2.9 COPIES files with `force: false` (transfer-only-if-absent); 2.10 LINKS with `force: false` (fail-on-conflict). 2.9's fragment source assert is check-gated because fragments are apply-time outputs; 2.10's SOURCE assert is ungated because repo content is static; 2.10's RESOLVE assert IS check-gated (dests absent under --check). Mirror 2.9's full `_TASK_KEYWORDS` set in the test helpers.
- **2.6/2.7** (install_dir assert, stat+assert pattern): 2.10 has NO install_dir assert (see above) but mirrors the stat+assert pair shape with derived counts.
- **cli_tools** (manifest parity): the exact `(name, target)` set-equality parity test.

### Deferred work / not re-opened here

- hypr/hyprpaper/waybar joining `symlinks.yaml`: Story 2.8's navigation note left "whether/how they join is 2.10's call" — the answer is NO: 2.9 owns them by COPY (FR-19), the reader test forbids adding them to the manifest, and done-criterion 7/9 both pass with the copy approach. Do not re-open.
- Install-spine symlinking (`<install>/*`): out of scope — 2.10 links ONLY repo `dotfiles/config/*` → `~/.config/*` (FR-20). NFR-8 spine containment: the role adds nothing else to the XDG config tree.

## Project Structure Notes

- `src/provisioning/ansible/roles/symlinks/tasks/main.yml` — NEW role tasks (source guard, XDG dir-ensure, link create, resolve guards).
- `src/provisioning/ansible/roles/symlinks/vars/main.yml` — NEW role vars (repo root, XDG home, `symlinks_links` mirror).
- `src/provisioning/ansible/playbooks/symlinks.yaml` — NEW one-per-role playbook (localhost, gather_facts, roles: [symlinks], no become, no group_by).
- `src/provisioning/tests/unit/test_symlinks_role.py` — NEW structural real-file tests (mirror `test_compositor_configs_role.py`).
- Consumed, NOT modified: `dotfiles/provisioning/symlinks.yaml` (2.1 lock), `dotfiles/config/{nvim,starship,wlogout,zsh}/` (2.8-era existing dirs), `src/provisioning/src/**` (Python hexagon untouched).
- No new dependencies. No Python outside the test file.

## Testing Requirements

- Full gates: `uv run pytest` (355-pass baseline from Story 2.9 + its review fixes — see Git Intelligence), `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src tests` (new file must be mypy-clean; 10 pre-existing baseline errors remain in test_default_palette_role.py/test_cli_tools_role.py — do NOT chase them), `python tests/architecture/test_layering.py` (standalone nicety).
- New `src/provisioning/tests/unit/test_symlinks_role.py` (see Tasks/Subtasks): copy the FULL helper suite verbatim from `test_compositor_configs_role.py` (`_find_ansible_dir()` walk-up resolver, `_TASK_KEYWORDS` (the extended set incl. block/rescue/delegate_to), `_module_key`/`_module`/`_module_text`/`_creates_value`, `_vars()`, `_tasks_with_module()`), plus the cli_tools-style `_manifest_entries()` reading `dotfiles/provisioning/symlinks.yaml`. Classes in order: `TestSymlinksRoleTree`, `TestSymlinksTasks`, `TestSymlinksVars`, `TestSymlinksPlaybook`. Assert:
  - role tree; tasks parse to named tasks
  - first task is the source stat (NOT the install_dir assert)
  - source stat+assert pair: both loop `symlinks_links`, `follow: true` on the stat, derived-count assert
  - link create task: `state: link`, `src` prefixed `{{ symlinks_repo_root }}/dotfiles/config/`, `dest` prefixed `{{ symlinks_xdg_config_home }}/`, **`force: false`** (locks AC 4 no-clobber), loop, NO `creates:`, NOT check-gated
  - resolve pair: `follow: false` + `islnk` assert, `follow: true` + `exists` assert, all gated `when: not ansible_check_mode`
  - XDG-home dir-ensure task: `state: directory`, ungated
  - no become; no hardcoded absolute paths (trim lock — scan vars too)
  - vars: required keys, repo_root mirror (exact string), XDG honors + F4 lock (no `{{ ansible_env.`), `symlinks_links` == manifest entries exactly
  - playbook: parses, localhost/gather_facts/roles, no become, no group_by; `--syntax-check` exit 0 (skip-if-absent)
  - runtime execution test (creates real symlinks into temp HOME/XDG; re-run is a no-op)
- Do NOT re-use a shared conftest for role tests — the duplicated-helper pattern is the accepted repo convention.

## Previous Story Intelligence

### Story 2.9 — Compositor Configs Role (DONE 2026-08-12, the immediate predecessor)
- Established the CURRENT canonical test suite to mirror: full helper set, extended `_TASK_KEYWORDS`, the runtime execution test (review finding 2026-08-12 — structural tests alone missed a silent copy no-op; the runtime test is now load-bearing). Mirror that discipline: THIS story's runtime test must prove symlinks actually land and resolve. [Source: 2-9-compositor-configs-role.md, test_compositor_configs_role.py]
- 2.9 COPIES hypr/hyprpaper/waybar skeletons + palette fragments into `~/.config/...` (FR-19). 2.10 must NOT link those dirs (manifest forbids; verify's symlink check requires every entry to resolve). The 2.9 role is the boundary: configs it owns are copies, configs in `symlinks.yaml` are links.
- 2.9's review-fix commit `fb0c979` is this story's baseline; the 355-pass suite is verified green (2026-08-12).

### Story 2.1 — Declarative Manifests (the manifest owner)
- Locked `dotfiles/provisioning/symlinks.yaml` with `kind: symlinks` / `entries: [{name, target}]`. Reader schema: required `{name, target}`, allowed `+version`. The reader test asserts names == `{nvim, starship, wlogout, zsh}` and forbids hypr/hyprpaper/waybar. This story's `symlinks_links` must mirror EXACTLY (parity test). [Sources: 2-1-declarative-manifests.md#152-159, dotfiles/provisioning/symlinks.yaml, yaml_manifest_reader.py#37-39, test_yaml_manifest_reader.py#215-236,332]

### Story 2.5 — Filesystem Role (the dir creator)
- Created the XDG config home + dirs via `filesystem_xdg_config_home` (honors `$XDG_CONFIG_HOME`, default `{{ ansible_facts.env.HOME }}/.config`, `ansible_facts.env` NOT `ansible_env`). This role links INTO that home — use the identical derivation. [Source: filesystem/vars/main.yml#23-31]

### Story 2.2 — Ansible Scaffold
- The scaffold (inventory, ansible.cfg, requirements.yml) is already in place; `symlinks` adds only a role dir, a playbook, and a test file — no inventory/config changes.

### Epic 1 retrospective (2026-08-08) — action item touching this story
- "Mirror-and-adapt discipline": explicit "what differs from the mirror" checklist (addressed in Dev Notes).

## Git Intelligence

- Baseline: `fb0c979` (`fix: apply code review findings for story 2.9 compositor configs role`, 2026-08-12). Working tree is CLEAN. 355 tests pass at baseline (verified 2026-08-12).
- Commit flow pattern (follow it): `chore: create story 2.10 symlinks role` (this story) → `feat: implement story 2.10 ...` → `fix: apply ... code review findings` → `chore: mark story 2.10 ... done`. Recent history: 2.9 (`dff7a6d`/`fb0c979`), 2.8 (`59f293e`/`5577a71`), 2.7 (`8d8a3b8`/`8a371c1`).
- This story adds ONLY: `src/provisioning/ansible/roles/symlinks/**`, `src/provisioning/ansible/playbooks/symlinks.yaml`, `src/provisioning/tests/unit/test_symlinks_role.py`. Verify with `git status --short` that nothing else moved.

## Latest Tech Information

- ansible-core **2.20.3** is the installed/runtime version (verified 2026-08-12 via `uv run ansible --version`); pyproject requires `ansible-core>=2.16`. Collections: community.general, ansible.posix, kewlfft.aur (pinned in requirements.yml). No new collections needed — `ansible.builtin.file`/`stat`/`assert` are core.
- `ansible.builtin.file` `state: link` (verified 2026-08-12): check_mode FULL support (predicts changed, writes nothing); `src` accepts a non-existing path → source guard required; relative `src` resolves relative to the link file → use absolute; `force: false` (default) fails loudly on a real dir/file dest (`refusing to convert...`) and replaces a mismatched symlink; re-run of a correct link reports `changed: false`. [Source: ansible.builtin.file module docs; empirical verification]
- **stat follow trap (verified 2026-08-12):** the stat module does NOT resolve symlinks by default in ansible-core 2.20.3 — `follow` must be explicit. `follow: false` on a dangling link → `exists: true, islnk: true`; `follow: true` on a dangling link → `exists: false`. The resolve-check MUST pass `follow` explicitly on every stat task.
- F4 lock (repo-wide): read env via `ansible_facts.env`, never the deprecated top-level `ansible_env` fact (INJECT_FACTS_AS_VARS hard-breaks on ansible-core >= 2.24).
- `gather_facts: true` is REQUIRED on the playbook (vars derive from `ansible_facts.env.HOME`/`XDG_CONFIG_HOME`).

## References

- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#433-445] — Story 2.10 ACs (symlinks role)
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#41] — FR-20 Symlinks Role
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#24,475] — FR-3 / FR-22 (verify asserts "symlinks resolved" among done-criteria)
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#50] — NFR-1 idempotency (Ansible is the state authority)
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#57] — NFR-8 spine containment
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#194] — plan §6: `symlinks.yaml` manifest (repo `dotfiles/config/*` → `~/.config/*`)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#154,164] — plan §6: `symlinks.yaml` playbook + `roles/symlinks/` tree
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#248] — done-criterion 9 (every symlink entry resolves to a real file)
- [Source: dotfiles/provisioning/symlinks.yaml] — the locked manifest (4 entries; header forbids hypr/hyprpaper/waybar)
- [Source: src/provisioning/src/provisioning/adapters/yaml_manifest_reader.py#37-39] — symlinks entry schema (required `name`+`target`)
- [Source: src/provisioning/src/provisioning/domain/enums.py#74] — `ManifestKind.SYMLINKS = "symlinks"`
- [Source: src/provisioning/ansible/roles/filesystem/vars/main.yml#23-31] — `filesystem_xdg_config_home` derivation to mirror as `symlinks_xdg_config_home`
- [Source: src/provisioning/ansible/roles/assets/vars/main.yml#15-19] — `assets_repo_root` derivation to mirror as `symlinks_repo_root`
- [Source: src/provisioning/ansible/roles/cli_tools/vars/main.yml + test_cli_tools_role.py#381] — the exact-match parity-test pattern to mirror
- [Source: src/provisioning/tests/unit/test_compositor_configs_role.py] — the full helper suite + runtime execution test pattern to mirror
- [Source: src/provisioning/ansible/playbooks/compositor-configs.yaml] — the playbook template (localhost, gather_facts, roles, no become, no group_by)
- [Source: _bmad-output/implementation-artifacts/2-9-compositor-configs-role.md] — previous story (copy-vs-link boundary; runtime exec test; review-fix baseline)
- [Source: _bmad-output/implementation-artifacts/2-1-declarative-manifests.md#152-175] — symlinks.yaml format + the icon-template-color-scheme-mappings NOT-a-symlink note
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml#75] — story 2-10-symlinks-role status (backlog → ready-for-dev this run)

## Dev Agent Record

### Agent Model Used

opencode (deepseek-v4-flash)

### Debug Log References

- Baseline `fb0c979` is the 2.9 review-fix commit; working tree clean; 355 tests pass.
- Ansible behaviors verified empirically 2026-08-12 against ansible-core 2.20.3 (see Latest Tech Information): `file` `state: link` check-mode + force-false conflict failures; the stat module's follow-flag default trap (dangling links report `exists: true` under follow:false, `exists: false` under follow:true).
- Pre-existing mypy baseline: `uv run mypy src tests` reports 10 errors in `tests/unit/test_default_palette_role.py` and `tests/unit/test_cli_tools_role.py` — present at baseline, NOT introduced by this story. The new `test_symlinks_role.py` must be mypy-clean.

### Completion Notes List

- Created Story 2.10 Symlinks Role context: `symlinks` role (source guard + dir-ensure + link create + resolve guards), `symlinks.yaml` playbook, structural + parity + runtime tests.
- Locked the manifest mirror: `symlinks_links` = the four `{name, target}` pairs from `dotfiles/provisioning/symlinks.yaml`; parity test enforces exact equality.
- Locked NO-install_dir-assert: this role consumes no install_dir; the first task is the fail-loud source stat+assert instead.
- Locked the stat follow trap: resolve checks MUST pass `follow: false` (islnk) and `follow: true` (exists) explicitly — the module default does not resolve links.
- Locked `force: false` on the link task (AC 4 no-clobber; fail-loud on real dir/file dests — verified error messages).
- Scope guards: no manifest edits (2.1 lock), no hypr/hyprpaper/waybar in `symlinks_links`, no install-spine linking (NFR-8), no Python hexagon changes.
- Status → ready-for-dev.
- Implemented Story 2.10 (2026-08-12): created `symlinks` role (vars mirror of the locked manifest + tasks: ungated source stat+assert, XDG dir-ensure, `state: link` `force: false` create, gated resolve stat+assert pair), `playbooks/symlinks.yaml`, and `test_symlinks_role.py` (18 tests: tree, tasks contract, source pair, link contract, resolve pair, vars + parity, playbook, syntax-check, runtime execution + idempotency).
- Runtime execution test verifies real symlinks land in temp HOME/XDG, resolve, point at the real repo source, and re-run is a no-op (`changed=0`).
- Full suite 355 → 373 passed; ruff check/format clean; mypy clean for the new file (10 pre-existing baseline errors in test_default_palette_role.py/test_cli_tools_role.py untouched); layering guard OK.
- Status → review.

### File List

- `src/provisioning/ansible/roles/symlinks/tasks/main.yml` (NEW)
- `src/provisioning/ansible/roles/symlinks/vars/main.yml` (NEW)
- `src/provisioning/ansible/playbooks/symlinks.yaml` (NEW)
- `src/provisioning/tests/unit/test_symlinks_role.py` (NEW)
- `_bmad-output/implementation-artifacts/2-10-symlinks-role.md` (this story)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (status update)
