---
baseline_commit: 56bde5c
---

# Story 3.1: GTK config dirs in the spine + config_links

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want `~/.config/gtk-3.0` and `~/.config/gtk-4.0` as spine symlinks with palette-importing skeletons,
So that GTK apps read the wallpaper palette from the runtime's `current/` pointers.

## Acceptance Criteria

### Verbatim contract (epics-gtk-theming.md, Story 3.1)

**Given** the user's existing `~/.config/gtk-3.0/{settings.ini,gtk.css}` (real files, user-owned)
**When** provisioning apply runs
**Then** spine `config/gtk-3.0/` holds the user's migrated `settings.ini` + `gtk.css` (backup guard: timestamped copy under `~/.config/.dotfiles-backups/`, never `rm -rf`) plus a palette import line appended/merged into `gtk.css` (`@import "colors.css";`)
**And** spine `config/gtk-4.0/` holds a new `gtk.css` with `@import "colors.css";`
**And** `config_links` creates `~/.config/gtk-{3,4}.0` → spine symlinks (idempotent, already-ours = no-op)
**And** verify gains a criterion asserting both symlinks + skeleton files; `nwg-look` write-through is documented (writes land in the spine through the link)

### Operational sub-ACs (dev contract — derived from the verbatim block + investigation §2 provisioning row and §6 risks)

1. **Given** `dotfiles/provisioning/filesystem.yaml` + `roles/filesystem/vars/main.yml`, **When** the spine manifest grows, **Then** `config/gtk-3.0` and `config/gtk-4.0` join `filesystem_spine_dirs` (and the manifest `entries` in the same order) so the filesystem role (2.5) creates both parents before any writer runs — pure data addition, no task changes (the loop already consumes the list); `roles/verify/vars/main.yml` `verify_install_spine_dirs` mirrors them (criterion 1), preserving the parity-EXACT locks (`test_install_spine_dirs_parity_with_filesystem`, `test_parity_with_manifest`) with zero test edits (AC: verbatim "spine `config/gtk-3.0/` + `config/gtk-4.0/`").

2. **Given** the config_links role, **When** the gtk dirs join the managed set, **Then** `config_links_managed_dirs` gains `gtk-3.0` + `gtk-4.0` (appended — order is parity-locked with `verify_managed_link_dirs` by `test_managed_link_dirs_parity_with_config_links`, which stays green with zero edits), so `~/.config/gtk-{3,4}.0 → <install>/config/gtk-{3,4}.0` ride the EXISTING guard machinery: exists-state classification (`_link_one.yml` stat + `is_correct_link`), timestamped whole-dir move-aside to `~/.config/.dotfiles-backups/<name>-<ts>`, TTY-aware `auto|ask` policy prompting, check-mode gating, idempotent already-ours no-op (AC: verbatim "And `config_links` creates `~/.config/gtk-{3,4}.0` → spine symlinks (idempotent, already-ours = no-op)").

3. **Given** the real user dirs on this machine (`~/.config/gtk-3.0/{settings.ini,gtk.css}` real files; `~/.config/gtk-4.0/settings.ini` only — investigation §1), **When** the migration guard fires for a seed dir, **Then** a NEW migrate-then-symlink step runs BEFORE the move-aside: the pre-existing dir's contents are COPIED into the freshly-created spine dir (`<install>/config/<name>/`) with `ansible.builtin.copy` (`remote_src: true`, trailing-`/` contents-into-dest, default `force: true`), gated `stat.exists AND stat.isdir AND not is_correct_link`; the existing backup `mv` then preserves the ORIGINAL verbatim in the timestamped backup (the spine copy is a second copy — the backup stays untouched/recoverable); ordering is pinned **seed → backup → symlink** so a seed failure aborts the run BEFORE the move (the user's live dir is never displaced by a failed migration) (AC: verbatim "the user's migrated `settings.ini` + `gtk.css` (backup guard: timestamped copy under `~/.config/.dotfiles-backups/`, never `rm -rf`)").

4. **Given** the palette-import skeleton requirement, **When** the per-entry include processes a gtk dir, **Then** an `ansible.builtin.lineinfile` on the SPINE path `<install>/config/gtk-{3,4}.0/gtk.css` with `line: '@import "colors.css";'` and `create: true` ensures the import line: gtk-4.0's file is NEW (the user has no `gtk-4.0/gtk.css`), gtk-3.0's file is the user's migrated file (xfce padding snippet) with the import APPENDED at EOF — `lineinfile` without `regexp` is the idempotent-append mechanism (inserts only if absent; re-runs NEVER duplicate the import); it runs on EVERY pass (not gated on the classification) so it also repairs a spine `gtk.css` missing the import, and it must be ordered AFTER the seed copy (the copy must not overwrite the appended line) and BEFORE the symlink task (AC: verbatim "plus a palette import line appended/merged into `gtk.css`" + "And spine `config/gtk-4.0/` holds a new `gtk.css` with `@import "colors.css";`").

5. **Given** a fresh machine (no `~/.config/gtk-{3,4}.0`), **When** provisioning apply runs, **Then** the guard classifies absent → no prompt, no backup, no seed; the append creates both `gtk.css` files with exactly the import line; the symlinks are created — the skeleton outcome is IDENTICAL to the migrated outcome except the migrated `settings.ini` files, whose presence is machine-state, not provisioning state (AC: verbatim skeleton clauses on a fresh machine).

6. **Given** the verify role, **When** the criteria grow, **Then** (i) `verify_install_spine_dirs` gains the two gtk dirs (criterion 1 machinery — spine dirs exist as real dirs); (ii) `verify_managed_link_dirs` gains `gtk-3.0` + `gtk-4.0`, pulling them into the EXISTING 5-layer symlink check (layers 1-3: islnk / exact `<install>/config/<name>` target / resolves-to-dir); (iii) a NEW `verify_gtk_skeleton_files` list (`~/.config/gtk-3.0/gtk.css`, `~/.config/gtk-4.0/gtk.css` — through the links, `follow: true`, isreg) delivers layer 4 (content-through-link) via a stat+assert pair mirroring the `verify_config_copy_content` pattern; (iv) a NEW grep gate (`grep -E '@import "colors\.css";'`) over both `gtk.css` files (through the `~/.config` links) asserts the palette wiring — mirror of the wlogout `style.css` grep gate — both new asserts check-gated `when: not ansible_check_mode` and registered in the vacuous-pass empty-list guard (AC: verbatim "And verify gains a criterion asserting both symlinks + skeleton files").

7. **Given** the nwg-look hazard (investigation §6: nwg-look writes `settings.ini`), **When** the story lands, **Then** the write-through is DOCUMENTED at the mechanism's home — the config_links role header (vars + tasks) gains the note that post-link nwg-look writes land IN the spine through the symlink and survive (and the backup guard migrates the pre-spine original) — plus a short migrate-then-symlink + nwg-look subsection in `docs/02-config-in-spine-pattern.md` (the guard-spec doc this task set extends); no other docs are touched (gt-4.2 owns the contract-doc reconciliation) (AC: verbatim "`nwg-look` write-through is documented (writes land in the spine through the link)").

## Tasks / Subtasks

- [ ] Task 1 — filesystem role: spine dirs (AC: 1)
  - [ ] `dotfiles/provisioning/filesystem.yaml`: append `- name: config/gtk-3.0` + `- name: config/gtk-4.0` to `entries` after `- name: config/itr` (comment noting the GTK consumer dirs land here in gt-3-1 and host the runtime's `colors.css` pointers at first seed).
  - [ ] `src/provisioning/ansible/roles/filesystem/vars/main.yml`: append the same two entries to `filesystem_spine_dirs` in the same order; extend the header comment (config-in-spine list) with the gtk dirs + the runtime-pointer note (provisioning creates the DIRS only — never the `colors.css` pointers, which the runtime seeder owns, gt-2-2).
  - [ ] VERIFY NO-EDIT: `src/provisioning/tests/unit/test_filesystem_role.py::test_parity_with_manifest` derives `expected` from the manifest dynamically — manifest + vars updated in lockstep stay green.
- [ ] Task 2 — config_links vars (AC: 2)
  - [ ] `src/provisioning/ansible/roles/config_links/vars/main.yml`: append `gtk-3.0` + `gtk-4.0` to `config_links_managed_dirs` (AFTER `itr` — list order is parity-locked with `verify_managed_link_dirs`).
  - [ ] Same file, new vars: `config_links_gtk_dirs: [gtk-3.0, gtk-4.0]` (the entries that get the migrate-seed + `@import` treatment) and `config_links_gtk_import_line: '@import "colors.css";'`; header comment gains the migrate-then-symlink design note + the nwg-look write-through note (AC 7).
- [ ] Task 3 — config_links tasks: migrate-then-symlink inside `_link_one.yml` (AC: 2, 3, 4)
  - [ ] `src/provisioning/ansible/roles/config_links/tasks/_link_one.yml`, inserted after the classification task and BEFORE the prompt/backup tasks (exact order: ensure-dir → seed → prompt → backup-mv → append → symlink):
    1. **Ensure spine dir** (seed dirs only): `ansible.builtin.file` `state: directory` on `{{ install_dir | trim }}/config/{{ config_link_name }}`, gated `when: config_link_name in config_links_gtk_dirs` — ungated for check mode (natively check-safe; direct config-links.yaml run self-containment, mirror of the 2.10 target-dir-ensure pattern).
    2. **Seed the spine from the user's existing dir**: `ansible.builtin.copy` `src: "{{ config_links_xdg_config_home }}/{{ config_link_name }}/"` `dest: "{{ install_dir | trim }}/config/{{ config_link_name }}/"` `remote_src: true`, gated `when: config_link_name in config_links_gtk_dirs and config_links_existing.stat.exists and config_links_existing.stat.isdir and not config_links_is_correct_link` — NO check-mode gate (copy has full check-mode support; the source is real machine content that exists under --check too). The `stat.isdir` gate skips a regular-file/foreign-symlink pre-existing target (the guard's `mv` still handles those).
    3. **Ensure the `@import` line** (after the backup-mv block, before the symlink task): `ansible.builtin.lineinfile` `path: "{{ install_dir | trim }}/config/{{ config_link_name }}/gtk.css"` `line: "{{ config_links_gtk_import_line }}"` `create: true`, gated `when: config_link_name in config_links_gtk_dirs` — NO `regexp:` (no-regexp + absent line = insert at EOF; present line = no-op; re-runs never duplicate), NO check-mode gate (lineinfile is check-safe), NOT gated on the classification (repairs a spine missing the import on re-run).
  - [ ] Confirm the EXISTING tasks are untouched: backup-root ensure, stat, spine-target/timestamp set_facts, classification, skip-debug, `ask`-policy pause, backup `mv` (check-gated), symlink.
  - [ ] Confirm nothing writes the `colors.css` pointer files (runtime-owned, gt-2-2) and nothing touches `state_root` (§11 boundary, AD-5).
- [ ] Task 4 — verify role (AC: 6)
  - [ ] `src/provisioning/ansible/roles/verify/vars/main.yml`: append `config/gtk-3.0` + `config/gtk-4.0` to `verify_install_spine_dirs` (same position as filesystem's list); append `gtk-3.0` + `gtk-4.0` to `verify_managed_link_dirs`; NEW var `verify_gtk_skeleton_files: ["{{ verify_xdg_config_home }}/gtk-3.0/gtk.css", "{{ verify_xdg_config_home }}/gtk-4.0/gtk.css"]` with a comment noting settings.ini is deliberately NOT gated (user-machine state) and the runtime `colors.css` pointers are deliberately NOT gated (runtime-owned; health = the gt-2-2 `inspect status` projection).
  - [ ] `src/provisioning/ansible/roles/verify/tasks/main.yml`: NEW stat+assert pair over `verify_gtk_skeleton_files` (`follow: true`, `selectattr('stat.isreg')` count parity — layer 4; check-gated); NEW grep gate pair — `ansible.builtin.command` `grep -E '@import "colors\.css";'` looping the skeleton files (through the `~/.config` links; `changed_when: false`, `failed_when: false`, check-gated) + assert `rc == 0` per file with a fail_msg mirroring the wlogout gate's shape.
  - [ ] Same file: extend the vacuous-pass empty-list guard assert (the `- name: Assert verify list vars are not empty` task) with `verify_gtk_skeleton_files | length > 0`.
- [ ] Task 5 — docs (AC: 7)
  - [ ] `docs/02-config-in-spine-pattern.md`: add a short "Migrate-then-symlink (GTK consumer dirs, gt-3-1)" subsection under the backup-guard section — per-entry seed flag semantics (copy pre-existing dir contents into the spine BEFORE the move-aside, ordering rationale), the idempotent `@import "colors.css";` append, and the nwg-look write-through sentence (nwg-look writes land in the spine through the link; the backup guard migrates the original).
- [ ] Task 6 — tests (AC: 2, 3, 4, 6)
  - [ ] NEW `src/provisioning/tests/unit/test_config_links_role.py` (mirror `test_config_copies_role.py` conventions — task/vars parsers, `_TASK_KEYWORDS`, `_module_key`): structural tests (first task = install_dir assert in `tasks/main.yml`; `_link_one.yml` backup `mv` gated + `ask` pause gated + symlink ungated-by-check; seed copy gated `isdir + not correct-link` and placed BEFORE the `mv` task; lineinfile carries `create: true` + the import-line var and sits AFTER the seed task; no become; no hardcoded absolute paths; vars parity `config_links_managed_dirs == verify_managed_link_dirs` — already locked from the verify side, lock it from this side too; `config_links_gtk_dirs ⊆ config_links_managed_dirs`).
  - [ ] Same file, execution tests (real `ansible-playbook` against a temp HOME/XDG/install, skip when ansible-playbook is absent — mirror `test_config_copies_role.py::test_playbook_executes_and_creates_config_copies`): (a) fresh machine → spine `gtk-{3,4}.0/` each hold `gtk.css` containing exactly one `@import "colors.css";` line, `~/.config/gtk-{3,4}.0` are symlinks into the spine, re-run recap `changed=0`; (b) migration machine → pre-create `~/.config/gtk-3.0/` with `settings.ini` + `gtk.css` (padding snippet WITHOUT the import) and `~/.config/gtk-4.0/` with `settings.ini` only → after apply: spine holds BOTH migrated files, `gtk-3.0/gtk.css` has the original snippet + exactly ONE import line appended, `gtk-4.0/gtk.css` is the new import file, a timestamped backup dir exists under `~/.config/.dotfiles-backups/` for each, re-run is `changed=0` and the import line count is STILL 1.
  - [ ] UPDATE `src/provisioning/tests/unit/test_verify_role.py`: `_build_provisioned_layout` gains the two gtk spine dirs + `~/.config/gtk-{3,4}.0` spine symlinks + both `gtk.css` files (with the import line) in the spine — the fixture IS the provisioned machine and must satisfy the new criterion; `TestVerifyVars._REQUIRED_KEYS` += `verify_gtk_skeleton_files`; NEW tests for the skeleton stat/assert pair + the grep gate (mirror the wlogout-gate tests' discovery helpers); VERIFY the two parity tests stay green with zero edits.
  - [ ] VERIFY ONLY (expected green, touch only if an assertion exists): `test_filesystem_role.py` (dynamic parity), `test_bootstrap_playbook.py` (order unchanged — config_links already runs after every writing role), `test_config_copies_role.py` (no config_copies changes; the gtk dirs are NOT config_copies dests so the palette-symlink tripwire never scans them), `test_settings_parity.py` (minimal-spine fixture omits gtk dirs — it exercises the settings playbook + CLI gates only), `tests/integration/test_ansible_dryrun.py` (config-links playbook already in `_PLAYBOOKS`; the new copy/lineinfile tasks are check-safe so the dry run stays clean), `test_apply_verify_container.py` (container bootstrap exercises the new flow for real — gtk dirs are new OUTCOMES, not new seams).
- [ ] Task 7 — Full green (AC: 6)
  - [ ] Record provisioning gate baselines BEFORE coding (gt-2-1/gt-2-2 stash procedure):
    ```bash
    uv run --directory src/provisioning pytest -q
    uv run --directory src/provisioning ruff check .
    uv run --directory src/provisioning ruff format --check .
    uv run --directory src/provisioning mypy
    ```
    Post-implementation must be EXACTLY at baseline — zero new violations; the NEW test file must be ruff-format clean (do not inherit the tests-wide pre-existing count).
  - [ ] Sanity greps: `grep -rn "gtk-3.0\|gtk-4.0" src/provisioning/ansible/` shows the dirs ONLY in filesystem manifest/vars, config_links vars/tasks, verify vars/tasks (+ tests); `grep -rn "colors.css" src/provisioning/ansible/roles/config_links/` shows NO pointer creation (import line only); `grep -rn "state_root\|XDG_STATE_HOME" src/provisioning/ansible/roles/config_links/` — unchanged (config_links never derives a state path).

## Dev Notes

### Scope boundary — this story is provisioning spine + migration only

Story gt-3-1 turns the GTK dirs into managed config-in-spine entries. It does **NOT** implement:

- **The `colors.css` pointer files** — `{install}/config/gtk-3.0/colors.css` and `{install}/config/gtk-4.0/colors.css` are runtime ConsumerPointer dests (gt-2-2, `StaticConsumerPathSpec`): the runtime seeder creates them on the first seed/reconcile AFTER this story's dirs exist. Provisioning must NEVER create, reference, or verify them. Before the first seed they are simply absent inside the spine dirs; the `@import "colors.css";` line pointing at them is harmless until then (GTK ignores a missing import file).
- **zshrc repoint** — `.zshrc.j2` → `current/colors.sequences` is gt-3-2.
- **Runtime changes** — seeder/inspect/applier are all done (gt-2-1..2-3); nothing in `src/runtime` is touched. The pre-gt-3-1 skip+warn on missing gtk pointer parents (gt-2-2 sub-AC 4d / Design decision 2) becomes dead code in the happy path once these dirs exist — do NOT touch the runtime to "simplify" it.
- **Runtime-owned health gates** — the runtime pointers are reported by `inspect status`'s spec-driven projection (gt-2-2); verify does not re-own them (would fail on any machine that has not re-seeded since provisioning).
- **Doc reconciliation** — `shared-data-contract.md`, `consumer-wiring.md`, ARCHITECTURE-SPINE AD-11, `docs/99` are gt-4.2. Only the `docs/02` guard-spec subsection (AC 7) is in scope here.

### Design decision 1 — why the minimal task set lives INSIDE config_links (not config_copies, not a new role)

The migration source is USER-MACHINE content (`~/.config/gtk-3.0/`), not repo content. `config_copies` is manifest-parity-locked to `dotfiles/provisioning/config-copies.yaml` (repo `dotfiles/config/*` sources; the parity test locks exact (name, target) set equality) and its contract is "repo dirs → spine" — it structurally cannot express "seed the spine from the machine's existing config". The guard that already owns exists-state classification, timestamped backups, TTY-aware prompting, check-gating, and idempotent no-ops IS `config_links` (`_link_one.yml`), and `docs/02`'s backup-guard spec is this role's design doc — so the minimal, cohesive change is three gated tasks in the per-entry include + two vars. A new `gtk_config` role would duplicate the seam assert, policy var, and backup root for no separation gain. The docs/02 "backup is a copy, never a move" line describes the pre-implementation spec; the shipped guard uses an atomic `mv` (the original is preserved verbatim at the backup path — same safety guarantee). The seed step is a genuine COPY (from the live path, before the mv) and does not change the mv mechanics.

### Design decision 2 — seed → backup → symlink ordering (partial-failure safety)

Seeding BEFORE the move-aside means: a seed-copy failure aborts the playbook with the user's live `~/.config/gtk-3.0/` still intact and untouched (no backup taken, no link created — re-run re-classifies the real dir and retries cleanly). Seeding after the mv would leave a failure window where the user's dir exists ONLY in the backup and a re-run classifies the destination as ABSENT (→ plain symlink, no seed) — the migrated spine would silently miss the user's files. The seed is unconditional-copy (`force: true` default): on any re-run where a real dir reappears at `~/.config/gtk-<x>.0` (e.g. the user restored it), the guard backs that dir up again AND re-seeds the spine from it — converging the spine to the restored content rather than silently diverging.

### Design decision 3 — a separate `config_links_gtk_dirs` list, entries stay plain strings

`config_links_managed_dirs` entries are bare names and the parity test (`test_managed_link_dirs_parity_with_config_links`) compares the two lists EXACTLY — converting entries to dicts (e.g. `{name, seed: true}`) would churn every entry, both lists, and the test for zero behavioral gain. One new membership list (`config_links_gtk_dirs`) + one line constant (`config_links_gtk_import_line`) keep the existing 11 entries byte-identical and make the gtk-specific behavior a visible, overridable var rather than a hardcoded name check inside `_link_one.yml`.

### Design decision 4 — the append mechanism and what is deliberately not gated

`ansible.builtin.lineinfile` without `regexp` is the canonical idempotent "append-if-absent": it inserts at EOF only when the exact line is missing, so the user's migrated xfce padding snippet is preserved verbatim above the import and a re-run can never duplicate `@import "colors.css";`. It runs on the SPINE path (never through `~/.config` — pre-link the XDG path may not exist, and post-link writing through the link is an indirection the spine path avoids). Both the seed copy and the lineinfile are check-safe modules (full check-mode support, verified against ansible-core 2.20.3 for copy in 2.10; lineinfile predicts would-change without writing) — only the existing `mv` keeps its `not ansible_check_mode` gate. The gtk-4.0 "new file" and gtk-3.0 "append" cases are therefore ONE mechanism with different inputs, not two task families.

### Fresh-machine vs this-machine matrix (the four classified outcomes)

| State at `~/.config/gtk-<x>.0` | seed | backup | gtk.css outcome |
|---|---|---|---|
| absent (fresh machine) | no | no | created with exactly the import line |
| real dir (this machine: gtk-3.0 settings.ini+gtk.css; gtk-4.0 settings.ini) | yes (contents → spine) | yes (timestamped mv) | migrated file + one appended import (gtk-3.0) / new file with import (gtk-4.0) |
| real file / foreign symlink | no (`stat.isdir` gate) | yes | new spine gtk.css with import |
| already our spine link | no | no (no-op) | import ensured (no-op when present) |

### Verify scope notes (what the new criteria do and do not assert)

- The 5-layer check machinery applies to the gtk dirs automatically via `verify_managed_link_dirs` (layers 1-3 are generic loops). Layer 4 (content) uses only `gtk.css` — the ONE file provisioning guarantees in both dirs. `settings.ini` presence is user-machine state (a fresh machine has none in gtk-3.0/gtk-4.0 until nwg-look or GTK writes it) and would false-fail verify on fresh machines if gated.
- The grep gate reads through the `~/.config/gtk-{3,4}.0` links (exercising the link, mirroring how the settings parse gates read through `~/.config/<tool>`), pinning the exact `@import "colors.css";` line so a drifted import path fails.
- Criterion 1's spine-dirs message ("nine spine DIRS") is already stale in prose; update the fail_msg wording to stay truthful when touched (count is derived, never hardcoded).

### Previous story intelligence (gt-2-2) + git intelligence

- gt-2-2 (done at HEAD 56bde5c) landed the declarative `StaticConsumerPathSpec` with the gtk-3.0/gtk-4.0 pointer entries (`config/gtk-{3,4}.0/colors.css` → `current/colors.{gtk,adw}.css`) and the missing-parent skip+warn rule — its docs explicitly defer the spine dirs to "gt-3-1's provisioning of those dirs (backup guard, skeleton files)". This story is that provisioning; after it, the runtime pointers resolve on the first `wallpaper set`/reconcile without any runtime change.
- gt-2-1/gt-2-2 pinned the baseline-gate discipline (record counts BEFORE coding via `git stash`, post-implementation exactly at baseline) — replicate for the provisioning suite (`uv run --directory src/provisioning pytest -q`; record skips too — ansible-dependent tests skip on missing binaries).
- Repo convention: `feat(provisioning): ...`-style commits with `baseline_commit` frontmatter (this story: `56bde5c`); review fixes follow as separate commits. Story files live in the WORKTREE `_bmad-output/implementation-artifacts/` (the sprint-status `story_location` still points at the MAIN repo — stale, correction pending; same note as gt-2-2).
- Sprint-status precedent: gt-epic-2 flipped to `in-progress` when its first story (gt-2-1) was created; the same rule would flip gt-epic-3 → `in-progress` NOW — pinned in sprint-status per the explicit create-run override ("gt-3-1 line only, everything else verbatim"); flag for the review/dev step to apply the epic transition if desired.

### Architecture compliance (what the implementation must respect)

| Invariant | Application here |
|---|---|
| Machine, not repo (docs/02 core invariant) | The migration source is the machine's live config; the seed COPY makes the spine self-contained; nothing references the repo |
| NFR-8 Spine Containment | `~/.config/gtk-{3,4}.0` become alias symlinks; a spine wipe leaves them broken = unprovisioned (verify layer 3 fails loud) |
| Backup safety (docs/02 guard spec) | Whole-dir timestamped backup, never `rm -rf`, never prompts without a TTY (`auto` default), never touches a correct link |
| §11 boundary (AD-5/AD-15) | Provisioning writes ONLY under the install spine + `~/.config` — never under `state_root`; the `colors.css` pointers inside the spine dirs are runtime writes (gt-2-2), not provisioning writes |
| Ansible-as-state-authority (NFR-1) | copy checksum idempotency, lineinfile absence-idempotency, no `creates:`, no mutation gates on check-safe modules |
| User-scoped privilege context | NO become/become_user anywhere in the touched roles (config_links + filesystem already comply; keep it that way) |
| Trim lock / F4 lock | Every path derives from `{{ install_dir | trim }}` / `{{ config_links_xdg_config_home }}` / `ansible_facts.env.*` — no `ansible_env`, no hardcoded absolutes |

### Testing standards summary

- Runner: `uv run --directory src/provisioning pytest -q` (integration tests skip cleanly when `ansible-playbook`/`podman`/`sudo` are absent — record the skip baseline).
- Structural-test conventions to mirror (`test_config_copies_role.py` / `test_verify_role.py`): YAML task parsing with the `_TASK_KEYWORDS` module-key extraction; count asserts derive from `<var> | length`, never literals; every new role var joins the vacuous-pass guards and the required-keys set; "no hardcoded absolute paths" scans over tasks AND vars.
- Execution tests run the REAL playbook against a temp HOME + `XDG_CONFIG_HOME` + `install_dir` with `ANSIBLE_CONFIG` pointed at the scaffold `ansible.cfg`; idempotency proof = second-run recap contains `changed=0`.
- Dry-run discipline: `test_ansible_dryrun.py` asserts `--check` exits 0, `failed=0`, and does NOT create the scratch `install_dir` — the new seed-copy (check-safe) and lineinfile (check-safe) tasks must not break it; only the `mv` remains check-gated.

### Project Structure Notes

- Blast radius (grep-driven at 56bde5c): `grep -rn "filesystem_spine_dirs"` → roles/filesystem vars + verify vars + the two parity tests (dynamic); `grep -rn "config_links_managed_dirs"` → roles/config_links vars + verify vars + the parity test (dynamic); `grep -rn "verify_install_spine_dirs\|verify_managed_link_dirs"` additionally hits `test_verify_role.py::_build_provisioned_layout` (the ONE hardcoded fixture enumeration that MUST grow the gtk dirs) — everything else updates in lockstep without test edits.
- `_link_one.yml` is the only per-entry include — all three new tasks live there, keeping `tasks/main.yml` (loop + seam assert) unchanged.
- No new playbook, no new role, no bootstrap-order change: config_links already runs after every writing role (bootstrap.yaml import order line 65), and the gtk spine dirs are created by filesystem (line 56) long before.
- The gtk spine dirs are NOT `filesystem_compositor_dirs` (those are XDG-home dirs for the compositor links) — they are spine `config/` subdirs like `config/nvim`.

### References

- Epics: `_bmad-output/planning-artifacts/epics-gtk-theming.md` — Story 3.1 (verbatim AC block), FR-4, Epic 3 overview
- Investigation: `_bmad-output/planning-artifacts/gtk-theming-investigation.md` — §1 (user-machine facts: gtk-3.0 real files Arc-Dark/xfce snippet; gtk-4.0 settings.ini only), §2 (provisioning row: config-in-spine + backup guard + config_links + verify, "never writes under state_root"), §3 (pointer table context — the colors.css pointers this story's dirs host), §6 (risks: nwg-look write-through, backup guard migrates the original)
- Guard spec: `docs/02-config-in-spine-pattern.md` — Backup/migration guard (exists-state classification table, backup mechanics, TTY-aware prompting, safety guarantees), 5-layer verify check
- Predecessor (runtime side of the contract): `_bmad-output/implementation-artifacts/gt-2-2-iconsumerpathspec-declarative-pointers.md` — pointer paths `{install}/config/gtk-{3,4}.0/colors.css`, missing-parent skip+warn, "spine dirs arrive in gt-3-1"
- Provisioning code: `src/provisioning/ansible/roles/filesystem/{tasks,vars}/main.yml` (spine-dir manifest pattern), `roles/config_links/{tasks/main.yml,tasks/_link_one.yml,vars/main.yml}` (seam assert, classification, policy, backup root/mv/symlink), `roles/config_copies/{tasks,vars}/main.yml` (copy idempotency + tripwire conventions), `roles/verify/{tasks,vars}/main.yml` (criterion 9 5-layer check, empty-list guard, grep-gate pattern at the wlogout task), `playbooks/bootstrap.yaml` (import order), `dotfiles/provisioning/{filesystem,config-copies}.yaml` (manifest parity), `group_vars/{arch,debian-family}.yml` (VERIFY ONLY — no gtk package adds in scope)
- Test conventions: `src/provisioning/tests/unit/test_config_copies_role.py` (structural + execution mirrors), `test_verify_role.py` (parity locks, `_build_provisioned_layout`, gate tests), `tests/integration/test_ansible_dryrun.py` (`_PLAYBOOKS` sweep)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

### Change Log
