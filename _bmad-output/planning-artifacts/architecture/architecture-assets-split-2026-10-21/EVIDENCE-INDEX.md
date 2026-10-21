# Evidence Index — one row per spine decision

Every row names the file:line or the command that supports the decision. The **Reproduce** column is
either a command **run by the author of this plan** (`[ran]`, with its observed output below) or a
release-time gate that has **not** been run (`[PLANNED]`). A decision whose evidence is a *design
consequence* rather than an observed fact says so in its own table at the end.

Working dir for every command: the `ticket/assetssplit-spine-and-slices` worktree
(`.worktrees/assetssplit`, base `23d5e9dc`).

| Decision | Evidence pointer | Reproduce |
| --- | --- | --- |
| AD-1 five entities, one-way graph | `src/runtime/tests/architecture/test_layering.py:104-111` (`_FORBIDDEN_CROSS_PACKAGE` = provisioning/core/infrastructure); `src/runtime/src/runtime/application/derive.py:12-13` (spine-only); `dotfiles/provisioning/cli-tools.yaml:8-15` (the existing pinned-install shape); `roles/runtime_daemon/tasks/main.yml` (artifact install) | `sed -n '100,115p' src/runtime/tests/architecture/test_layering.py` [ran] |
| AD-2 assets is data-only | the two engines that must *not* be duplicated: `src/runtime/pyproject.toml:15`, `src/provisioning/pyproject.toml:14` (`[project.scripts]`); `ARCHITECTURE.md:313` (csg generate), `:318` (itr render) | `rg -n '\[project.scripts\]' src/*/pyproject.toml` [ran] → exactly 2 (runtime, provisioning) |
| AD-3 one repo / five class dirs / one tag | measured corpus: 117 SVGs / 12 groups, 8 mapping YAMLs, 13 hypr Lua, 8 nvim files, 6 `.desktop`, 1 script, empty `btop-themes/`, 82 656 450-byte tarball | the `Measured inventory` block below [ran] |
| AD-4 semver = the deployment pin | consumers address content by literal path: `roles/compositor_configs/vars/main.yml:110-125` (15 per-file skeleton entries), `dotfiles/provisioning/assets.yaml:9-17`, `roles/verify/vars/main.yml:493-507` | `rg -c '^  - \{ name:' src/provisioning/ansible/roles/compositor_configs/vars/main.yml` [ran] → 22 total across the 3 lists (15 skeleton + 1 script + 6 desktop) |
| AD-5 fetch once into `<spine>/assets/<tag>/` | the pinned-checkout precedent: `roles/assets/vars/main.yml:67-69` (`assets_csg_pinned_tag` + path), `roles/assets/tasks/main.yml:112-136` (stat/assert then synchronize), `ARCHITECTURE.md:198-203` (`cli-tools/<name>/<tag>/` + `pinned`) | `sed -n '112,136p' src/provisioning/ansible/roles/assets/tasks/main.yml` [ran] |
| AD-6 manifest is the single source of truth | `dotfiles/provisioning/assets.yaml:1-33`; the hand-maintained role mirror `roles/assets/vars/main.yml:92-102`; parity anchor `src/provisioning/tests/unit/test_assets_role.py:30-31` (`_MANIFEST_PATH`) | `sed -n '28,32p' src/provisioning/tests/unit/test_assets_role.py` [ran] |
| AD-7 split moves the source, never the destination | `roles/verify/vars/main.yml:415-437` (`verify_asset_dirs`/`_files`), `:493-507` (skeletons); runtime candidates `derive.py:185-200`; deploy targets `roles/assets/vars/main.yml:38-43,47,51,117` | `sed -n '415,440p' src/provisioning/ansible/roles/verify/vars/main.yml` [ran] |
| AD-8 template render contract | `roles/kitty_config/templates/kitty.conf.j2:2` (absolute include); `roles/zsh_config/tasks/main.yml:59-74` (11 vars); `roles/settings/tasks/main.yml:45-57` (the seam assert); `dotfiles/config/wlogout/style.css.tpl` (5 vars) | `grep -oE '\{\{[^}]+\}\}' dotfiles/config/wlogout/style.css.tpl \| sort -u` [ran] → 5 names; `for f in src/provisioning/ansible/roles/display_manager/templates/*; do …` [ran] → 1/0/0/3/1 vars |
| AD-9 DM templates move, DM policy stays | `roles/display_manager/vars/main.yml:20-49` (type, packages, Pixie pin, conf paths); `roles/display_manager/tasks/main.yml:26-68` (install→fetch→patch→render), `:112-131` (enable/disable) | `sed -n '20,49p' src/provisioning/ansible/roles/display_manager/vars/main.yml` [ran] |
| AD-10 desktop validation, three layers | 6 entries with **no `TryExec`** (`dotfiles/applications/*.desktop`); 7 keybind-invoked script names of 9 `exec_cmd` targets (`dotfiles/config/hypr/keybindings.lua:34,44,51,71,80,532`; the other two are `kitty`, `thunar`); the one repo-authored script `roles/compositor_configs/vars/main.yml:131-132`; the 6 rendered wrappers `roles/cli_tools/tasks/main.yml:48-90`; existing gate `roles/verify/vars/main.yml:60-79` | `grep -hE '^(Name\|Exec\|TryExec)=' dotfiles/applications/*.desktop \| cut -d= -f1 \| sort \| uniq -c` [ran] → `6 Exec`, `6 Name`, **0 `TryExec`** |
| AD-11 generated/mutable never assets | `roles/compositor_configs/tasks/main.yml:91-105` (icons.json generated twice); `roles/settings/vars/main.yml:113-116`; `roles/btop_config/vars/main.yml:59-63` + `tasks:52-63` (active-theme read); `dotfiles/config/btop/active-theme` | `find dotfiles -name 'icons.json' -o -name 'settings.toml' \| wc -l` [ran] → 0 (nothing generated is committed — the rule preserves that) |
| AD-12 schema versions ≠ repo tag | **no schema file exists**: `find dotfiles -iname '*schema*' -o -iname '*vocab*'` → 0 hits. The working analogue: `ARCHITECTURE.md:412` (`contract_version` in the JSON) + `:422-424` (same-tag rule); `roles/compositor_configs/vars/main.yml:175-190` (`schemaVersion` stamped at generation) | `find dotfiles -iname '*schema*' -o -iname '*vocab*'` [ran] → no output (exit 0, 0 lines) |
| AD-13 runtime consumes only the spine | `derive.py:123` (`_DEV_INPUTS_ROOT_ENV`), `:128-133` (the 4 input names), `:146-200` (spine + repo candidates), `:196-235` (`resolve_input`), `:219-235` (`require_input` error); tripwire `src/runtime/src/runtime/application/doctor.py:125`; tests `src/runtime/tests/unit/test_derive_input_provenance.py:99-152` | `rg -n 'DOTFILES_DEV_INPUTS_ROOT' src/runtime/src/runtime/application/` [ran] → `derive.py:13,123,203` + `doctor.py:125` |
| AD-14 three excluded corpora | csg templates are an **absolute checkout path** by design: `dotfiles/provisioning/assets.yaml:18-28`, `roles/assets/vars/main.yml:53-69,96-102`; AGS unit deployment `roles/ags_apps/vars/main.yml:1-90`; `ARCHITECTURE.md:241-247` | `sed -n '18,28p' dotfiles/provisioning/assets.yaml` [ran] |
| AD-15 mu-strict 13-item birth | `mu/AGENTS.md:5-13` (evidence rule), `:28` (worktree rule); `mu/tickets/LIFECYCLE.md` (6 gate one-liners); `mu/skills-lock.json` → 7 skills; `mu/scripts/worktree-guard.sh` sha256 `b059ea803bd104ee80b6ec79b85ad6d73e9a2d7c57bb1717203411c4c6cfafc2`; `openspec/specs/cli-repo-birth/spec.md:1-40` | `python3 -c "import json;print(len(json.load(open('/home/inumaki/Development/mu/skills-lock.json'))['skills']))"` [ran] → 7; `sha256sum /home/inumaki/Development/mu/scripts/worktree-guard.sh` [ran] |
| AD-16 destructive-last per class | the silent-no-op hazard is documented in the role: `roles/assets/tasks/main.yml:26-32` ("synchronize against a missing src copies nothing"); the absence-guard shape to copy: `scripts/deploy-coverage.py:1360-1398` | `sed -n '1360,1398p' scripts/deploy-coverage.py` [ran] |
| AD-17 `dotfiles-v3` becomes composition-only | one local `source:` is gated today: `scripts/deploy-coverage.py:1771-1819` (`assert_manifest_source_scope`), `:1752-1768` (`assert_no_cli_tools_dir`); `AGENTS.md` §2; the **8** `{{ playbook_dir }}/../../../..` derivations that must become a seam | `rg -n 'playbook_dir \}\}/\.\./\.\./\.\./\.\.' src/provisioning/ansible/roles/*/vars/main.yml \| grep -v '^.*#'` [ran] → 8 assignments |

## Design consequences (no observation yet — stated as consequences, not facts)

| Item | Why it is a consequence |
| --- | --- |
| AD-2, AD-3 the assets repo does not exist | Every claim about its *shape* is a design decision; the only observed facts are the corpus it will hold (measured below) and the absence of a schema/vocabulary file (`find` → 0). S0 is the first executed proof. |
| AD-8 the vars schemas do not exist | `templates/**/vars.schema.json` is new work in S0/S3. What *is* observed: the render sites' var sets (`roles/zsh_config/tasks/main.yml:59-74` = 11; `kitty.conf.j2` = 1; `btop.conf.j2` = 1; `style.css.tpl` = 5; DM = 1/0/0/3/1) and the strictness risk (`kitty.conf.j2:2` embeds an absolute path, so an empty render is a silently broken config). |
| AD-10 layer 1 and layer 3 | No `.desktop` carries `TryExec` today and no gate validates an `Exec`; `verify` asserts 3 bin scripts (`verify_bin_scripts:60-79`), not the 7 keybind-invoked names. Both layers are new; the *hazard* is observed (`roles/cli_tools/tasks/main.yml:48-90` renders 6 wrappers that a keybind calls by name). |
| AD-12 the support window | OPEN-4. No consumer reads a `schema_major` today, so there is nothing to measure; S5 is the first executed proof (including its two negative tests). |
| AD-5 the assets fetch task | No `roles/assets` task fetches anything today — it reads the repo and the csg checkout. The fetch shape is copied from `cli_tools` (`ARCHITECTURE.md:224-227`), not measured in `assets`. S1 is the first executed proof. |
| AD-17 the manifests-dir seam | No `--manifests-dir`/`--inventory` flag exists; every role derives the repo root from `playbook_dir` (8 sites). S6 is the first executed proof. |

## Measured inventory (commands run, 2026-10-21, worktree `.worktrees/assetssplit`)

```bash
find dotfiles/assets/icon-templates -name '*.svg' | wc -l                       # 117
for d in dotfiles/assets/icon-templates/*/; do … find "$d" -name '*.svg' | wc -l; done
#   app-icons 10 · brightness 1 · capture-tool 13 · media-transport 4
#   media-transport-panel 2 · microphone 2 · power-mode 3 · settings-panel 17
#   status-bar 47 · ui 7 · volume 5 · wlogout 6            → 12 groups, 117 total
grep -rl '{{' dotfiles/assets/icon-templates --include='*.svg' | wc -l          # 107 carry a placeholder
find dotfiles/assets/icon-templates -name '*.svg' | while read f; do grep -q '{{' "$f" || echo "$f"; done | wc -l
#   10  — all of them app-icons/default/*.svg (static brand art)
ls -1 dotfiles/config/icon-template-color-scheme-mappings/ | wc -l              # 8
grep -c 'template:' dotfiles/config/icon-template-color-scheme-mappings/*.yaml
#   battery 11 · defaults 0 · email-client 1 · icons 136 · network 21
#   power-menu 3 · wallpaper-selector 1 · wlogout 6          → 179 variant entries
ls dotfiles/config/hypr/*.lua | wc -l                                           # 13
find dotfiles/config/nvim -type f | wc -l                                       # 8
ls dotfiles/applications/*.desktop | wc -l                                      # 6
ls -la dotfiles/assets/wallpapers/wallpapers.tar.gz                             # 82 656 450 bytes
ls -A dotfiles/assets/btop-themes                                               # .gitkeep only
du -sh dotfiles/assets dotfiles/config                                          # 80M, 184K
cat dotfiles/config/btop/active-theme                                           # colors.btop.theme (mutable)
grep -c 'assets.yaml\|roles/assets' scripts/deploy-coverage.py                  # 0
find dotfiles -iname '*schema*' -o -iname '*vocab*'                             # (no output)
ls LICENSE CHANGELOG.md                                                         # exit 2 — neither exists
uv --version                                                                    # uv 0.9.22
sha256sum /home/inumaki/Development/mu/scripts/worktree-guard.sh                 # b059ea80…c6cfafc2
python3 -c "…skills-lock…"                                                      # 7 hash-pinned skills
```

## Contradictions found between the brief and the repo

Each is a **brief statement that the tree does not support as written**. The spine resolves each one;
none reopens a decision the brief marked fixed.

| # | Brief says | Repo says | Resolution in the spine |
| --- | --- | --- | --- |
| C-1 | "runtime consumes ONLY the spine (enforced by `src/runtime/tests/architecture/test_layering.py`)" | `test_layering.py` enforces **hexagonal layering + the cross-package import ban** (`:104-111` for the package ban, `:60-72` for layers). Spine-only *input resolution* is enforced by `derive.py` (`resolve_input`, `:196-235`) and proven by `tests/unit/test_derive_input_provenance.py:99-152`, with the `doctor` tripwire at `application/doctor.py:125`. | AD-13 cites the correct enforcers; the invariant is unchanged. No new gate needed — only the citation is corrected so S1/S5 do not "strengthen" a test that already does something else. |
| C-2 | "`icons` (117 SVGs, **7 placeholders**, 8 mapping YAMLs + vocabulary/schema)" | 117 and 8 are exact. "7 placeholders" is not reproducible: 107 SVGs contain a `{{COLOR_*}}` placeholder and 10 (the `app-icons` group) contain none; no file is named or marked "placeholder" (`grep -rli placeholder` → 0). Three candidate readings: **7** = the non-vocabulary mapping files (8 − `defaults.yaml`), **7** = the `ui/` group's SVG count, or **7** = a stale count from before the corpus grew. | Treated as **117 SVGs / 12 groups / 107 templated / 10 static** (measured). The "7" is not used by any rule; AD-3's inventory row carries the measured figures. |
| C-3 | "`icons/schema.json schema_major`" and "template `vars.schema.json`" exist as contract handles | **Neither exists**: `find dotfiles -iname '*schema*' -o -iname '*vocab*'` → no output. What exists is `defaults.yaml`'s `COLOR_*` **vocabulary** and the generated `schemaVersion` integer in `roles/compositor_configs/vars/main.yml:175-190`. | AD-12 defines them as **new files** created in S0 (icons) and S3 (per-template). Marked "new work" rather than cited as existing. |
| C-4 | "`configs` (static: hypr 13 lua, hyprpaper, rofi, **wlogout**, nvim, starship)" | `dotfiles/config/wlogout/style.css.tpl` is a **Jinja template** with 5 vars, rendered by `roles/wlogout_config/tasks/main.yml:36-37`; and the whole `wlogout/` dir is also copied by `config_copies_entries` (`config_copies/vars/main.yml:68-72`). The same double life applies to `dotfiles/config/zsh/` (copied as a config dir, while `.zshrc.j2` is rendered by `zsh_config`). | The class boundary splits per **file**, not per directory: `wlogout/layout` → `configs`; `wlogout/style.css.tpl` → `templates`; `zsh/` supplies only the rendered `.zshrc` after S3. SLICES S2 steps 2 and 4 record the copy-shape change. |
| C-5 | "`.desktop` + scripts live in assets `desktop`" | Only **1 of the 7** keybind-invoked scripts is repo-authored (`toggle-touchpad`, `roles/compositor_configs/vars/main.yml:131-132`). The other six (`rofi-ui`, `capture-ui`, `hypr-pano-ui`, `wallpaper-selector-ui`, `icon-color-mapping-editor`, `btop-theme-studio`) are Jinja templates rendered by `roles/cli_tools/tasks/main.yml:48-90` because they bake installed-binary paths. (The keybind file has 9 `exec_cmd` targets; the remaining two, `kitty`/`thunar`, are package binaries.) | AD-10 scope boundary: `assets/desktop/scripts` holds repo-authored **static** scripts only; rendered launchers stay in the installer. Layer 3 still asserts all 7 exist and are executable. |
| C-6 | (class list assigns btop to `content` = "btop themes") | `dotfiles/config/btop/active-theme` is a **mutable preference** — the btop studio writes it and `roles/btop_config` reads it to pick the theme (`vars/main.yml:59-63`, `tasks:52-63`). A pinned corpus cannot hold a file a GUI rewrites. | AD-11 excludes it from assets; **OPEN-5** decides where it lands. S2's entry criteria block on OPEN-5 so it is not copied as config by accident. |
| C-7 | "`verify` asserts checkout/tag/class presence + schema compatibility" (implying the shape gate exists) | `verify` has **zero** `assets`-shape assertions today, and `scripts/deploy-coverage.py` has **zero** references to `assets.yaml` or `roles/assets` (`grep -c` → 0). The only assets coverage is the role's own unit test. | S5 step 4 adds the assets block to `deploy-coverage` (manifest `repo`+semver `tag`, role/verify mirror parity, no `dotfiles/` source, retired dirs absent) — without it the new pin would be the one pin no gate checks. |
| C-8 | Desktop layer 1 validates "`TryExec`" | No `.desktop` entry carries `TryExec` today (`rg -E '^TryExec=' dotfiles/applications/` → no hits); 3 of 6 `Exec` lines are bare binaries (`tidal-hifi`, `kitty`, …) rather than absolute paths. | AD-10 layer 1 makes **adding `TryExec`** part of the slice (S4 step 2), and `requires[]` is derived from the `Exec` line rather than assumed to already be declared. |

## Reports and sources read in full

- `ARCHITECTURE.md` (1–625) — the composition-repo authority: §2 what the repo owns, §3 topology, §4
  the seven repos + tags, §5 repo map, §6 provisioning (role order, spine layout, assets/settings/
  verify, mirrors), §7 runtime, §9 gates, §10.1 birth checklist, §11 recipes, §12 residuals.
- `AGENTS.md` (1–67), `Makefile` (1–160, `GATES` at 61–63), `bootstrap.sh` (1–40).
- `src/provisioning/ansible/roles/{assets,compositor_configs,config_copies,settings,display_manager,kitty_config,btop_config,zsh_config,wlogout_config,verify,filesystem}/` (vars + tasks + templates).
- `src/provisioning/ansible/playbooks/bootstrap.yaml` (order, 1–90).
- `src/runtime/src/runtime/application/derive.py` (1–300), `application/doctor.py` (118–130),
  `tests/architecture/test_layering.py` (1–130), `tests/integration/conftest.py` (80–140).
- `scripts/deploy-coverage.py` (1–80, 1342–1400, 1752–1840), `scripts/ci-gates-parity.py` (1–80).
- `_bmad-output/planning-artifacts/architecture/architecture-cli-repos-2026-10-19/{ARCHITECTURE-SPINE,SLICES,EVIDENCE-INDEX}.md`
  — the structural precedent (status block, paradigm, AD Binds/Prevents/Rule, birth checklist, slice
  loop, evidence table shape).
- `openspec/specs/cli-repo-birth/spec.md` (1–60), `openspec/changes/archive/2026-10-21-cli-tools-repos/POST-MIGRATION.md` (1–50)
  — the birth/closing rituals already proven once.
- `dotfiles/` tree (config, assets, applications, scripts, provisioning manifests, `wallpapers.tar.gz`).
- `mu/AGENTS.md` (1–29), `mu/tickets/LIFECYCLE.md` (1–60), `mu/tickets/INDEX.md` (1–40),
  `mu/skills-lock.json`, `mu/scripts/worktree-guard.sh`.
