---
baseline_commit: fb0c979
---

# Story 2.10: Config Copies Role

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Change Log

- 2026-08-12: Story created — ultimate context engine analysis completed; comprehensive developer guide created (FR-20).
- 2026-08-12: Story implemented — `symlinks` role + playbook + 18 structural/parity/runtime tests; suite 355 → 373 green.
- 2026-08-12: **PIVOT (code review finding, decision)** — runtime independence: configs are now COPIED, not symlinked. Nothing in the repo is referenced at runtime, so the machine keeps working after the repo is deleted. The role/manifest/playbook/tests were renamed `symlinks` → `config_copies` / `config-copies` and rewritten for copy semantics (mirror of 2.9 compositor_configs). Manifest `kind` became `config-copies`; reader enum/schema/tests updated; done-criterion 9 + epic FR-20/2.12 updated. All four patch findings from the code review were folded into the pivot.

## Story

As an operator,
I want a `config_copies` role that copies repo configs into `~/.config/`,
So that my configs live in the repo as the SOURCE and the machine works after the repo is deleted (runtime independence).

## Acceptance Criteria

1. `roles/config_copies/` role exists with `tasks/main.yml` (AC 1, FR-20)
2. Every entry in `dotfiles/provisioning/config-copies.yaml` is copied from repo `dotfiles/config/*` to `~/.config/*` as a REAL directory — NOT a symlink (nothing in the repo is referenced at runtime; the machine works after the repo is deleted) (AC 2, FR-20, pivot 2026-08-12)
3. Broken, missing, or non-directory sources/targets are reported as failures (AC 3)
4. Re-runs are idempotent — unchanged configs are left alone (AC 4, FR-20, NFR-1)

## Tasks / Subtasks

- [x] Rename pivot artifacts: `dotfiles/provisioning/symlinks.yaml` → `config-copies.yaml` (`kind: config-copies`), role `symlinks/` → `config_copies/`, playbook `symlinks.yaml` → `config-copies.yaml`, test `test_symlinks_role.py` → `test_config_copies_role.py`, story `2-10-symlinks-role.md` → `2-10-config-copies-role.md` (pivot 2026-08-12)
- [x] Update the manifest schema contract: `ManifestKind.SYMLINKS` → `ManifestKind.CONFIG_COPIES = "config-copies"` in `domain/enums.py`, entry schema `({name, target, version}, {name, target})` keyed by `CONFIG_COPIES` in `yaml_manifest_reader.py`, and the reader/domain tests (`test_yaml_manifest_reader.py` symlinks tests → config-copies, `test_domain.py` member assert) (pivot 2026-08-12)
- [x] Create `src/provisioning/ansible/roles/config_copies/vars/main.yml` (AC: 1-4)
  - [x] Open with the standard header comment: `# Config copies role vars (Story 2.10, pivot 2026-08-12).` + role-description + `# Mirror-and-adapt discipline (Epic 1 retro action item)` block itemizing what differs from each mirror (mirror `compositor_configs/vars/main.yml` header shape)
  - [x] `config_copies_repo_root`: `{{ playbook_dir }}/../../../..` (mirror `assets_repo_root`/`compositor_configs_repo_root` exactly — see Dev Notes "Where files live")
  - [x] `config_copies_xdg_config_home`: same XDG-config-home derivation as the filesystem role's `filesystem_xdg_config_home` (honors `$XDG_CONFIG_HOME`, default `{{ ansible_facts.env.HOME | default(ansible_facts.user_dir) + '/.config' }}`; uses `ansible_facts.env`, NOT the deprecated top-level `ansible_env` fact — F4 lock) — see Dev Notes "The `~/.config` vs XDG home decision"
  - [x] `config_copies_entries`: list of `{name, target}` dicts mirroring `dotfiles/provisioning/config-copies.yaml` entries EXACTLY (see Dev Notes "Mirroring the locked manifest") — currently:
      - `{ name: nvim, target: nvim }`
      - `{ name: starship, target: starship }`
      - `{ name: wlogout, target: wlogout }`
      - `{ name: zsh, target: zsh }`
  - [x] NO hardcoded absolute paths; NO install_dir-derived values (this role consumes no install_dir — see Dev Notes "Why there is NO install_dir assert")
- [x] Create `src/provisioning/ansible/roles/config_copies/tasks/main.yml` (AC: 1-4)
  - [x] FIRST task: the fail-loud FACT-GATHERING assert (`ansible_facts.env.HOME is defined`, fail_msg naming `gather_facts: true`) — replaces the install_dir assert position (see Dev Notes "Why there is NO install_dir assert" + review patch: without it a `gather_facts: false` run dies with an opaque traceback)
  - [x] Non-empty guard: assert `config_copies_entries | length > 0` (review patch: all count asserts derive from `| length`, so an empty list would vacuously pass `0 == 0` and silently disable the role)
  - [x] Fail-loud SOURCE-presence stat+assert pair, ungated (sources are static repo content):
      - stat each `{{ config_copies_repo_root }}/dotfiles/config/{{ item.name }}` with `follow: true`, register `config_copies_source_check`
      - assert `... | selectattr('stat.exists') | selectattr('stat.isdir') | list | length == config_copies_entries | length` (review patch: checks `stat.isdir` so a regular file at a source path fails loudly, not silently copied), fail_msg naming the repo source dirs
  - [x] `Ensure XDG config home exists`: `ansible.builtin.file` `state: directory` on `{{ config_copies_xdg_config_home }}` (AC 2 — direct-run self-containment; ungated — natively check-safe; mirror 2.6/2.9 "Ensure ... dirs exist")
  - [x] `Ensure target config dirs exist`: `ansible.builtin.file` `state: directory` loop on `{{ config_copies_xdg_config_home }}/{{ item.target }}` (copy does NOT create the top-level dest parent; ungated — check-safe)
  - [x] Copy configs: `ansible.builtin.copy`, `src: "{{ config_copies_repo_root }}/dotfiles/config/{{ item.name }}/"` (trailing-`/` = contents-into-dest), `dest: "{{ config_copies_xdg_config_home }}/{{ item.target }}/"`, `remote_src: true`, default `force: true`, `loop: "{{ config_copies_entries }}"` (AC 2, 3, 4 — see Dev Notes "copy module semantics"). NO `creates:`, NO `when: not ansible_check_mode` gate (full check-mode support — verified). NOT `force: false` (directory src + force: false + pre-existing dest dir is a SILENT NO-OP — 2.9 review finding)
  - [x] Resolve stat+assert pair (AC 3, done-criterion 9 — see Dev Notes "The fail-loud layers"), BOTH gated `when: not ansible_check_mode`:
      - stat each `{{ config_copies_xdg_config_home }}/{{ item.target }}` with `follow: false`, register `config_copies_dest_check`; assert `... | selectattr('stat.isdir') | list | length == config_copies_entries | length` — `follow: false` makes a symlink report `islnk: true / isdir: false`, so the assert proves every dest is a REAL directory (runtime independence: not a copy, not a link back into the repo)
  - [x] Header comment documenting the scope + the fail-loud contract + the runtime-independence pivot (see Dev Notes "Scope")
  - [x] NO become/become_user anywhere (user-scoped role, mirror 2.5-2.9)
  - [x] NO hardcoded absolute paths (everything via `{{ config_copies_repo_root }}` and `{{ config_copies_xdg_config_home }}`)
- [x] Create `src/provisioning/ansible/playbooks/config-copies.yaml` (AC: 1)
  - [x] Open with the standard explanatory comment block (mirror `compositor-configs.yaml`): one-per-role playbook; user-scoped (NO become); distro-agnostic (NO group_by — role consumes no group_vars); why `gather_facts: true` is REQUIRED (vars derive from `ansible_facts.env.HOME`/`XDG_CONFIG_HOME`); the runtime-independence pivot note
  - [x] `hosts: localhost`, `gather_facts: true`, `roles: [config_copies]`, NO become, NO group_by
- [x] Add structural real-file tests `src/provisioning/tests/unit/test_config_copies_role.py` (AC: 1-4)
  - [x] Role tree exists: `tasks/main.yml`, `vars/main.yml`
  - [x] Tasks parse to a list of named tasks
  - [x] First task is the fail-loud FACT-GATHERING assert (asserts `ansible_facts.env.HOME is defined`, fail_msg names `gather_facts`) — and explicitly NOT the install_dir assert
  - [x] Non-empty guard assert on `config_copies_entries | length > 0`, ungated
  - [x] Source stat+assert pair: both loop `config_copies_entries`, `follow: true` on the stat, assert on derived count incl. `stat.isdir` (`selectattr('stat.exists') | selectattr('stat.isdir') | list | length == config_copies_entries | length`, no hardcoded literal), both ungated
  - [x] Copy task: `ansible.builtin.copy`, `src` prefixed `{{ config_copies_repo_root }}/dotfiles/config/` AND ending in `/`, `dest` prefixed `{{ config_copies_xdg_config_home }}/` AND ending in `/`, `remote_src: true`, NOT `force: false` (locks the no-silent-no-op contract), loop over `config_copies_entries`, NO `creates:`, NOT check-gated
  - [x] Resolve stat+assert pair: ONE stat loop `follow: false` + assert `stat.isdir`, both gated `when: not ansible_check_mode` (proves real dirs, not symlinks — runtime independence)
  - [x] Dir-ensure tasks: XDG-home dir-ensure + per-target dir-ensure, both ungated
  - [x] NO become/become_user anywhere
  - [x] No hardcoded absolute paths in module bodies (trim lock)
  - [x] vars test: required keys (`config_copies_repo_root`, `config_copies_xdg_config_home`, `config_copies_entries`), `config_copies_repo_root` mirrors assets exactly, `config_copies_xdg_config_home` honors `$XDG_CONFIG_HOME` via `ansible_facts.env` + F4 lock (assert NO `{{ ansible_env.` present)
  - [x] **Parity test**: `config_copies_entries` `(name, target)` pairs EXACTLY equal the parsed `dotfiles/provisioning/config-copies.yaml` `entries` (cli_tools-style set equality — see Dev Notes "Mirroring the locked manifest")
  - [x] Playbook test: parses, `hosts: localhost`, `gather_facts: true`, `roles: [config_copies]`, no become, no group_by
  - [x] `ansible-playbook --syntax-check` exits 0 (skip if ansible-playbook absent)
  - [x] **Runtime execution test** `test_playbook_executes_and_creates_config_copies`: temp `HOME` + `XDG_CONFIG_HOME`, run the real playbook with `ANSIBLE_CONFIG`, assert each `xdg/<target>` `is_dir()` is True, `is_symlink()` is False (runtime independence), and `os.listdir(xdg/<target>) == os.listdir(repo dotfiles/config/<name>)` (contents landed); re-run reports `changed=0` (see Dev Notes "The runtime execution test")
- [x] Verify full suite + lint + layering guard (AC: 4)
  - [x] `uv run pytest` — full suite green, no regressions from the 355-pass baseline (Story 2.9 + review fixes)
  - [x] `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean (mypy baseline: 10 pre-existing errors in test_default_palette_role.py + test_cli_tools_role.py — new file must be clean)
  - [x] `python tests/architecture/test_layering.py` exits 0 (standalone nicety)
  - [x] `git status --short` shows ONLY the renamed role dir, playbook, test file, manifest, and story/status artifacts

### Review Findings

- [x] [Review][Decision] **Resolved by pivot (2026-08-12):** nvim lazy.nvim runtime writes would dirty the git worktree — resolved by copying, not symlinking: nothing in the repo is referenced at runtime. `dotfiles/config/nvim` remains the static SOURCE; `~/.config/nvim` is a real copy and `lazy-lock.json` lives only on the machine. [src/provisioning/ansible/roles/config_copies/tasks/main.yml]
- [x] [Review][Patch] Source-presence guard now checks `stat.exists` AND `stat.isdir` — a regular file at a source path fails loudly (copy roles never silently copy a file where a dir is expected) [src/provisioning/ansible/roles/config_copies/tasks/main.yml]
- [x] [Review][Patch] Empty `config_copies_entries` now guarded by a non-empty assert — a manifest desync / runtime override fails loudly instead of vacuous `0 == 0` passes [src/provisioning/ansible/roles/config_copies/tasks/main.yml]
- [x] [Review][Patch] `gather_facts` is now a fail-loud FIRST-task assert — an opaque `user_dir` traceback is replaced by a friendly message naming the requirement [src/provisioning/ansible/roles/config_copies/tasks/main.yml]
- [x] [Review][Patch] `fail_msg`s no longer hardcode the entry names ("nvim, starship, wlogout, zsh") — they name the manifest generically, so the messages cannot drift from the manifest [src/provisioning/ansible/roles/config_copies/tasks/main.yml]
- [x] [Review][Defer] `config_copies_repo_root: "{{ playbook_dir }}/../../../.."` resolves against the *calling* playbook's dir — a 2.12 aggregator at a different depth than `playbooks/` would silently mis-resolve or fail misleadingly; shared pattern across assets/compositor_configs [src/provisioning/ansible/roles/config_copies/vars/main.yml:28] — deferred, pre-existing
- [x] [Review][Defer] Live-playbook tests `pytest.skip` when `ansible-playbook` is absent and `assert "changed=0" in second.stdout` is brittle across ansible-core recap formats — suite can be green with runtime behavior unverified [src/provisioning/tests/unit/test_config_copies_role.py] — deferred, CI robustness
- [x] [Review][Defer] Nested `name`/`target` manifest entries would fail with an opaque ENOENT (no dest parent creation; only the config home + target dirs are ensured) — latent; manifest is locked flat [src/provisioning/ansible/roles/config_copies/tasks/main.yml] — deferred, not actionable now
- [x] [Review][Defer] Relative `XDG_CONFIG_HOME` accepted unvalidated — shared spec-mandated derivation with the filesystem role; any fix belongs to both roles [src/provisioning/ansible/roles/config_copies/vars/main.yml:46] — deferred, pre-existing pattern

## Dev Notes

### Scope — what Story 2.10 is and is not

**IS:** the `config_copies` Ansible role (FR-20): reads the DECLARATIVE manifest contract (`dotfiles/provisioning/config-copies.yaml`, `kind: config-copies`, Story 2.1), mirrored into the role's vars, and copies each entry from repo `dotfiles/config/<name>` → `~/.config/<target>` as a REAL directory. Plus its one-per-role playbook and a structural real-file test (incl. a parity lock and a runtime execution test).

**IS NOT:** the `compositor_configs` role (2.9 — it COPIES the hypr/hyprpaper/waybar skeletons+fragments per-FILE), the `settings` role (2.11), the `verify` role or aggregate `bootstrap.yaml` (2.12), or any Python hexagon change beyond the manifest enum/schema rename. Do NOT touch `dotfiles/provisioning/*.yaml` (five manifests LOCKED in Story 2.1 — the reader test `test_config_copies_manifest_lists_only_existing_dirs` forbids hypr/hyprpaper/waybar entries). Do NOT add any `.py` under `ansible/`. Do NOT modify the repo `dotfiles/config/` tree (plan §6: "existing dirs unchanged" — the role only reads it).

### The pivot — runtime independence (2026-08-12 code review decision)

The original spec linked configs (FR-20 "symlinks role"). A code-review decision escalated the requirement: **nothing in the repo may be used at runtime — configs must be copied, and the machine must work after deleting the repo.** Symlinking `~/.config/nvim` into the git-tracked tree also coupled nvim's runtime writes (`lazy-lock.json`) into the worktree. The pivot therefore converts Story 2.10 from symlinks to copies, mirroring the 2.9 compositor_configs discipline:

- `~/.config/<target>` is a REAL directory (proven by the resolve stat with `follow: false` + `stat.isdir` assert — a symlink reports `islnk: true / isdir: false`).
- The repo is only ever the SOURCE for a provision run; nothing in the repo is referenced at runtime.
- The copy uses the default `force: true` (Ansible is the state authority, NFR-1): unchanged content reports `ok`/`changed: false` (checksum idempotency); a changed repo source propagates on the next apply. NOT `force: false` — a directory `src` + `force: false` + a pre-existing dest dir is a SILENT NO-OP (2.9 review finding 2026-08-12).

### The four entries, and why hypr/hyprpaper/waybar are NOT here

The manifest (and therefore `config_copies_entries`) contains EXACTLY four entries — the only EXISTING config dirs, per plan §2: `nvim`, `starship`, `wlogout`, `zsh`. The hypr/hyprpaper/waybar skeletons are produced by Story 2.8 and PLACED BY COPY in Story 2.9 (`compositor_configs` role) — they are not entries here. The `icon-template-color-scheme-mappings/` dir is an ASSET deployed to `<install>/icon-mappings/` (Story 2.6). Do NOT add any of these to `config_copies_entries` — the parity test and the reader test both lock the set to the four. [Source: dotfiles/provisioning/config-copies.yaml, yaml_manifest_reader.py, 2-1-declarative-manifests.md, test_yaml_manifest_reader.py]

### Mirroring the locked manifest (Ansible does NOT read manifests)

Ansible roles do NOT read `dotfiles/provisioning/*.yaml` — each role mirrors its manifest into `vars/main.yml` and a structural parity test locks them together (single source of truth). For `config_copies_entries`, the parity form is the cli_tools exact-match: `{tuple(e.items()) for e in config_copies_entries} == {tuple(e.items()) for e in parsed_manifest_entries}` on `(name, target)`. The `name` field is the repo source dir under `dotfiles/config/`; `target` is the `~/.config/` component. Current data has `name == target` for all four — do NOT assume they must be equal, and do NOT assume they must differ. [Source: cli_tools/vars/main.yml, test_cli_tools_role.py#381, dotfiles/provisioning/config-copies.yaml]

### Where files live

```
src/provisioning/ansible/
├── playbooks/
│   └── config-copies.yaml              ← NEW — one-per-role playbook (AC 1)
└── roles/
    └── config_copies/                  ← NEW (AC 1)
        ├── tasks/main.yml              ← NEW (AC 1-4)
        └── vars/main.yml               ← NEW
src/provisioning/tests/unit/
    └── test_config_copies_role.py      ← NEW — structural real-file tests
dotfiles/provisioning/
    └── config-copies.yaml              ← RENAMED from symlinks.yaml (kind: config-copies)
```

- Everything lives INSIDE the ansible scaffold. `config_copies_repo_root: "{{ playbook_dir }}/../../../.."` mirrors `assets_repo_root`/`compositor_configs_repo_root` exactly — from `playbooks/` up to the repo root (playbooks → ansible → provisioning → src → repo). [Source: assets/vars/main.yml#15-19]
- The repo source for each entry is `{{ config_copies_repo_root }}/dotfiles/config/<name>/` (a DIRECTORY — the copy uses a trailing-`/` src for contents-into-dest semantics, so `~/.config/<target>/` gets the directory's contents, not a nested `target/<name>/`).
- The machine target is `{{ config_copies_xdg_config_home }}/<target>/` (a path directly under the config home — the dir-ensure tasks only need to create the config home itself and each target dir).

### The `~/.config` vs XDG home decision

The ACs and FR-20 use `~/.config/...` shorthand. The filesystem role (2.5) already created the XDG config dirs via `filesystem_xdg_config_home`. This role must copy to the SAME resolved location (the actual `~/.config` when `$XDG_CONFIG_HOME` is unset, the default). Therefore: **derive `config_copies_xdg_config_home` with the IDENTICAL `ansible_facts.env.XDG_CONFIG_HOME | default(ansible_facts.env.HOME | default(ansible_facts.user_dir) + '/.config', true)` expression the filesystem role uses** — do NOT hardcode `~/.config`. Use `ansible_facts.env`, NOT the deprecated top-level `ansible_env` fact (hard-breaks on ansible-core >= 2.24 — the repo-wide F4 lock). `gather_facts: true` on the playbook is REQUIRED for `ansible_facts.env` to be populated — and the FIRST task asserts that loudly (review patch).

### Why there is NO install_dir assert

Every spine-touching role (2.5/2.6/2.7/2.9) opens with the verbatim `install_dir` seam assert. The `config_copies` role consumes NO install_dir — its sources are the static repo tree (`dotfiles/config/`) and its targets are under the XDG config home; nothing derives from `<install>` (unlike `cli_tools` and `packages`, which also correctly omit it). The FIRST task is instead the fail-loud **fact-gathering** assert (vars derive from `ansible_facts.env`), followed by the fail-loud **source-presence** stat+assert (prevents copying against a missing repo dir). Do NOT copy the install_dir assert into this role; do NOT alias install_dir into a var. [Source: cli_tools/tasks/main.yml, packages/tasks/main.yml]

### copy module semantics (verified empirically, ansible-core 2.20.3)

- `ansible.builtin.copy` with a DIRECTORY `src` ending in `/` copies the contents into `dest/` recursively (nested dirs incl. hidden files). Natively idempotent via checksums: unchanged content reports `ok`/`changed: false` — satisfies AC 4 and NFR-1 (Ansible is the state authority).
- **`force: false` is FORBIDDEN here:** with a directory `src` + `force: false` + a pre-existing dest dir the module silently no-ops (nothing is ever placed) — the 2.9 review finding 2026-08-12. The default `force: true` is what makes the copy actually land; idempotency comes from checksums, not from force.
- The `copy` module FAILS loudly on a missing/unreadable source — this is a secondary fail-loud guard behind the source stat+assert.
- **`remote_src: true`:** the repo is local; on localhost `src` is on the target machine (mirror of the assets role's directory copies).
- **Check-mode support is FULL** (verified: `--check` predicts `changed` and writes nothing). The copy task needs NO `when: not ansible_check_mode` gate. The RESOLVE stat+assert pair IS gated (dests are absent on a fresh target under --check).
- **copy does NOT create the top-level dest parent** — the config home + target dirs are re-ensured first (mirror of the 2.6/2.9 "Ensure ... dirs exist" pattern) so a direct config-copies.yaml run is self-contained.

### The fail-loud layers (AC 3 + runtime independence)

Three independent guards make "broken or missing targets reported as failures" and "real dirs, not repo references" concrete:

1. **Missing/non-directory repo source** — source stat+assert (ungated, static content): if `dotfiles/config/<name>` is absent OR a regular file, abort BEFORE copying, with a fail_msg naming the dirs. Checks `stat.isdir` explicitly (review patch).
2. **Unreadable/missing source at copy time** — the `copy` module fails loudly (secondary guard).
3. **Missing, non-directory, or SYMLINK dest after apply** — the resolve stat+assert pair (gated `when: not ansible_check_mode`). The stat uses `follow: false` and asserts `stat.isdir`: a real copied directory reports `isdir: true`; a symlink (e.g. an accidentally restored link back into the repo) reports `islnk: true / isdir: false` — the runtime-independence guarantee is that every dest is a REAL directory. The assert uses the derived `| length` count, NEVER a hardcoded literal. [Sources: done-criterion 9 (docs/01-dotfiles-provisioning-phase1-plan.md#248), 2.12 verify AC "config copies present"; verified 2026-08-12]

### Check-mode / idempotency summary

| Task | Check-mode | Idempotency |
|---|---|---|
| Fact-gathering assert | ungated (pure assert) | n/a |
| Non-empty guard | ungated (pure assert) | n/a |
| Source stat+assert | ungated (static repo content; stat is read-only) | n/a |
| Ensure XDG config home + target dirs (`file` directory) | safe (native) | native |
| Copy configs (`copy` directory) | FULL support, no gate needed (verified) | checksum idempotent — unchanged content reports `changed: false`; NOT force: false (silent no-op trap) |
| Resolve stat+assert | GATED `not ansible_check_mode` (dests absent on fresh target under --check) | n/a |

### Playbook naming

Playbook filename `config-copies.yaml`; role dir `config_copies/`. This is the SAME underscore/hyphen asymmetry as `compositor-configs.yaml` vs `compositor_configs` (the repo convention). **Note the name collision (intentional):** `dotfiles/provisioning/config-copies.yaml` is the declarative MANIFEST (2.1 lock); `src/provisioning/ansible/playbooks/config-copies.yaml` is this story's PLAYBOOK. The role reads the manifest's contract only through the mirrored `config_copies_entries` var + parity test — it never opens the manifest at runtime. Do not confuse the two files. [Source: docs/01-dotfiles-provisioning-phase1-plan.md#154,194]

### The runtime execution test

Mirror 2.9's `test_playbook_executes_and_places_skeletons_and_fragments` (the 2026-08-12 review-finding regression guard — the structural tests alone could not catch silent no-ops): create `tempfile.TemporaryDirectory()`, `home`/`xdg`, set `env["HOME"]`, `env["XDG_CONFIG_HOME"]`, `env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")`, run `ansible-playbook playbooks/config-copies.yaml`, assert for each manifest entry:
- `(xdg / target).is_dir()` is True;
- `(xdg / target).is_symlink()` is False (runtime independence — NOT a repo reference);
- `set(os.listdir(xdg / target)) == set(os.listdir(_REPO_ROOT / "dotfiles" / "config" / name))` (contents landed).
Because `config_copies_repo_root` derives from `playbook_dir`, the role copies the REAL repo sources into the temp XDG home — no fixtures needed. Re-running the playbook must be a no-op (`changed=0` recap) to lock AC 4 at runtime. [Source: test_compositor_configs_role.py#470-523]

### Mirror-and-adapt discipline (Epic 1 retro action item)

This role mirrors several siblings. "What differs from each mirror":
- **2.5 filesystem** (XDG config home): 2.5 CREATES the config dirs; 2.10 COPIES INTO them. Share the exact XDG derivation (`ansible_facts.env`, F4 lock); do not duplicate logic with a different result.
- **2.9 compositor_configs** (dir-ensure + check-gating + runtime exec test): 2.9 COPIES per-FILE with `force: false` (transfer-only-if-absent — a directory src + force: false is a silent no-op); 2.10 COPIES DIRECTORIES with the default `force: true` (checksum idempotent — Ansible is the state authority). 2.9's fragment source assert is check-gated (fragments are apply-time outputs); 2.10's SOURCE assert is ungated (repo content is static); 2.10's RESOLVE assert IS check-gated (dests absent under --check). 2.9's resolve verifies placed files; 2.10's resolve verifies REAL DIRECTORIES (runtime independence).
- **2.6 assets** (copy + repo_root + trailing-`/`): 2.6 copies from `<repo>/dotfiles/assets/**` into the install spine; 2.10 copies from `<repo>/dotfiles/config/*` into the user config home. Both use `ansible.builtin.copy` with `remote_src: true` and a trailing-`/` src.
- **cli_tools** (manifest parity): the exact `(name, target)` set-equality parity test.

### Deferred work / not re-opened here

- hypr/hyprpaper/waybar joining `config-copies.yaml`: Story 2.8's navigation note left "whether/how they join is 2.10's call" — the answer is NO: 2.9 owns them by COPY (FR-19), the reader test forbids adding them to the manifest. Do not re-open.
- Install-spine symlinking (`<install>/*`): out of scope — 2.10 copies ONLY repo `dotfiles/config/*` → `~/.config/*` (FR-20). NFR-8 spine containment: the role adds nothing else to the XDG config tree.
- Planning snapshots (PRD 2026-08-03, SPEC.md, .memlog, hex-architecture doc, readiness report) still say "symlinks" — historical records of the pre-pivot plan; the live contracts (plan doc, epic, reader, role, story) are updated.

## Project Structure Notes

- `src/provisioning/ansible/roles/config_copies/tasks/main.yml` — NEW role tasks (fact-gathering assert, non-empty guard, source guard, XDG + target dir-ensure, copy, resolve guard).
- `src/provisioning/ansible/roles/config_copies/vars/main.yml` — NEW role vars (repo root, XDG home, `config_copies_entries` mirror).
- `src/provisioning/ansible/playbooks/config-copies.yaml` — NEW one-per-role playbook (localhost, gather_facts, roles: [config_copies], no become, no group_by).
- `src/provisioning/tests/unit/test_config_copies_role.py` — NEW structural real-file tests (mirror `test_compositor_configs_role.py`).
- `dotfiles/provisioning/config-copies.yaml` — RENAMED from `symlinks.yaml`; `kind: config-copies` (2.1 lock updated by the pivot).
- `src/provisioning/src/provisioning/domain/enums.py` + `adapters/yaml_manifest_reader.py` + `tests/unit/test_domain.py` + `tests/unit/adapters/test_yaml_manifest_reader.py` — SYMLINKS → CONFIG_COPIES rename.
- Consumed, NOT modified: `dotfiles/config/{nvim,starship,wlogout,zsh}/` (existing dirs; the role only reads them), `src/provisioning/src/**` (Python hexagon untouched beyond the enum/schema rename).
- No new dependencies. No Python outside the test file + the enum/reader rename.

## Testing Requirements

- Full gates: `uv run pytest` (355-pass baseline from Story 2.9 + its review fixes — see Git Intelligence), `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src tests` (new file must be mypy-clean; 10 pre-existing baseline errors remain in test_default_palette_role.py/test_cli_tools_role.py — do NOT chase them), `python tests/architecture/test_layering.py` (standalone nicety).
- New `src/provisioning/tests/unit/test_config_copies_role.py` (see Tasks/Subtasks): copy the FULL helper suite verbatim from `test_compositor_configs_role.py` (`_find_ansible_dir()` walk-up resolver, `_TASK_KEYWORDS` (the extended set incl. block/rescue/delegate_to), `_module_key`/`_module`/`_module_text`/`_creates_value`, `_vars()`, `_tasks_with_module()`), plus the cli_tools-style `_manifest_entries()` reading `dotfiles/provisioning/config-copies.yaml`. Classes in order: `TestConfigCopiesRoleTree`, `TestConfigCopiesTasks`, `TestConfigCopiesVars`, `TestConfigCopiesPlaybook`. Assert:
  - role tree; tasks parse to named tasks
  - first task is the fail-loud fact-gathering assert (NOT the install_dir assert)
  - non-empty guard assert on `config_copies_entries | length > 0`, ungated
  - source stat+assert pair: both loop `config_copies_entries`, `follow: true` on the stat, derived-count assert incl. `stat.isdir`
  - copy task: `ansible.builtin.copy`, `src` prefixed `{{ config_copies_repo_root }}/dotfiles/config/` + trailing `/`, `dest` prefixed `{{ config_copies_xdg_config_home }}/` + trailing `/`, `remote_src: true`, NOT `force: false`, loop, NO `creates:`, NOT check-gated
  - resolve pair: ONE stat loop `follow: false` + `stat.isdir` assert, both gated `when: not ansible_check_mode`
  - XDG-home dir-ensure + per-target dir-ensure: `state: directory`, ungated
  - no become; no hardcoded absolute paths (trim lock — scan vars too)
  - vars: required keys, repo_root mirror (exact string), XDG honors + F4 lock (no `{{ ansible_env.`), `config_copies_entries` == manifest entries exactly
  - playbook: parses, localhost/gather_facts/roles [config_copies], no become, no group_by; `--syntax-check` exit 0 (skip-if-absent)
  - runtime execution test (creates real dir copies into temp HOME/XDG — NOT symlinks; re-run is a no-op)
- Do NOT re-use a shared conftest for role tests — the duplicated-helper pattern is the accepted repo convention.

## Previous Story Intelligence

### Story 2.9 — Compositor Configs Role (DONE 2026-08-12, the immediate predecessor)
- Established the CURRENT canonical test suite to mirror: full helper set, extended `_TASK_KEYWORDS`, the runtime execution test (review finding 2026-08-12 — structural tests alone missed a silent copy no-op; the runtime test is now load-bearing). Mirror that discipline: THIS story's runtime test must prove copies actually land as real dirs.
- 2.9 COPIES hypr/hyprpaper/waybar skeletons + palette fragments into `~/.config/...` (FR-19). 2.10 copies the four config dirs (FR-20) with the same copy discipline. The 2.9 boundary: its fragment sources are apply-time outputs (check-gated); 2.10's sources are static repo content (ungated).

### Story 2.1 — Declarative Manifests (the manifest owner)
- Locked `dotfiles/provisioning/config-copies.yaml` (renamed from `symlinks.yaml` by the pivot) with `kind: config-copies` / `entries: [{name, target}]`. Reader schema: required `{name, target}`, allowed `+version`. The reader test asserts names == `{nvim, starship, wlogout, zsh}` and forbids hypr/hyprpaper/waybar. This story's `config_copies_entries` must mirror EXACTLY (parity test). [Sources: 2-1-declarative-manifests.md, dotfiles/provisioning/config-copies.yaml, yaml_manifest_reader.py#37-39, test_yaml_manifest_reader.py]

### Story 2.5 — Filesystem Role (the dir creator)
- Created the XDG config home + dirs via `filesystem_xdg_config_home` (honors `$XDG_CONFIG_HOME`, default `{{ ansible_facts.env.HOME }}/.config`, `ansible_facts.env` NOT `ansible_env`). This role copies INTO that home — use the identical derivation. [Source: filesystem/vars/main.yml#23-31]

### Story 2.2 — Ansible Scaffold
- The scaffold (inventory, ansible.cfg, requirements.yml) is already in place; `config_copies` adds only a role dir, a playbook, and a test file — no inventory/config changes.

### Epic 1 retrospective (2026-08-08) — action item touching this story
- "Mirror-and-adapt discipline": explicit "what differs from the mirror" checklist (addressed in Dev Notes).

## Git Intelligence

- Baseline: `fb0c979` (`fix: apply code review findings for story 2.9 compositor configs role`, 2026-08-12). Working tree was CLEAN. 355 tests pass at baseline (verified 2026-08-12).
- Pivot commit flow: this story's review run renamed `symlinks` → `config_copies` / `config-copies` and rewrote the role/playbook/test for copy semantics; the reader enum/schema/tests were updated; the plan doc done-criterion 9 + epic FR-20/2.12 verify criterion were updated.
- This story adds/renames ONLY: `dotfiles/provisioning/config-copies.yaml`, `src/provisioning/ansible/roles/config_copies/**`, `src/provisioning/ansible/playbooks/config-copies.yaml`, `src/provisioning/tests/unit/test_config_copies_role.py`, the enum/reader/test renames, and the story/status artifacts. Verify with `git status --short` that nothing else moved.

## Latest Tech Information

- ansible-core **2.20.3** is the installed/runtime version (verified 2026-08-12 via `uv run ansible --version`); pyproject requires `ansible-core>=2.16`. Collections: community.general, ansible.posix, kewlfft.aur (pinned in requirements.yml). No new collections needed — `ansible.builtin.copy`/`stat`/`assert`/`file` are core.
- `ansible.builtin.copy` (verified 2026-08-12): directory `src` with a trailing `/` copies contents recursively into `dest/` (checksum idempotent — unchanged → `changed: false`); `force: false` with a directory src + pre-existing dest dir is a SILENT NO-OP; check_mode FULL support (predicts changed, writes nothing); fails loudly on a missing source. [Source: ansible.builtin.copy module docs; empirical verification]
- **stat follow trap (verified 2026-08-12):** the stat module does NOT resolve symlinks by default in ansible-core 2.20.3 — `follow` must be EXPLICIT. With `follow: false` a symlink reports `islnk: true / isdir: false`; the resolve guard uses this to prove every dest is a REAL directory (runtime independence).
- F4 lock (repo-wide): read env via `ansible_facts.env`, never the deprecated top-level `ansible_env` fact (INJECT_FACTS_AS_VARS hard-breaks on ansible-core >= 2.24).
- `gather_facts: true` is REQUIRED on the playbook (vars derive from `ansible_facts.env.HOME`/`XDG_CONFIG_HOME`) — the FIRST task asserts it fails loudly.

## References

- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#433-445] — Story 2.10 ACs (config_copies role, copy-not-symlink)
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#41] — FR-20 Config Copies Role
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#24,475] — FR-3 / FR-22 (verify asserts "config copies present" among done-criteria)
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#50] — NFR-1 idempotency (Ansible is the state authority)
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#57] — NFR-8 spine containment
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#194] — plan §6: `config-copies.yaml` manifest (repo `dotfiles/config/*` → `~/.config/*`)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#154,164] — plan §6: `config-copies.yaml` playbook + `roles/config_copies/` tree
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#248] — done-criterion 9 (every config-copy entry is a real directory at runtime)
- [Source: dotfiles/provisioning/config-copies.yaml] — the locked manifest (4 entries; header forbids hypr/hyprpaper/waybar)
- [Source: src/provisioning/src/provisioning/adapters/yaml_manifest_reader.py#37-39] — config-copies entry schema (required `name`+`target`)
- [Source: src/provisioning/src/provisioning/domain/enums.py#74] — `ManifestKind.CONFIG_COPIES = "config-copies"`
- [Source: src/provisioning/ansible/roles/filesystem/vars/main.yml#23-31] — `filesystem_xdg_config_home` derivation to mirror as `config_copies_xdg_config_home`
- [Source: src/provisioning/ansible/roles/assets/vars/main.yml#15-19] — `assets_repo_root` derivation to mirror as `config_copies_repo_root`
- [Source: src/provisioning/ansible/roles/cli_tools/vars/main.yml + test_cli_tools_role.py#381] — the exact-match parity-test pattern to mirror
- [Source: src/provisioning/tests/unit/test_compositor_configs_role.py] — the full helper suite + runtime execution test pattern to mirror
- [Source: src/provisioning/ansible/playbooks/compositor-configs.yaml] — the playbook template (localhost, gather_facts, roles, no become, no group_by)
- [Source: _bmad-output/implementation-artifacts/2-9-compositor-configs-role.md] — previous story (copy-vs-link boundary; runtime exec test; review-fix baseline)
- [Source: _bmad-output/implementation-artifacts/2-1-declarative-manifests.md] — config-copies.yaml format + the icon-template-color-scheme-mappings NOT-a-copy note
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml#75] — story 2-10-config-copies-role status

## Dev Agent Record

### Agent Model Used

opencode (deepseek-v4-flash)

### Debug Log References

- Baseline `fb0c979` is the 2.9 review-fix commit; working tree clean; 355 tests pass.
- Ansible behaviors verified empirically 2026-08-12 against ansible-core 2.20.3 (see Latest Tech Information): `copy` directory semantics (trailing `/`, checksum idempotency, force:false silent-no-op trap, check-mode support); the stat module's follow-flag default trap (a symlink reports `islnk: true / isdir: false` under follow:false).
- Pre-existing mypy baseline: `uv run mypy src tests` reports 10 errors in `tests/unit/test_default_palette_role.py` and `tests/unit/test_cli_tools_role.py` — present at baseline, NOT introduced by this story. The new `test_config_copies_role.py` must be mypy-clean.

### Completion Notes List

- Created Story 2.10 Config Copies context: `config_copies` role (fact-gathering assert + non-empty guard + source guard + XDG/target dir-ensure + copy + resolve guard), `config-copies.yaml` playbook, structural + parity + runtime tests.
- **PIVOT 2026-08-12 (code review):** runtime independence — configs are COPIED not symlinked; the machine works after the repo is deleted. Renamed `symlinks` → `config_copies`/`config-copies` everywhere (manifest, kind, reader enum/schema/tests, role, playbook, test, story, sprint key), updated plan done-criterion 9 + epic FR-20/2.12, and folded all four patch findings into the copy design (`stat.isdir` source guard, non-empty guard, gather_facts first-task assert, generic fail_msgs).
- Locked the manifest mirror: `config_copies_entries` = the four `{name, target}` pairs from `dotfiles/provisioning/config-copies.yaml`; parity test enforces exact equality.
- Locked NO-install_dir-assert: this role consumes no install_dir; the first task is the fail-loud fact-gathering assert instead.
- Locked the copy contract: directory `src` trailing `/`, `remote_src: true`, default `force: true` (checksums = idempotency; NOT force: false — silent-no-op trap), NO `creates:`, ungated (full check-mode support).
- Locked the resolve guard: ONE stat `follow: false` + `stat.isdir` assert (real dirs, not symlinks — runtime independence), gated under --check.
- Scope guards: no manifest edits beyond the pivot rename, no hypr/hyprpaper/waybar in `config_copies_entries`, no install-spine copying (NFR-8), no Python hexagon changes beyond the enum/schema rename.
- Status → review.
- Implemented Story 2.10 (2026-08-12, post-pivot): created `config_copies` role + `config-copies.yaml` playbook + `test_config_copies_role.py` (19 tests: tree, tasks contract, non-empty guard, source pair, copy contract, resolve guard, dir-ensures, vars + parity, playbook, syntax-check, runtime execution + idempotency).
- Runtime execution test verifies real directory copies land in temp HOME/XDG (NOT symlinks — runtime independence), contents match the repo source, and re-run is a no-op (`changed=0`).
- Full suite green (reader/domain/manifest tests updated for `kind: config-copies`); ruff clean; mypy clean for the new file (10 pre-existing baseline errors untouched); layering guard OK.

### File List

- `src/provisioning/ansible/roles/config_copies/tasks/main.yml` (NEW — renamed from `symlinks/`)
- `src/provisioning/ansible/roles/config_copies/vars/main.yml` (NEW — renamed from `symlinks/`)
- `src/provisioning/ansible/playbooks/config-copies.yaml` (NEW — renamed from `symlinks.yaml`)
- `src/provisioning/tests/unit/test_config_copies_role.py` (NEW — renamed from `test_symlinks_role.py`)
- `dotfiles/provisioning/config-copies.yaml` (NEW — renamed from `symlinks.yaml`, `kind: config-copies`)
- `src/provisioning/src/provisioning/domain/enums.py` (SYMLINKS → CONFIG_COPIES)
- `src/provisioning/src/provisioning/adapters/yaml_manifest_reader.py` (schema key)
- `src/provisioning/tests/unit/test_domain.py` + `src/provisioning/tests/unit/adapters/test_yaml_manifest_reader.py` (kind rename)
- `docs/01-dotfiles-provisioning-phase1-plan.md` (done-criterion 9, §6 tree, role order)
- `_bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md` (FR-3/12/20, story 2.10, story 2.12)
- `_bmad-output/implementation-artifacts/2-10-config-copies-role.md` (this story — renamed from `2-10-symlinks-role.md`)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (story key)
- `_bmad-output/implementation-artifacts/deferred-work.md` (deferred entries updated for the rename)
