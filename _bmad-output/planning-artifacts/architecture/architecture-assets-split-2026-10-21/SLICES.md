# Migration Slices — the dotfiles corpus into one pinned assets repo

Sequential, destructive-last. S0 births the repo; S1–S4 move one class group each and delete what
they orphan; S5 makes the contract versions executable; S6 extracts the installer; S7 closes
`dotfiles-v3` as the composition repo. **No slice starts before its predecessor is merged on
`master`.**

Conventions used below:

```bash
# Consumer-side variables. OPEN-1 (hosting/name) is resolved to the precedent:
# public repo under this owner, same as the seven pinned repos.
ASSETS_REPO_BASE="https://github.com/RandomGenericUsername"
ASSETS_NAME="dotfiles-assets"          # OPEN-1: rename HERE ONLY if the name changes
MU=/home/inumaki/Development/mu         # harness source of truth
DTF=/home/inumaki/Development/dotfiles/dotfiles-v3   # main checkout
WT=$DTF/.worktrees/<slice-id>           # this slice's worktree
SPINE="${XDG_DATA_HOME:-$HOME/.local/share}/dotfiles"
```

Every acceptance gate is a command with an expected observable. "Expect exit 0" means the command
itself proves the claim. **Gates marked `PLANNED` are written to be run at slice time; they have not
been executed by the author of this plan** — the evidence for the *current* behaviour is in
`EVIDENCE-INDEX.md`, not in these blocks.

**Provisionability invariant (applies to every slice).** A slice is not mergeable unless the host is
still provisionable: `make gates-ci` exit 0 **and** the corpus-owned roles still resolve their
source. Before S1 the source is the repo; from S1 on it is the pin. The single command that proves
it end-to-end on a disposable target is `dev/vm-verify` (`dev/vm-fresh.sh`, incus) — local-only, not
CI (`ARCHITECTURE.md:563`).

**Tag chain — no slice consumes a tag an earlier slice did not produce:**

| Slice | Produces | Consumes |
| --- | --- | --- |
| S0 | assets `v0.1.0` (skeleton: 5 empty classes + schemas + catalog) | — |
| S1 | assets `v0.2.0` (icons + content) | assets `v0.1.0` (format/CI only) |
| S2 | assets `v0.3.0` (configs) | assets `v0.2.0` |
| S3 | assets `v0.4.0` (templates) | assets `v0.3.0` |
| S4 | assets `v0.5.0` (desktop) | assets `v0.4.0` |
| S5 | none (unless OPEN-4 forces a schema bump → `v0.6.0`) | assets `v0.5.0` |
| S6 | installer `v0.1.0` | assets `v0.5.0` (or `.6`) |
| S7 | none — pins finalize | installer `v0.1.0`, assets latest |

---

## S0 — Birth the assets repo (mu harness, five empty classes, schemas, catalog)

**Scope.** Create the repo with the full 13-item birth checklist and a *valid but empty* corpus, then
cut `v0.1.0`. Nothing in `dotfiles-v3` changes, so the host stays provisionable by construction. The
point of tagging an empty corpus is to prove the release ritual (gates → tag → CI → anonymous
clone) before the expensive migration depends on it.

**Entry criteria.**

- `master` clean (`bash scripts/worktree-guard.sh check-clean`), `make gates-ci` exit 0.
- OPEN-1 answered (repo name + visibility). Default if not: `dotfiles-assets`, public,
  `RandomGenericUsername`.
- Worktree: `bash scripts/worktree-guard.sh create s0 assets-repo-birth`.
- The three re-pointed birth items are understood (spine AD-15 items 8, 10, 13).

**Steps.**

1. Create the GitHub repo (public, empty). Clone to `/tmp/opencode/$ASSETS_NAME`.
2. Copy the harness **verbatim** from `mu`: `AGENTS.md` (retarget the scope paragraph, keep the
   evidence/worktree/planning-vs-code rules word-for-word), `CLAUDE.md` symlink, `tickets/`
   (`INDEX.md`, `LIFECYCLE.md`, `_template/`, `_fixtures/`), `scripts/worktree-guard.sh`,
   `.agents/skills/`, `skills-lock.json`, `_bmad/`, `.opencode/`, `openspec/` (config from `mu`,
   context retargeted).
3. Add the five class dirs with `.gitkeep` in each (`icons/{templates,mappings}`,
   `templates/`, `configs/`, `content/`, `desktop/{applications,scripts}`).
4. Add `catalog.yaml` — class → directory → "empty in v0.1.0" — with a `schema_major` per schema-
   bearing class. It names **no** spine path (AD-2/AD-6).
5. Add `icons/schema.json` (`schema_major: 1`, group → variants → template path, placeholder
   vocabulary rules) and `templates/README` + one `*.vars.schema.json` template shape
   (`schema_major: 1`, `required[]`, `optional[]`). These are the contracts S1/S3 fill in.
6. `Makefile`: `help validate lint gates hermetic` anchored on `$(CURDIR)`. `validate` runs the
   schema well-formedness check + `catalog.yaml`/class-dir agreement **+ the AD-11 absence check**
   (`icons.json`, any `settings.toml`, any rendered `kitty.conf`/`btop.conf`/`.zshrc` in the tree →
   fail); `lint` runs `shellcheck` over `desktop/scripts/**` (vacuously passes) and
   `python3 -m compileall scripts`; `gates` = `validate lint hermetic`; `hermetic` = the same with
   empty `HOME`/`XDG_*` and a foreign cwd.
7. `README.md` (public surface + how `dotfiles-v3` will pin it, naming no path in another repo),
   `CHANGELOG.md` (`0.1.0 — skeleton`), MIT `LICENSE`.
8. `.github/workflows/gates.yml` with one job per `make gates` target; add `scripts/ci-gates-parity.py`
   (copy from `dotfiles-v3`, retarget) so workflow ⇄ Makefile cannot drift.
9. Green, then release `v0.1.0` (annotated).

**Acceptance gates.**

```bash
cd "/tmp/opencode/$ASSETS_NAME"

# 1. Birth checklist — harness is mu's, byte for byte.
diff -u "$MU/scripts/worktree-guard.sh" scripts/worktree-guard.sh
diff -u "$MU/skills-lock.json" skills-lock.json
# expect: both exit 0, no output

bash scripts/worktree-guard.sh check-clean
# expect: exit 0

rg -c "Evidence:|Verify:" AGENTS.md
# expect: >= 2
test -L CLAUDE.md && echo LINK_OK
rg -c "Gate .*:" tickets/LIFECYCLE.md
# expect: >= 6
python3 _bmad/scripts/memlog.py --help >/dev/null && echo MEMLOG_OK
openspec validate --specs
# expect: exit 0

# 2. Data-only (AD-2).
rg -n '\[project.scripts\]' pyproject.toml 2>/dev/null
# expect: exit 1 (no console script; pyproject may not exist at all)
test ! -d src && echo NO_PACKAGE_ROOT

# 3. The five classes exist and the catalog agrees with them.
ls -d icons templates configs content desktop
python3 scripts/validate-catalog.py
# expect: exit 0; prints the 5 classes and the 2 schema_major values

# AD-11 is mechanical, not a convention: a generated artifact in the tree fails validate.
touch icons/mappings/icons.json && make validate; echo "rc=$?"
# expect: non-zero, naming icons/mappings/icons.json
rm icons/mappings/icons.json

# 4. Fresh clone + gates + build-free release.
cd /tmp/opencode && rm -rf assets-fresh
git clone "$ASSETS_REPO_BASE/$ASSETS_NAME" assets-fresh && cd assets-fresh
make gates
# expect: exit 0 (validate + lint + hermetic)

# 5. Tag exists, annotated, anonymously fetchable.
git ls-remote --tags "$ASSETS_REPO_BASE/$ASSETS_NAME" 'v0.1.0'
# expect: exactly one peeled line (tag object + ^{} commit)
```

**Rollback.** Before any consumer pins it: delete the local tag and the repo (nothing depends on
it). After S1 pins `v0.2.0`: never delete or move `v0.1.0` — ship `v0.1.1`.

**Deletion step.** None in `dotfiles-v3`. S0 touches no host file.

---

## Slice template (applies to S1–S4)

Each class group executes the same loop (AD-16):

1. **Land** the class content in the assets repo, from the current in-tree paths, **byte-identical**
   (`cp -a`, then `git status` shows only additions).
2. **Validate + tag** in the assets repo (`make gates` → `vX.Y.0`).
3. **Rewire** the installer: `dotfiles/provisioning/assets.yaml` `assets.tag` bump +
   `roles/assets/vars/main.yml` mirror + `roles/verify/vars/main.yml` mirror, in one commit.
4. **Prove by execution** — `make gates-ci`, `make deploy-coverage`, the role's unit tests, and (on a
   disposable target) a provision + `dotfiles-provision verify`.
5. **Delete** the in-tree copy *and every reference it orphaned* (role vars, verify mirrors,
   `deploy-coverage` expectations, runtime dev candidates, test fixtures, `.gitignore`, prose) in
   the same slice.
6. **Merge.** The next class waits.

Rollback for every slice: bump `assets.tag` back to the previous tag (or remove the `assets:` block
entirely) and `git revert` the deletion commit. A published tag is never deleted or moved.

---

## S1 — `icons` + `content` → assets `v0.2.0` (first real cut-over)

**Scope.** Move the biggest corpus and the only blobs: 117 SVGs in 12 groups + 8 mapping YAMLs, the
82.6 MB wallpaper tarball, and the (currently empty) authored btop themes. These are the two classes
the **runtime** reads (`derive.py:185-215`), so this slice proves AD-13 end-to-end. It also repoints
the runtime's dev candidates — the one runtime change in the whole split.

**Entry criteria.** S0 merged; assets `v0.1.0` published; `master` green; OPEN-3 answered (tag
cadence; default = release on any change).

**Steps.**

1. Copy verbatim into the assets repo:
   - `dotfiles/assets/icon-templates/` → `icons/templates/` (12 groups, 117 SVGs);
   - `dotfiles/config/icon-template-color-scheme-mappings/` → `icons/mappings/` (8 YAMLs;
     `defaults.yaml` is the `COLOR_*` vocabulary, not a group map — say so in the class README);
   - `dotfiles/assets/wallpapers/wallpapers.tar.gz` → `content/wallpapers/` (**no re-pack** — the
     bytes are the contract; re-packing changes the hash the runtime derives from);
   - `dotfiles/assets/btop-themes/` → `content/btop-themes/` (only `.gitkeep` today).
2. `icons/schema.json`: keep `schema_major: 1`; add the concrete shape the consumer relies on
   (group → `color_mappings` → `variants[{name,template,output}]`, template paths **relative to the
   templates root** — the itr loader joins them under the group's `template_dir` default `.`).
   Add `make validate-icons`: every `template:` in every mapping resolves to a real file under
   `icons/templates/`; every `{{COLOR_*}}` token used by any SVG is declared in `defaults.yaml` or a
   group `color_mappings`; every SVG parses as XML. **This is the gate the corpus has never had** —
   a stale mapping entry is otherwise discovered at render time on a user's machine.
3. `content/`: add `make validate-content` — the tarball contains a top-level `default.png`
   (the installer already asserts this at runtime, `roles/assets/tasks/main.yml:74-88`; the assets
   repo asserts it at release time so a bad tarball cannot be tagged); every `*.theme` is non-empty.
4. Tag `v0.2.0`.
5. In `dotfiles-v3`: add the `assets:` block to `dotfiles/provisioning/assets.yaml`
   (`repo`, `tag: v0.2.0`, `classes` map per AD-6), mirror it in `roles/assets/vars/main.yml`, and
   rewrite the two repo-relative entries to read the checkout:
   `assets_copies` icon-templates/icon-mappings → `<spine>/assets/<tag>/icons/{templates,mappings}`;
   wallpapers → `<spine>/assets/<tag>/content/wallpapers/wallpapers.tar.gz`; btop authored themes →
   `<spine>/assets/<tag>/content/btop-themes/`. Keep `csg-templates` and `weg-effects` exactly as
   they are (AD-14).
6. Add the fetch step to `roles/assets/tasks/main.yml` **before** every copy: shallow clone
   `repo@tag` → `<spine>/assets/<tag>/`, `rm -rf .git`, write `<spine>/assets/pinned`, then the
   existing stat/assert-before-copy discipline. (Shape to copy:
   `roles/assets/tasks/main.yml:112-136`.)
7. Mirror in `roles/verify/vars/main.yml`: `<spine>/assets/pinned`, the class dirs, and the same
   required-member sets already asserted (`verify_asset_dirs`, `verify_asset_files` — these need no
   path change, which is the point of AD-7).
8. Repoint the runtime dev candidates in `derive.py:185-215`: `dotfiles/assets/icon-templates` →
   `icons/templates`, `dotfiles/config/icon-template-color-scheme-mappings` → `icons/mappings`
   (relative to `DOTFILES_DEV_INPUTS_ROOT`, which now means "an assets checkout"). Update
   `src/runtime/tests/unit/test_derive_input_provenance.py`'s fixture layout to match.
9. Repoint `src/runtime/tests/integration/conftest.py:87-105` (`resolve_icon_templates_dir`), which
   currently hard-codes `dotfiles/assets/icon-templates` as the live source: resolve from the
   provisioned spine, else the assets checkout via `DOTFILES_ICON_TEMPLATES_DIR`, else skip loudly.
10. Delete the four in-tree sources.

**Acceptance gates.**

```bash
cd "$WT"

# 1. The assets repo is green and tagged.
git clone "$ASSETS_REPO_BASE/$ASSETS_NAME" /tmp/opencode/assets-s1 && cd /tmp/opencode/assets-s1
make gates
# expect: exit 0 — validate-icons (every mapping template resolves), validate-content (default.png
#         present in the tarball), lint, hermetic
git ls-remote --tags origin 'v0.2.0'
# expect: one peeled line

# 2. Byte-identical import: nothing was re-encoded.
cd "$WT"
git -C /tmp/opencode/assets-s1 show v0.2.0:content/wallpapers/wallpapers.tar.gz | sha256sum
sha256sum dotfiles/assets/wallpapers/wallpapers.tar.gz    # (pre-deletion, or from the merge base)
# expect: identical hashes
diff -r dotfiles/assets/icon-templates /tmp/opencode/assets-s1/icons/templates
diff -r dotfiles/config/icon-template-color-scheme-mappings /tmp/opencode/assets-s1/icons/mappings
# expect: both exit 0 (run BEFORE step 10)

# 3. Manifest + mirrors agree (AD-6).
rg -n 'tag: v0\.2\.0' dotfiles/provisioning/assets.yaml src/provisioning/ansible/roles/assets/vars/main.yml src/provisioning/ansible/roles/verify/vars/main.yml
# expect: >= 3 matches, same tag
uv run --directory src/provisioning pytest tests/unit/test_assets_role.py tests/unit/test_verify_role.py -q
# expect: exit 0 (parity tests green after both mirrors move together)

# 4. Provisioning shape.
make deploy-coverage && make gates-ci
# expect: exit 0

# 5. Proved by execution on a disposable target (local-only, needs incus).
dev/vm-fresh.sh && dev/vm-verify
# PLANNED. expect: exit 0; verify passes the asset criteria (criterion 4 + the icons criterion)
# and the runtime renders icons from the spine after `runtime_seed`.

# 6. The runtime reads the SPINE, not a checkout.
env -u DOTFILES_DEV_INPUTS_ROOT uv run --directory src/runtime python -c "
from pathlib import Path
from runtime.application.derive import resolve_input
p, src = resolve_input('icon_templates', Path('$SPINE'))
print(p, src); assert src == 'spine', src
"
# expect: <spine>/icon-templates spine

# 7. Deletion proof.
test ! -e dotfiles/assets/icon-templates && test ! -e dotfiles/config/icon-template-color-scheme-mappings \
  && test ! -e dotfiles/assets/wallpapers && test ! -e dotfiles/assets/btop-themes \
  && echo "FOUR SOURCES ABSENT"
git ls-files dotfiles/assets dotfiles/config/icon-template-color-scheme-mappings
# expect: empty
```

**Rollback.** Bump `assets.tag` back / remove the `assets:` block, revert the deletion commit,
restore the four trees from the merge base. Published tags stay.

**Deletion step.** `git rm -r dotfiles/assets/icon-templates dotfiles/config/icon-template-color-scheme-mappings dotfiles/assets/wallpapers dotfiles/assets/btop-themes`;
remove `dotfiles/assets/` when empty; repoint the runtime dev candidates + integration conftest; update
`ARCHITECTURE.md` §5/§6.5 and `docs/Adding an Icon — ITR and Provisioning Pipeline.md`; add a
`deploy-coverage` assertion that `dotfiles/assets/` does not exist (AD-16 catch-all).

---

## S2 — `configs` → assets `v0.3.0`

**Scope.** Move the static skeleton corpus: 13 hypr Lua files, `hyprpaper.conf`,
`rofi/launcher/config.rasi`, `wlogout/layout`, 8 nvim files, `starship.toml` (25 files). No runtime
reads these directly — they are read by the compositor, nvim, starship and rofi at session time
through `~/.config/<name>` symlinks. OPEN-2 decides whether `content` folds into `configs`; this
slice proceeds with them separate.

**Entry criteria.** S1 merged; assets `v0.2.0`; `master` green; **OPEN-5 answered** for
`btop/active-theme` (it must not be copied as config — see step 4).

**Steps.**

1. Copy verbatim into `configs/`: `dotfiles/config/hypr/*.lua` (13), `hyprpaper/hyprpaper.conf`,
   `rofi/launcher/config.rasi`, `wlogout/layout`, `nvim/**` (8), `starship/starship.toml`.
2. **Do not copy** `dotfiles/config/zsh/.zshrc.j2` (templates class, S3), `dotfiles/config/wlogout/style.css.tpl`
   (templates class, S3 — it is a Jinja template with 5 vars), or `dotfiles/config/btop/*`
   (`active-theme` is a mutable preference, AD-11/OPEN-5; themes are `content`).
3. Tag `v0.3.0`.
4. Rewire `roles/compositor_configs` (`compositor_configs_skeleton_files`, 15 entries) and
   `roles/config_copies` (`config_copies_entries`: nvim, starship, wlogout, zsh) to read
   `<spine>/assets/<tag>/configs/…`. Keep every `dest` byte-identical (AD-7). Note the split
   consequence: the `wlogout` copy entry now supplies `layout` only (its `style.css.tpl` arrives
   with S3's render), so the directory copy becomes a per-file copy for wlogout — record the change
   in the role header.
5. Bump both verify mirrors (`verify_compositor_skeleton_files:493-507`,
   `verify_config_copies_targets:820-825`, `verify_config_copy_content:834-840` — no path change,
   only the source; the lists stay).
6. Delete the in-tree config tree **except** what S3/S4 still need (`zsh/.zshrc.j2`,
   `wlogout/style.css.tpl`, `btop/active-theme` if S7 has not moved it yet).

**Acceptance gates.**

```bash
cd "$WT"

git clone "$ASSETS_REPO_BASE/$ASSETS_NAME" /tmp/opencode/assets-s2 && cd /tmp/opencode/assets-s2
make gates
# expect: exit 0
git ls-remote --tags origin 'v0.3.0'
# expect: one peeled line

cd "$WT"
# Byte-identical import of the static set.
diff -r dotfiles/config/hypr /tmp/opencode/assets-s2/configs/hypr
diff -r dotfiles/config/nvim /tmp/opencode/assets-s2/configs/nvim
# expect: exit 0 (before deletion)

# Skeleton registration still complete (AGENTS.md §2) — the list is unchanged, its source moved.
uv run --directory src/provisioning pytest tests/unit/test_compositor_configs_role.py \
  tests/unit/test_compositor_skeleton_configs.py tests/unit/test_config_copies_role.py -q
# expect: exit 0

make deploy-coverage && make gates-ci
# expect: exit 0

dev/vm-fresh.sh && dev/vm-verify
# PLANNED. expect: exit 0; the three compositor dirs + nvim/starship/wlogout resolve through the
# ~/.config symlinks and every skeleton file is present in the spine.

test ! -e dotfiles/config/hypr && test ! -e dotfiles/config/hyprpaper \
  && test ! -e dotfiles/config/rofi && test ! -e dotfiles/config/nvim \
  && test ! -e dotfiles/config/starship && echo "CONFIGS ABSENT"
test -e dotfiles/config/zsh/.zshrc.j2 && test -e dotfiles/config/wlogout/style.css.tpl \
  && echo "S3 SOURCES STILL PRESENT"
ls -A dotfiles/config
# expect: only what S3/S4 still own (zsh, wlogout, btop)
```

**Rollback.** Pin bump back + revert the deletion commit.

**Deletion step.** Remove the six static config dirs; update `ARCHITECTURE.md` §5/§6.6;
`docs/02-config-in-spine-pattern.md` (its "configs are copied from the repo" sentence now names the
assets pin); extend `deploy-coverage` with an absence guard for the deleted dirs.

---

## S3 — `templates` → assets `v0.4.0` (vars schemas + strict render)

**Scope.** Move every Jinja source and give each one a vars schema: zsh `.zshrc.j2` (11 vars), kitty
`kitty.conf.j2` (1), btop `btop.conf.j2` (1), wlogout `style.css.tpl` (5), display-manager ×5
(1–3 each). This is the slice that makes AD-8 and AD-9 executable.

**Entry criteria.** S2 merged; assets `v0.3.0`; `master` green. The DM template move is pre-agreed
(AD-9) — the installer keeps selection/packages/enablement.

**Steps.**

1. Copy the five template groups into `templates/` with their sources' **current Jinja bodies
   unchanged** (`dotfiles/config/zsh/.zshrc.j2`, `dotfiles/config/wlogout/style.css.tpl`, the
   role-internal `kitty.conf.j2` / `btop.conf.j2` / DM templates).
2. Write one `*.vars.schema.json` per template: `schema_major: 1`, `required[]` (name + type),
   `optional[]`. Derive `required[]` from what the template actually consumes — not from the role's
   full var set.
3. `make validate-templates`: every `*.j2`/`*.tpl` has a sibling schema; every `{{ var }}` in a
   template appears in its schema; **no `default(` on a required var** (grep-level rule, the AD-8
   guard); every schema is valid JSON Schema and its `required[]` is non-empty.
4. Tag `v0.4.0`.
5. Installer: point the five roles' `template:` sources at `<spine>/assets/<tag>/templates/…`
   (`zsh_config.tasks:59-62`, `kitty_config.tasks:43-46`, `btop_config.tasks:75-78`,
   `wlogout_config.tasks:36-37`, `display_manager.tasks:62-68,96-102`). Keep every supplied var and
   every `dest` unchanged.
6. Add the **required-var parity test** (AD-8.4) in the installer repo: for each assets template it
   renders, every schema `required[]` name is supplied by that role's render task. Static, offline.
7. `display_manager`: keep `display_manager_type`, packages, Pixie pin, enablement, the
   login-timeout patch and every `become`; only the five `src:` values move.
8. Delete the in-tree sources.

**Acceptance gates.**

```bash
cd "$WT"

git clone "$ASSETS_REPO_BASE/$ASSETS_NAME" /tmp/opencode/assets-s3 && cd /tmp/opencode/assets-s3
make gates
# expect: exit 0 — validate-templates reports 10 templates, 10 schemas, 0 defaults on required vars
git ls-remote --tags origin 'v0.4.0'
# expect: one peeled line

cd "$WT"
# Every required var is supplied — the new parity test, proving AD-8.4.
uv run --directory src/provisioning pytest tests/unit/test_settings_role.py \
  tests/unit/test_zsh_config_role.py tests/unit/test_kitty_config_role.py \
  tests/unit/test_btop_config_role.py tests/unit/test_wlogout_config_role.py \
  tests/unit/test_display_manager_role.py -q
# expect: exit 0

# The rendered artifacts are correct on a real target.
dev/vm-fresh.sh && dev/vm-verify
# PLANNED. expect: exit 0; verify checks zsh/.zshrc, kitty/kitty.conf, btop/btop.conf (the two pinned
# values), wlogout/style.css, and the DM conf; the .zshrc include path resolves to the existing
# <state>/dotfiles/current/colors.sequences.

make deploy-coverage && make gates-ci
# expect: exit 0

test ! -e dotfiles/config/zsh && test ! -e dotfiles/config/wlogout/style.css.tpl \
  && echo "TEMPLATE SOURCES ABSENT"
rg -n 'templates/' src/provisioning/ansible/roles/*/tasks/main.yml | grep -c assets
# expect: >= 5 (the five render tasks now read the checkout)
```

**Rollback.** Pin bump back + revert. The DM rollback is safe in isolation because the installer
tasks keep identical vars and dests — this is why AD-9 forbids splitting the DM concern.

**Deletion step.** Remove the template sources; update `roles/*/vars` header comments that say "the
template lives in the repo"; update `ARCHITECTURE.md` §6.5 and the `docs/` guide that names
`dotfiles/config/zsh/.zshrc.j2`; extend `deploy-coverage`.

---

## S4 — `desktop` → assets `v0.5.0` (three validation layers)

**Scope.** Move the 6 `.desktop` entries and `toggle-touchpad`, add `desktop/desktop.yaml` with
`requires`/`optional`, add `TryExec` to each entry, and land the three layers of AD-10. Last corpus
slice; after this the assets repo is complete.

**Entry criteria.** S3 merged; assets `v0.4.0`; `master` green; a container engine available (the
package presence check needs a real host or the disposable VM).

**Steps.**

1. Copy `dotfiles/applications/*.desktop` (6) → `desktop/applications/`, and
   `dotfiles/scripts/toggle-touchpad` → `desktop/scripts/` (`mode 0755` preserved).
2. Add `TryExec=` to each entry (the binary `Exec` launches: `antigravity-ide`, `code`,
   `devin-desktop`, `kitty`, `tidal-hifi`) — layer 1 depends on it.
3. `desktop/desktop.yaml`: per entry `{file, requires: [binaries], optional: [binaries]}`. Derive
   from the `Exec` line + `desktop/scripts`. `clone`-style entries (`copilot`, `codex`) require
   `kitty`; the IDE overrides require their own binary.
4. `make validate-desktop` (layer 1): every `.desktop` parses (`configparser`, `[Desktop Entry]`,
   `Type`, `Name`, `Exec`), `Exec`'s argv[0] is absolute or in `requires`, `TryExec` present and in
   `requires`, `Icon` non-empty; `shellcheck desktop/scripts/*`; `desktop.yaml` agrees with the
   `.desktop` set exactly.
5. Tag `v0.5.0`.
6. Installer: `roles/compositor_configs` reads `desktop/applications/*.desktop` and
   `desktop/scripts/toggle-touchpad` from the checkout; per-entry `requires`/`optional` resolution
   (layer 2) runs before the copy — a missing **required** binary fails, a missing optional is
   skipped with a message.
7. `verify` (layer 3): keep the deployed-set assertions, add "every `Exec` binary resolves on
   `PATH`" and "every hypr-keybind-invoked script/launcher exists and is executable"
   (`rofi-ui`, `capture-ui`, `hypr-pano-ui`, `wallpaper-selector-ui`,
   `icon-color-mapping-editor`, `btop-theme-studio`, `toggle-touchpad` — the six installers stay in
   `cli_tools`, AD-10 scope boundary).
8. Delete `dotfiles/applications/` and `dotfiles/scripts/`.

**Acceptance gates.**

```bash
cd "$WT"

git clone "$ASSETS_REPO_BASE/$ASSETS_NAME" /tmp/opencode/assets-s4 && cd /tmp/opencode/assets-s4
make gates
# expect: exit 0 — validate-desktop reports 6 entries, 6 with TryExec, 1 script shellcheck-clean
git ls-remote --tags origin 'v0.5.0'
# expect: one peeled line

# Layer 1 is not vacuous: break one entry and watch it fail.
cp desktop/applications/code.desktop /tmp/opencode/code.bak
sed -i 's/^Exec=.*/Exec=definitely-not-installed --flag %F/' desktop/applications/code.desktop
make validate-desktop; echo "rc=$?"
# expect: non-zero, naming code.desktop and definitely-not-installed
cp /tmp/opencode/code.bak desktop/applications/code.desktop

cd "$WT"
uv run --directory src/provisioning pytest tests/unit/test_compositor_configs_role.py \
  tests/unit/test_verify_role.py -q
# expect: exit 0 (layer 2 + layer 3 mirrors)

dev/vm-fresh.sh && dev/vm-verify
# PLANNED. expect: exit 0; the six entries are in $XDG_DATA_HOME/applications, toggle-touchpad is
# 0755 and on PATH, and the keybind-script assertion passes.

make deploy-coverage && make gates-ci
# expect: exit 0

test ! -e dotfiles/applications && test ! -e dotfiles/scripts && echo "DESKTOP SOURCES ABSENT"
```

**Rollback.** Pin bump back + revert. If layer 2 proves too strict on a package-less target, demote
that binary to `optional` in `desktop.yaml` and ship a PATCH — not a rollback.

**Deletion step.** Remove `dotfiles/applications/`, `dotfiles/scripts/`; update
`roles/compositor_configs/vars/main.yml` header (it currently says the entries are authored under
`dotfiles/applications/`); update `ARCHITECTURE.md` §5; extend `deploy-coverage`; add the assets repo
to the `docs/` pin table.

---

## S5 — Runtime/verify contract assertions (schema_major support window)

**Scope.** Make AD-12 executable: the installer refuses an out-of-window `schema_major` **before** it
deploys anything, and `verify` re-asserts the deployed corpus's schema versions. No corpus moves. If
OPEN-4 forces a wider window, this slice ships assets `v0.6.0`; otherwise no new tag.

**Entry criteria.** S4 merged; assets `v0.5.0`; `master` green; **OPEN-4 answered** (default: accept
exactly one major).

**Steps.**

1. Add `assets_schema_support` to `roles/assets/vars/main.yml` (per class: the accepted
   `schema_major`), mirrored by the manifest and by `verify`.
2. Fetch task: after the clone, read `<checkout>/icons/schema.json` and each
   `<checkout>/templates/**/*.vars.schema.json`, and `assert` every `schema_major` is in the support
   window — before the first copy, with the file path and the expected window in `fail_msg`.
3. `verify`: re-read the deployed corpus's schemas from `<spine>/assets/<tag>/` and assert the same
   window; assert `<spine>/assets/pinned` equals the manifest tag.
4. Extend `deploy-coverage` with the assets shape (this is a **new** assertion — the current gate has
   none; `grep -c "assets.yaml\|roles/assets" scripts/deploy-coverage.py` → 0): manifest has `repo`
   + a semver `tag`; role and verify mirrors agree; `assets/` has no per-class `source:` pointing
   into `dotfiles/`; the retired corpus dirs are absent.
5. Negative tests: a checkout whose `schema_major` is too high fails the fetch assert; a `pinned`
   file with the wrong tag fails verify.

**Acceptance gates.**

```bash
cd "$WT"

# Support window is enforced before any copy.
uv run --directory src/provisioning pytest tests/unit/test_assets_role.py -q -k schema
# expect: exit 0, including the two negative cases

uv run --directory src/provisioning pytest tests/unit/test_verify_role.py -q -k assets
# expect: exit 0

# Negative test is real, not asserted in prose: point the pin at the previous tag (older schema)
# and watch the assert name the file.
rg -n 'assets_schema_support' src/provisioning/ansible/roles/{assets,verify}/vars/main.yml
# expect: >= 2 matches

make deploy-coverage && make gates-ci
# expect: exit 0; deploy-coverage now prints the assets pin and the five class dirs
dev/vm-fresh.sh && dev/vm-verify
# PLANNED. expect: exit 0; verify asserts <spine>/assets/pinned == the manifest tag
```

**Rollback.** Revert the slice; the corpus is untouched, so rollback is a normal branch revert with
no pin consequence.

**Deletion step.** None (nothing is deleted). This slice only adds assertions — which is why it is
separate from S1–S4: a schema check bundled into the first cut-over would have been untestable
against the skeleton corpus.

---

## S6 — Extract the installer engine out of `dotfiles-v3`

**Scope.** Move `src/provisioning/` (the `dotfiles-provision` engine, its Ansible roles and
playbooks, its tests) into its own mu-strict repo, and make it accept the **composition repo's**
manifests and inventory from outside its own checkout (AD-17). This is the only code extraction in
this change.

**Entry criteria.** S5 merged; assets `v0.5.0` (or `.6`); `master` green; the installer repo's name
answered (same owner/visibility decision as OPEN-1); a container engine available.

**Steps.**

1. Birth the repo (13 items, AD-15 — items 8/10/13 are the **code-repo** shape here, not the data
   shape). Import `src/provisioning/{pyproject.toml,src,tests,uv.lock}` as the repo root, history via
   `git subtree split -P src/provisioning`.
2. Move the Ansible tree (`ansible/` with 21 roles + 23 playbooks) as the repo's own tree. Its
   tests move with it (`tests/unit/*_role.py`, `tests/architecture/test_layering.py`).
3. **The seam.** Replace all **8** `{{ playbook_dir }}/../../../..` derivations with a single
   `manifests_dir` / `composition_root` extra-var resolved once in the engine CLI and passed down:
   `roles/assets/vars/main.yml:19`, `roles/compositor_configs/vars/main.yml:25`,
   `roles/config_copies/vars/main.yml:45`, `roles/btop_config/vars/main.yml:57`,
   `roles/cli_tools/vars/main.yml:8`, `roles/gui_tools/vars/main.yml:80`,
   `roles/zsh_config/vars/main.yml:19`, `roles/wlogout_config/vars/main.yml:10`.
   This is the load-bearing step: after the split the roles read the **assets checkout**, not a
   composition checkout, so every remaining `repo_root` reference must be re-derived or deleted.
4. Keep `cli-output` as a git-tag pin (`pyproject.toml:24-25`); no path pins (the extraction rule).
5. The composition repo keeps `dotfiles/provisioning/*.yaml`, `ansible/inventory/`, `group_vars/`,
   and passes them via `--manifests-dir` / `--inventory`. Record the exact flag in both READMEs.
6. `bootstrap.sh` stays in the composition repo and calls the installed `dotfiles-provision`
   (`uv tool install` from the tag), not `uv run --directory src/provisioning`.
7. Tag installer `v0.1.0`; pin it in the composition repo (`cli-tools.yaml` `dotfiles-runtime`-style
   entry, or a dedicated `installer:` block — decide once, mirror once).
8. Delete `src/provisioning/` and its tests from `dotfiles-v3`; keep `src/runtime/`.

**Acceptance gates.**

```bash
cd /tmp/opencode && rm -rf provision && git clone "$ASSETS_REPO_BASE/dotfiles-provision" provision
cd provision && make sync && make gates && make hermetic && uv lock --check && uv build
# expect: exit 0; dist/ has the sdist + wheel
git ls-remote --tags origin 'v0.1.0'
# expect: one peeled line

# The seam: the engine provisions from a foreign manifests dir (the composition checkout).
cd "$WT"
uv run --directory /tmp/opencode/provision dotfiles-provision verify \
  --manifests-dir "$WT/dotfiles/provisioning" --install-dir "$SPINE"
# PLANNED (exact flag name lands with step 3). expect: exit 0; it reads the assets pin from the
# composition repo and asserts the deployed corpus

# Composition repo is now runtime + pins only.
test ! -e src/provisioning && echo "ENGINE EXTRACTED"
git ls-files src | sed 's#/.*##' | sort -u
# expect: only src/runtime
make gates-ci && make deploy-coverage
# expect: exit 0 (the composition gate set must be re-pointed at the pinned engine first)

dev/vm-fresh.sh && dev/vm-verify
# PLANNED. expect: exit 0 — the full bootstrap from `bootstrap.sh` using the pinned engine.
```

**Rollback.** Revert the deletion commit and restore `src/provisioning/` from the merge base; revert
the pin. The published installer tag stays. Because `bootstrap.sh` changes in the same slice as the
deletion, a half-rollback is not a valid state — revert both commits together.

**Deletion step.** `git rm -r src/provisioning`; re-point `Makefile` (`contracts-check` and the
`uv run --directory src/provisioning` gates move to the pinned engine or become engine-repo gates);
update `AGENTS.md` §2 (it currently says "the only in-repo Python is `src/runtime/` and
`src/provisioning/`"), `ARCHITECTURE.md` §2/§5/§9, and `scripts/deploy-coverage.py`'s
`assert_manifest_source_scope` (the one permitted local `source:` — `dotfiles-runtime` — is now
joined by the installer pin, or by a separate `installer:` block that the gate learns).

---

## S7 — `dotfiles-v3` closeout as the composition repo

**Scope.** No corpus and no engine moves. This slice finishes the charter (AD-17): finalize pins,
delete the last orphaned references, add the composition gates that assert the repo is a composition
repo, and make the docs true.

**Entry criteria.** S6 merged; installer `v0.1.0`; assets at the latest tag; `master` green.

**Steps.**

1. Finalize the pin set in one place: `dotfiles/provisioning/*.yaml` (+ a documented `installer:`
   block if S6 created one). Every pin semver-tagged; no `path`/`editable` pin anywhere.
2. Composition gates: extend `deploy-coverage` with a catch-all — `dotfiles/assets/`,
   `dotfiles/config/` (except files S7 still owns, if any), `dotfiles/applications/`,
   `dotfiles/scripts/`, `src/provisioning/` absent; exactly the permitted local `source:` entries;
   the assets/installer pins mirrored in role + verify.
3. `make gates-ci` must remain six targets (`Makefile:61-63`); `ci-gates-parity` must stay green
   with the same workflow job set (`.github/workflows/gates.yml`), or a declared `RENAMES` entry.
4. Add the missing product metadata the closeout exposes: `dotfiles-v3` has **no `LICENSE` and no
   `CHANGELOG.md`** today (`ls LICENSE CHANGELOG.md` → exit 2). A composition repo that pins seven
   repos needs at least its own license statement.
5. Docs: `ARCHITECTURE.md` (sections 2, 4, 5, 6.5–6.6, 9, 10.1, 11, 12), `docs/02-config-in-spine-pattern.md`,
   `docs/Adding an Icon — …`, the pin table, and a new `openspec/specs/assets-repo-consumption/spec.md`.
6. Archive the change: `openspec/changes/archive/<date>-assets-split/` + a `POST-MIGRATION.md` in
   the precedent's shape (command + observed result per claim).

**Acceptance gates.**

```bash
cd "$WT"

make gates-ci
# expect: exit 0, six gates
make deploy-coverage
# expect: exit 0; prints the assets pin, the installer pin, the seven repo pins, and zero local
#         corpus sources

# The repo authors no corpus and no engine.
test ! -e src/provisioning && test ! -e dotfiles/assets && test ! -e dotfiles/applications \
  && test ! -e dotfiles/scripts && echo "COMPOSITION-ONLY"
git ls-files src | sed 's#/.*##' | sort -u
# expect: only src/runtime

# No path/editable pin survives.
rg -n 'path = "\.\.|editable = true' --glob 'pyproject.toml' .
# expect: exit 1

# Every pin is a semver tag.
rg -n 'tag = "v[0-9]+\.[0-9]+\.[0-9]+"|tag: v[0-9]+\.[0-9]+\.[0-9]+' src dotfiles/provisioning
# expect: every pin line matches; no `latest`, no branch name

# Fresh machine, end to end.
dev/vm-fresh.sh && dev/vm-verify
# PLANNED. expect: exit 0 — bootstrap.sh installs the pinned engine, which fetches the pinned assets
# and provisions the host; verify passes all done-criteria.

# Docs are not lying.
rg -n 'src/provisioning|dotfiles/assets/icon-templates' AGENTS.md ARCHITECTURE.md
# expect: exit 1 (prose updated) — historical dirs _bmad-output/ and openspec/changes/archive/ excluded
```

**Rollback.** Revert the slice; pins are additive, so a revert returns the previous pin set.

**Deletion step.** Remove the last orphaned references the corpus/engine deletions left in prose and
`.gitignore`; this is the terminal catch-all commit (the precedent's terminal-absence-guard shape).

---

## Post-migration verification (after S7 merges)

```bash
cd "$DTF"
make gates-ci && make deploy-coverage
# expect: exit 0

# One corpus, one pin, five classes, deployed once per tag.
ls -d "$SPINE/assets/"* | sort
cat "$SPINE/assets/pinned"
# expect: one tag dir + `pinned` holding the same tag
for c in icons templates configs content desktop; do test -d "$SPINE/assets/$(cat "$SPINE/assets/pinned")/$c" || echo "MISSING $c"; done
# expect: no output

# The runtime reads the spine and nothing else.
env -u DOTFILES_DEV_INPUTS_ROOT uv run --directory src/runtime python -c "
from pathlib import Path
from runtime.application.derive import input_provenance
prov = input_provenance(Path('$SPINE'))
assert all(src != 'repo' for _, src in prov.values()), prov
print(prov)
"
# expect: exit 0; every input 'spine' or (for weg_effects) present after runtime_seed

# The three repos this change touches exist and are pinned.
git ls-remote --tags "$ASSETS_REPO_BASE/$ASSETS_NAME" | tail -3
git ls-remote --tags "$ASSETS_REPO_BASE/dotfiles-provision" 'v0.1.0'
# expect: one line for the installer, the assets tag list ending at the pinned tag

# No returned tree.
test ! -e dotfiles/assets && test ! -e src/provisioning && echo "RETIRED TREES ABSENT"
```

If any command contradicts the expected observable, the migration is not done — the gate is
execution, not this document.
