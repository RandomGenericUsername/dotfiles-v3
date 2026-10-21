---
name: 'Assets split — the dotfiles corpus becomes one pinned repo'
type: architecture-spine
purpose: build-substrate
altitude: feature
paradigm: 'five entities on a pinned-artifact supply chain, with one immutable asset corpus'
scope: 'Extracting the dotfiles asset corpus (icons, templates, configs, content, desktop) out of
  dotfiles-v3 into a single pinned data repo, and cutting provisioning over to fetch it once per tag
  into the install spine. Closes the topology as five things: runtime engine, installer engine,
  assets, composition repo, and the already-extracted external packages. No code extraction happens
  here except the installer (S6); every other slice moves data and rewires the consumer.'
status: final
created: '2026-10-21'
updated: '2026-10-21'
binds:
  - assets repo (new; name OPEN-1)
  - dotfiles-v3 (installer + runtime + composition)
  - src/provisioning/ansible/roles/{assets,compositor_configs,config_copies,settings,display_manager,kitty_config,btop_config,zsh_config,wlogout_config,verify}
  - dotfiles/provisioning/assets.yaml
  - dotfiles/config/**
  - dotfiles/assets/**
  - dotfiles/applications/**
  - dotfiles/scripts/**
sources:
  - ARCHITECTURE.md
  - AGENTS.md
  - Makefile
  - dotfiles/provisioning/assets.yaml
  - dotfiles/provisioning/config-copies.yaml
  - src/provisioning/ansible/playbooks/bootstrap.yaml
  - src/runtime/src/runtime/application/derive.py
  - src/runtime/tests/architecture/test_layering.py
  - scripts/deploy-coverage.py
  - _bmad-output/planning-artifacts/architecture/architecture-cli-repos-2026-10-19/ARCHITECTURE-SPINE.md
  - openspec/specs/cli-repo-birth/spec.md
  - openspec/changes/archive/2026-10-21-cli-tools-repos/POST-MIGRATION.md
  - /home/inumaki/Development/mu/AGENTS.md
  - /home/inumaki/Development/mu/tickets/LIFECYCLE.md
companions:
  - SLICES.md
  - EVIDENCE-INDEX.md
  - .memlog.md
---

# Architecture Spine — Assets split

## Design Paradigm

**Five entities on a pinned-artifact supply chain, with one immutable asset corpus.** The supply
chain already exists for code: `contracts` → three libs → three CLIs → `dotfiles-v3`, every edge a
git tag. This change adds the *data* half of the same chain: one repo publishes the corpus the
installer deploys, `dotfiles-v3` pins it, and the runtime never learns it exists.

The load-bearing move is not "move the files". It is that **the installer becomes the only writer
of the corpus into the spine, and the runtime keeps reading the spine exactly as it does today**
(`src/runtime/src/runtime/application/derive.py:12-13`). Destinations are frozen (AD-7); only the
source of the bytes moves.

| # | Entity | Lives in | Owns | Consumes |
| --- | --- | --- | --- | --- |
| 1 | runtime engine | `src/runtime/` (`dotfiles-runtime`) | desktop state machine, `apply → derive → reconcile`, palette/effects/icons derivation | **the install spine only** (+ `DOTFILES_DEV_INPUTS_ROOT` for dev) |
| 2 | installer engine | `src/provisioning/` (`dotfiles-provision`) → own repo at S6 | Ansible roles/playbooks, manifests reader, verify | assets (pinned), CLIs (pinned), AGS units (pinned), packages, the composition repo's manifests/vars |
| 3 | assets | new repo (OPEN-1) | the corpus: icons, templates, configs, content, desktop; the corpus's own schemas | nothing |
| 4 | composition repo | `dotfiles-v3` after S7 | pins (runtime, installer, assets, tools, AGS, contracts), host inventory/vars, bootstrap entry, composition gates, docs | all four others as pins |
| 5 | extracted packages | `contracts`, `cli-output`, `config-assembler-engine`, `oci-runtime`, `csg`, `weg`, `itr`, `ags-platform`, `ags-apps` | their own surfaces | each other, by tag |

```text
                          +----------------------------+
                          |  (5) external packages     |
                          |  contracts · libs · CLIs   |
                          |  ags-platform · ags-apps   |
                          +-------------+--------------+
                                        | pinned tags
                                        v
  +------------------+   pinned tag   +---------------------+
  | (3) assets repo  |--------------->| (2) installer       |
  | icons templates  |                |     engine          |
  | configs content  |                | roles · playbooks   |
  | desktop          |                | verify · manifests  |
  +------------------+                +----------+----------+
                                                 |
                        writes the corpus into   |  installs (artifact dep,
                        <spine>/assets/<tag>/    |  never a code import)
                        then deploys per class   v
                                      +---------------------+
                                      | (1) runtime engine  |
                                      | reads the SPINE     |
                                      | only (layering test)|
                                      +---------------------+
                                                 ^
                                                 | pins + host vars + manifests
                                      +---------------------+
                                      | (4) composition repo|
                                      | dotfiles-v3         |
                                      +---------------------+
```

**Direction rules (enforced by test, not convention)**

| Rule | Enforced by |
| --- | --- |
| runtime imports no provisioning code and no asset path; it reads the spine | `src/runtime/tests/architecture/test_layering.py:104-111` (`_FORBIDDEN_CROSS_PACKAGE`), `derive.py:12-13,196-230` |
| installer → runtime is an artifact dependency (a `uv tool install` of the pinned runtime), not an import | `roles/runtime_daemon/tasks/main.yml`, `dotfiles/provisioning/cli-tools.yaml` (`dotfiles-runtime` is the one `source:` entry) |
| assets is a leaf: it imports nothing and names no consumer destination | AD-2, AD-6 (gate: no spine path in the assets repo) |
| the composing repo authors no corpus content after S7 | AD-17, extension of `scripts/deploy-coverage.py` absence guards |

## Inherited Invariants & Constraints

Binding inputs — inherited, not re-derived here.

| Inherited | From | Binds here |
| --- | --- | --- |
| Evidence rule: every non-trivial claim carries a command + observed result, or a file path + line range | `AGENTS.md` §3; `mu/AGENTS.md:5-13` | every AD below and every gate in `SLICES.md` |
| Never work on `master`; `.worktrees/<id>/` on `ticket/<id>-<slug>`; merge only on green gates | `AGENTS.md` §1; `mu/AGENTS.md:28` | each slice's branch and entry criteria |
| Planning edits and code changes land in separate commits | `AGENTS.md` §4 | this spine is a planning-only commit; each slice's deletion commit carries code |
| New skeleton sources must be registered in `compositor_configs_skeleton_files` **and** the `verify` mirror, or a fresh provision deploys an unresolvable import | `AGENTS.md` §2 | AD-7, AD-8, S2 gate |
| Consume external units whole, pinned by tag; never vendor | `ARCHITECTURE.md` §4; cli-repos spine AD-3/AD-10 | AD-5, AD-6 |
| Retire a gate by deleting it, never by leaving it pointing at a tree the repo no longer owns | cli-repos spine AD-14; `docs/LESSONS-ags-apps-migration.md` §5 | AD-16, every slice's deletion step |
| Destructive-last per target; a published tag is never moved | cli-repos spine AD-13 | AD-16 |
| mu-strict birth (13 items) from the first commit | cli-repos spine AD-12; `openspec/specs/cli-repo-birth/spec.md` | AD-15 |
| Fixed by the human: the five entities, the class structure, one repo-wide tag, the manifest shape, the exclusions, the DM split, the three desktop validation layers | run constraints (`SLICES.md` entry criteria; `.memlog.md` entries 1–11) | AD-1…AD-14 |
| cli-repos spine AD-10: provisioning addresses tools by `{name, repo, tag}` and asset entries by a **pinned checkout path** | `architecture-cli-repos-2026-10-19/ARCHITECTURE-SPINE.md` AD-10 | AD-5 **extends** it (a corpus repo with its own pin), it does not replace it: `csg-templates` keeps reading the csg checkout (AD-14), and `assets.yaml` stays the authoritative manifest (AD-6). No inherited AD is weakened. |

## Invariants & Rules

### AD-1 — Five entities, one-way dependency graph, no cycles

- **Binds:** all five entities; every new edge introduced by this change.
- **Prevents:** the two failure shapes the code split already proved — a consumer reaching into a
  producer's tree, and a "leaf" that turns out to depend on its consumer (which makes every future
  version bump a lockstep release).
- **Rule:** the graph is exactly: `installer → assets` (pinned fetch), `installer → external
  packages` (pinned fetch/install), `installer → runtime` (artifact install), `composition repo →
  {installer, assets, runtime, packages}` (pins + host vars), `runtime → spine`. Assets has **zero
  outbound edges**. The runtime has **zero edges to assets** — not an import, not a path, not a
  `command -v`. The installer never imports runtime code and the runtime never imports installer
  code (`test_layering.py:104-111`).
- **Evidence:** `src/runtime/tests/architecture/test_layering.py:104-111`;
  `src/runtime/src/runtime/application/derive.py:12-13,196-230`.

### AD-2 — The assets repo is data-only: no importable package, no console script, no engine

- **Binds:** the assets repo, its `Makefile`, its CI.
- **Prevents:** the corpus repo growing a renderer (that is `itr`), a palette generator (that is
  `csg`), or a provisioner (that is the installer) — each of which would immediately need a release
  cadence coupled to code and re-open the split.
- **Rule:** no `src/<package>/`, no `[project.scripts]`, no `dotfiles-*` binary. A
  `pyproject.toml` is permitted **only** as dev tooling for the validators (no importable package,
  no console script) or omitted entirely. The repo may carry Python only under `scripts/` as
  CI-executed validators. Its `Makefile` verbs are validation verbs (`validate`, `lint`, `gates`,
  `hermetic`), never `install`. It names **no consumer destination and no spine path** (AD-6).
- **Evidence (what it replaces, i.e. the engines that do exist elsewhere):** `itr` console +
  render (`ARCHITECTURE.md:318`), `csg` generate (`ARCHITECTURE.md:313`), installer CLI
  `dotfiles-provision` (`src/provisioning/pyproject.toml:14-15`).

### AD-3 — One repo, five class directories, one tag

- **Binds:** the assets repo layout, the consumer manifest, every CI scope.
- **Prevents:** five tags for one corpus (five pins to bump per release, five "which tag is the
  icons at?" questions), and the opposite failure — a tag per file.
- **Rule:** classes are **directories plus manifest entries plus CI scopes**, never version
  boundaries: `icons/`, `templates/`, `configs/`, `content/`, `desktop/`. One annotated
  `vMAJOR.MINOR.PATCH` tag covers all five. A class directory may not be renamed and a file may not
  move between classes without a MAJOR (AD-4), because the consumer manifest reads class paths
  literally.

```text
<assets-repo>/
  AGENTS.md   CLAUDE.md -> AGENTS.md   README.md   CHANGELOG.md   LICENSE   Makefile
  catalog.yaml                     # what is inside each class (repo-local truth; NO spine paths)
  icons/
    templates/                     # 12 groups, 117 SVGs (107 carry {{COLOR_*}} placeholders)
    mappings/                      # icons.yaml + 6 group files + defaults.yaml (the COLOR_* vocabulary)
    schema.json                    # the icons contract; carries schema_major (AD-12)
  templates/
    zsh/.zshrc.j2                  + .zshrc.vars.schema.json
    kitty/kitty.conf.j2            + kitty.conf.vars.schema.json
    btop/btop.conf.j2              + btop.conf.vars.schema.json
    wlogout/style.css.tpl          + style.css.vars.schema.json
    display-manager/{sddm.conf,config.toml,regreet.toml,regreet.css,hypr-session}.j2
                                   + display-manager.vars.schema.json
  configs/
    hypr/*.lua (13)   hyprpaper/hyprpaper.conf   rofi/launcher/config.rasi
    wlogout/layout    nvim/** (8)                starship/starship.toml
  content/
    wallpapers/wallpapers.tar.gz   # must contain default.png
    btop-themes/                   # authored *.theme (empty today: only .gitkeep)
  desktop/
    applications/*.desktop (6)     scripts/toggle-touchpad     desktop.yaml  # requires/optional
  scripts/validate-*.py            # CI-only validators (shellcheck wrapper, .desktop spec, schemas)
  openspec/   tickets/   .agents/skills/   _bmad/   .opencode/   skills-lock.json
  .github/workflows/gates.yml
```

- **Evidence:** measured inventory — 117 SVGs in 12 groups (`find … -name '*.svg' | wc -l` → 117),
  8 mapping YAMLs (`ls dotfiles/config/icon-template-color-scheme-mappings/`), 13 hypr Lua files
  (`ls dotfiles/config/hypr/*.lua | wc -l` → 13), 8 nvim files, 6 `.desktop` entries, 1 in-repo
  script, an empty `btop-themes/` (`.gitkeep` only), `wallpapers.tar.gz` = 82 656 450 bytes.

### AD-4 — Semver means one thing: the tag is the deployment pin

- **Binds:** every assets release; every consumer pin bump.
- **Prevents:** a "PATCH" that renames a class directory (breaks the manifest silently) and a
  "MAJOR" for an added wallpaper (which would force five unrelated consumers to re-pin).
- **Rule:**
  - **MAJOR** — any contract or path break: class directory rename, a file the consumer addresses by
    path removed or moved, a mapping vocabulary rename, a template's **required** var removed or
    retyped, `schema_major` bumped (AD-12).
  - **MINOR** — additive only: a new icon/group/variant, a new template (with its own first
    `schema_major`), a new `.desktop` entry, a new wallpaper.
  - **PATCH** — content fix that keeps every path: SVG recolor, wallpaper re-encode, text fix in a
    mapping file.
  - A tag is never moved or deleted; a fix is a new tag. Release ritual = gates green → version in
    `CHANGELOG.md` (+ `catalog.yaml` if the class inventory changed) → annotated tag → consumer pin
    bump in its own commit.
- **Evidence:** the consumer addresses content by literal path —
  `roles/compositor_configs/vars/main.yml:110-125` (15 per-file entries),
  `dotfiles/provisioning/assets.yaml:9-17` (`source:` is a literal repo path),
  `roles/verify/vars/main.yml:493-507` (the verify mirror of the same paths).

### AD-5 — Fetch once per tag into the spine; deploy per class from that checkout

- **Binds:** the installer's assets role, the manifest, verify.
- **Prevents:** (a) five clones for five classes, (b) a network read at deploy time (a provision
  that only works online), and (c) the stale-source class of bug the cli-tools split already fixed
  by pinning a checkout (`roles/assets/vars/main.yml:53-69` is today's pinned-checkout precedent).
- **Rule:** the role shallow-clones `repo@tag` into `<install>/assets/<tag>/` **once**, removes
  `.git`, and writes `<install>/assets/pinned` containing exactly the tag (one line, beside the tag
  dir — the `cli-tools/<name>/pinned` shape). Every class deploy reads from
  `<install>/assets/<tag>/<class>/…`; no task reads the composition checkout or the network after
  the clone. A missing checkout fails loud **before** the first copy (the stat/assert pair at
  `roles/assets/tasks/main.yml:112-128` is the shape to copy).
- **Evidence:** `roles/assets/vars/main.yml:67-69` (`assets_csg_pinned_tag` +
  `assets_csg_templates_source`), `roles/assets/tasks/main.yml:112-136` (stat/assert then
  synchronize), `ARCHITECTURE.md:198-203` (`cli-tools/<name>/<tag>/` + `pinned`).

### AD-6 — The manifest is the single source of truth for the pin and the destination class map

- **Binds:** `dotfiles/provisioning/assets.yaml`, `roles/assets/vars/main.yml`,
  `roles/verify/vars/main.yml`, the parity test.
- **Prevents:** the three-copy drift the CLI pins already have to be gate-locked against
  (`ARCHITECTURE.md:257-269`), and — new here — the destination class map being duplicated in a
  second file that no gate compares.
- **Rule:** the composition repo's `assets.yaml` grows one block:

  ```yaml
  assets:
    repo: https://github.com/<owner>/<assets-repo>     # OPEN-1
    tag: v0.1.0
    classes:
      icons:     { dest: icons,        schema: icons/schema.json }
      templates: { dest: templates,    schema: "**/vars.schema.json" }
      configs:   { dest: configs,      schema: null }
      content:   { dest: content,      schema: null }
      desktop:   { dest: desktop,      schema: desktop/desktop.yaml }
  ```

  `dest` is **class-local and spine-relative-to-the-class-deploy**, never an absolute path.
  `roles/assets/vars/main.yml` mirrors `repo`/`tag`/the class map; `roles/verify/vars/main.yml`
  mirrors `tag` + the required member sets; a structural parity test locks manifest ⇄ role ⇄ verify
  (the existing `TestAssetsCsgTemplatesSource` family). `catalog.yaml` in the assets repo describes
  **what is inside** a class and never names a spine path — the two documents answer different
  questions and neither repeats the other.
- **Evidence:** `dotfiles/provisioning/assets.yaml:1-33`;
  `roles/assets/vars/main.yml:92-102` (the hand-maintained mirror);
  `src/provisioning/tests/unit/test_assets_role.py:30-31` (`_MANIFEST_PATH`, the parity anchor).

### AD-7 — The split moves the source, never the destination

- **Binds:** every install where the corpus already lands; the runtime; verify.
- **Prevents:** the split becoming a MAJOR for the runtime and every consumer at once — a mass
  destination rename would touch `derive.py`'s candidate list, `verify_*` paths, every
  `~/.config/<tool>` symlink, and the runtime's cache keys, for no user-visible gain.
- **Rule:** the deployed paths are **frozen**:

  | Class | Deployed to (unchanged from today) | From |
  | --- | --- | --- |
  | `icons/templates` | `<spine>/icon-templates/` | `dotfiles/assets/icon-templates/` |
  | `icons/mappings` | `<spine>/icon-mappings/` | `dotfiles/config/icon-template-color-scheme-mappings/` |
  | `configs` | `<spine>/config/{hypr,hyprpaper,rofi,wlogout,nvim,starship}/` (`wlogout/` gets **layout only**; its `style.css` is rendered by the templates class) | `dotfiles/config/*` |
  | `templates` (rendered) | `<spine>/config/{zsh,kitty,btop,wlogout}/…` | role-internal + repo `.j2`/`.tpl` |
  | `content/wallpapers` | `<spine>/wallpapers/` (unarchived) | `dotfiles/assets/wallpapers/wallpapers.tar.gz` |
  | `content/btop-themes` | `<spine>/config/btop/themes/` | `dotfiles/assets/btop-themes/` |
  | `desktop/applications` | `$XDG_DATA_HOME/applications/*.desktop` | `dotfiles/applications/` |
  | `desktop/scripts` | `$XDG_BIN_HOME/toggle-touchpad` (0755) | `dotfiles/scripts/toggle-touchpad` |

  The fetched unit itself lands at `<spine>/assets/<tag>/` (new, and the only new path).
  `verify` asserts a **required minimum set** of named members, never an exact count and never
  full-set equality — otherwise every MINOR tag breaks verify.
- **Evidence:** `roles/verify/vars/main.yml:415-437` (`verify_asset_dirs`,
  `verify_asset_files`), `:493-507` (skeletons), `derive.py:185-215` (runtime candidate paths),
  `roles/assets/vars/main.yml:38-43` (`assets_deploy_dirs`), `:47,51,117` (wallpapers/effects).

### AD-8 — Template render contract: assets ships the template and its schema, never the values

- **Binds:** `templates` class, the rendering roles (`zsh_config`, `kitty_config`, `btop_config`,
  `wlogout_config`, `display_manager`), the parity test.
- **Prevents:** the two observed failure shapes — a template that renders an **empty** path and
  silently produces a broken config (the reason `kitty.conf.j2:2` and `.zshrc.j2` embed absolute
  spine/state paths), and the assets repo acquiring host facts (install dir, XDG homes, engine)
  it cannot know.
- **Rule:**
  1. assets ships `<name>.j2` (or `.tpl`, kept for the existing wlogout file) **plus**
     `<name>.vars.schema.json` with `schema_major`, `required[]` (name + type) and `optional[]`.
  2. **No `| default('')`** and no `default(...)` on a required var inside an assets template. The
     installer renders via `ansible.builtin.template`, whose undefined-variable behavior is
     strict (an undefined var fails the task rather than rendering empty); the rule exists so a
     template cannot *defeat* that with a silent fallback.
  3. The installer **supplies** every var; the assets repo supplies none. A pre-render assert per
     render call (the `install_dir` seam assert is the precedent,
     `roles/settings/tasks/main.yml:45-57`) makes a missing var a named failure.
  4. A static parity test in the installer repo asserts, for each assets template it renders, that
     every entry in the schema's `required[]` is supplied by that role's render task — offline, no
     Ansible run. The schema's own well-formedness is validated in the **assets** repo CI.
  5. Rendered output is **not** an asset: the assets repo never contains a `settings.toml`, a
     `kitty.conf`, or a `btop.conf` (AD-11).
- **Evidence:** `roles/kitty_config/templates/kitty.conf.j2:1-4` (absolute include),
  `roles/zsh_config/tasks/main.yml:59-74` (11 vars supplied at render),
  `roles/settings/tasks/main.yml:45-57` (the seam assert),
  `dotfiles/config/wlogout/style.css.tpl` (5 vars: `COLORS_FILE_PATH`, `CURRENT_WALLPAPER_SYMLINK`,
  `FONT_SIZE_PX`, `STATE_ROOT`, `SYSTEM_FONT_FAMILY`),
  `roles/display_manager/templates/*.j2` (1–3 vars each, measured).

### AD-9 — Display-manager templates are assets; DM type/packages/enablement stay in the installer

- **Binds:** `display_manager` role, `templates/display-manager/`.
- **Prevents:** a DM concern split across two repos (a template in assets edited against packages in
  the installer) and the assets repo acquiring `become`/systemd behavior it must never have.
- **Rule:** the five templates move (`sddm.conf.j2`, `config.toml.j2`, `regreet.toml.j2`,
  `regreet.css.j2`, `hypr-session.j2`). The installer keeps: `display_manager_type` selection,
  `display_manager_sddm_packages` / `display_manager_packages_{regreet,tuigreet}`, the Pixie repo
  pin, service enablement/disablement, the login-timeout patch, and every `become: true` task. The
  assets side is rendered with vars the installer supplies
  (`display_manager_sddm_display_server`, `display_manager_greeter_user`, …) and ships a JSON
  schema per AD-8. The installer's render task remains `mode: "0644"` + `become: true`; assets
  carries no mode or ownership.
- **Evidence:** `roles/display_manager/vars/main.yml:20-49` (type/packages/conf paths),
  `roles/display_manager/tasks/main.yml:26-68` (install → fetch → patch → render),
  `roles/display_manager/tasks/main.yml:112-131` (enable/disable).

### AD-10 — Desktop validation is three layers, each owned by a different repo

- **Binds:** assets CI, the installer's desktop deploy, `verify`.
- **Prevents:** a `.desktop` entry whose `Exec` binary is absent — which rofi `drun` still lists, so
  the user gets a menu entry that does nothing (the exact silent-failure class the keybind gates
  already exist for: `verify_bin_scripts`, `roles/verify/vars/main.yml:60-79`).
- **Rule:**

  | Layer | Owner | Asserts | Failure mode |
  | --- | --- | --- | --- |
  | 1. static | **assets CI** | every `.desktop` parses (spec: required keys, `[Desktop Entry]`, `Type`), every `Exec`/`TryExec` names a binary in the entry's declared `requires`, scripts pass `shellcheck`, `desktop.yaml` is well-formed | assets tag cannot be cut |
  | 2. deploy-time | **installer** | resolves each entry's `requires[]` against installed packages/binaries and each `optional[]` with a warning; a missing **required** binary fails the run; a missing optional is reported and the entry is skipped | provision fails (required) / degrades loudly (optional) |
  | 3. deployed | **verify** | the deployed set is present at `$XDG_DATA_HOME/applications/`, each `.desktop` `Exec` resolves on `PATH`, `toggle-touchpad` is executable, and **every script/launcher name a hypr keybind invokes exists and is executable** | gate fails |

  Assets ships the entry + a `desktop.yaml` declaring `requires`/`optional` per entry. Assets does
  **not** decide whether a package is installed. Today's entries carry **no `TryExec`** — adding it
  is part of layer 1, and layer 1's `requires` list is the authority for layer 2.
  Scope boundary: `assets/desktop/scripts` holds **repo-authored static scripts only**
  (`toggle-touchpad`). The AGS launcher wrappers (`rofi-ui`, `capture-ui`, `hypr-pano-ui`,
  `wallpaper-selector-ui`, `icon-color-mapping-editor`, `btop-theme-studio`) are Jinja-rendered by
  the installer's `cli_tools` role because they bake in installed-binary paths — they stay there
  (see Contradiction C-2).
- **Evidence:** `dotfiles/applications/*.desktop` (6 files, zero `TryExec`);
  `dotfiles/config/hypr/keybindings.lua:34,44,51,71,80,532` (7 invoked script/launcher names; the
  file has 9 `exec_cmd` targets in total — the other two, `kitty` and `thunar`, are package binaries
  covered by the PATH gate);
  `roles/compositor_configs/vars/main.yml:131-132` (the one repo-authored script),
  `:154-160` (the 6 entries); `roles/cli_tools/tasks/main.yml:48-90` (the rendered wrappers);
  `roles/verify/vars/main.yml:60-79` (`verify_bin_scripts`).

### AD-11 — Generated and mutable artifacts are never assets

- **Binds:** the assets repo scope; `compositor_configs`, `settings`, the runtime.
- **Prevents:** versioning derived output — which makes the repo a second source of truth for
  something a role or the runtime computes, and guarantees the committed copy drifts.
- **Rule:** the assets repo contains **no** `icons.json`, **no** rendered `settings.toml`, **no**
  rendered `kitty.conf`/`btop.conf`/`.zshrc`, **no** palette or `current/` state, and **no**
  `btop/active-theme`. Those stay where they are produced: `icons.json` in `compositor_configs`
  (`roles/compositor_configs/vars/main.yml:164-190`), settings in `settings`
  (`roles/settings/vars/main.yml:107-116`), palette/current in the runtime.
  `dotfiles/config/btop/active-theme` is a **mutable host preference** (the studio writes it), so
  it cannot become a pinned asset at all — it is OPEN-5.
- **Evidence:** `roles/compositor_configs/tasks/main.yml:91-105` (icons.json generated, twice),
  `roles/settings/vars/main.yml:113-116`, `roles/btop_config/vars/main.yml:59-63` +
  `roles/btop_config/tasks/main.yml:52-63` (the active-theme read), `dotfiles/config/btop/active-theme`
  (content: `colors.btop.theme`).

### AD-12 — Contract schema versions are separate from the repo tag

- **Binds:** `icons/schema.json`, every `templates/**/vars.schema.json`, provision-time and
  verify-time compatibility checks.
- **Prevents:** two opposite failures — forcing a MAJOR repo tag for an *additive* schema change
  (killing MINOR/PATCH cadence), and shipping a *breaking* shape change inside a PATCH-looking
  content commit (invisible to every consumer).
- **Rule:** each schema file carries `schema_major` (integer) and its own documented shape. The
  **tag** answers "which corpus is deployed"; **`schema_major`** answers "can this consumer parse
  it". They move independently, with two constraints:
  1. a MAJOR **tag** implies the schema check still passes for the supported window;
  2. raising `schema_major` requires a MAJOR tag even when no path changed.
  `provision` refuses a `schema_major` outside the consumer's support window and names the file and
  the expected range; `verify` re-asserts the deployed corpus's schema versions. The support window
  itself is OPEN-4.
- **Evidence:** no schema file exists today — `find dotfiles -iname '*schema*'` → 0 hits. The
  *analogue* that works is the invocation contract's `DATA_VERSION` + same-tag rule
  (`ARCHITECTURE.md:412,422-424`) and the icons manifest's `schemaVersion`
  (`roles/compositor_configs/vars/main.yml:175-190`). Marked as **new work**: the files are created
  in S0/S1/S3.

### AD-13 — The runtime consumes only the spine; assets is never a runtime dependency

- **Binds:** `derive.py`, the runtime integration tests, the assets repo.
- **Prevents:** `DOTFILES_DEV_INPUTS_ROOT`-shaped convenience leaking into production (the bug the
  spine-only rule was written for), and the runtime acquiring a checkout path that only exists on a
  developer machine.
- **Rule:** the four runtime derivation inputs keep exactly their current **names and spine
  candidates** — `csg_templates`, `weg_effects`, `icon_templates`, `icon_mappings`
  (`derive.py:128-133` labels, `:146-185` candidates). Of those, **two are fed by assets**
  (`icon_templates`, `icon_mappings`), one by the **csg pin** (`csg_templates`), one is
  **runtime/installer-generated** (`weg_effects`). `resolve_input` tries the spine first and
  consults a repo checkout **only** when `DOTFILES_DEV_INPUTS_ROOT` is set, and then logs it
  (`derive.py:196-235`); `doctor` flags a repo-sourced input
  (`src/runtime/src/runtime/application/doctor.py:125`). A missing input raises
  `MissingDerivationInputError` naming the spine path.
  The three **repo candidates** that name the deleted tree are the exception, and they are the
  reason this rule is written down: in S1 they are re-pointed from
  `dotfiles/assets/icon-templates` / `dotfiles/config/icon-template-color-scheme-mappings` to the
  assets checkout layout (`icons/templates`, `icons/mappings`), so the dev override means "point
  the dev root at an assets checkout". Until S1 they are untouched.
- **Evidence:** `derive.py:123` (`_DEV_INPUTS_ROOT_ENV`), `:196-235` (`resolve_input`),
  `:219-235` (`require_input` error text),
  `src/runtime/tests/unit/test_derive_input_provenance.py:99-152`,
  `src/runtime/tests/architecture/test_layering.py:104-111`.

### AD-14 — Three corpora are excluded from assets, permanently

- **Binds:** the assets repo scope; `roles/assets`, `roles/settings`, `ags_apps`.
- **Prevents:** one corpus with two owners — the failure mode that makes "which copy is live?"
  unanswerable and guarantees the two copies diverge.
- **Rule:** these never enter the assets repo:
  1. **csg palette templates** — they ship in the `csg` repo and are read from its pinned checkout
     (`<install>/cli-tools/csg/<tag>/src/color_scheme_generator/defaults/templates`). The assets
     role keeps that entry as a **checkout copy**, not a repo copy.
  2. **AGS app assets** (bar/overlay sources, `icons.json` shape sources) — owned by the
     `ags-apps` unit, deployed WHOLE as live links.
  3. **Generated output** — AD-11.
- **Evidence:** `dotfiles/provisioning/assets.yaml:18-28` (the ABSOLUTE csg source and why),
  `roles/assets/vars/main.yml:53-69,96-102`, `ARCHITECTURE.md:241-247`,
  `roles/ags_apps/vars/main.yml:1-90` (unit-deployed apps).

### AD-15 — Repo birth is mu-strict, from the first commit (13 items)

- **Binds:** the assets repo (S0) and the installer repo (S6).
- **Prevents:** "harness later", which the AGS guide names as the reason per-app splits were
  deferred, and a first tag whose content cannot be re-verified.
- **Rule:** a repo is not a valid extraction target until all 13 items below are present and green on
  a fresh clone. Harness files are **copied** from `mu` (same `skills-lock.json` hashes, same
  `worktree-guard.sh`), never re-authored. Three items are re-pointed for a **data** repo — marked ⇄.

  | # | Item | Source / shape | Gate that proves it |
  | --- | --- | --- | --- |
  | 1 | `AGENTS.md` with the evidence contract (Evidence + Verify per claim), worktree rule, planning-vs-code rule | copy from `mu/AGENTS.md`, retarget scope | `rg -c "Evidence:|Verify:" AGENTS.md` ≥ 2 |
  | 2 | `CLAUDE.md` symlink → `AGENTS.md` | `ln -s AGENTS.md CLAUDE.md` | `test -L CLAUDE.md` |
  | 3 | `tickets/INDEX.md`, `tickets/LIFECYCLE.md`, `tickets/_template/{epic,requirement,task,bug,ops-task,spike}.md`, `tickets/_fixtures/router-lanes.md` | copy from `mu/tickets` | `rg -c "Gate .*:" tickets/LIFECYCLE.md` ≥ 6 |
  | 4 | `scripts/worktree-guard.sh`, executable, byte-identical to `mu` | copy from `mu` | `diff -u "$MU/scripts/worktree-guard.sh" scripts/worktree-guard.sh` → exit 0; `check-clean` → 0 |
  | 5 | `.agents/skills/` + `skills-lock.json` (7 hash-pinned skills) | copy from `mu` verbatim | `diff -u "$MU/skills-lock.json" skills-lock.json` → exit 0 |
  | 6 | `_bmad/` (config, scripts, core-tools, method, custom) | copy from `mu` | `python3 _bmad/scripts/memlog.py --help` → 0 |
  | 7 | `openspec/config.yaml` + `specs/` + `changes/` | config from `mu`, context retargeted | `openspec validate --specs` → 0 |
  | 8 ⇄ | `catalog.yaml` + per-class layout + the schemas (data repo: **no** importable package, no console script) | AD-2, AD-3 | `make validate` → 0; `rg -n '\[project.scripts\]' pyproject.toml` → exit 1 |
  | 9 | `Makefile` with fresh-clone verbs anchored on `$(CURDIR)`: `help validate lint gates hermetic` (data repo has no `sync/build/install`) | shape from `mu/Makefile` | `make validate && make gates` → 0 on a fresh clone |
  | 10 ⇄ | Hermetic validation (empty `HOME` + four `XDG_*`, foreign cwd) — a data repo's "tests" are validators | AD-15 note | `make hermetic` → 0 |
  | 11 | `.github/workflows/gates.yml`, one job per `make gates` target + `ci-gates-parity` | shape from dotfiles `.github/workflows/gates.yml` | parity script → PASS |
  | 12 | `README.md` (public surface + how `dotfiles-v3` pins it, naming no path inside another repo), `CHANGELOG.md`, `LICENSE` (MIT) | new | `make gates` docs check |
  | 13 ⇄ | `desktop/desktop.yaml` + `scripts/validate-desktop.py` + `shellcheck` wiring (the data-repo replacement for `docker/`) | AD-10 layer 1 | `make validate` fails on a bad `Exec`; passes on the shipped corpus |

- **Evidence:** `mu/AGENTS.md:5-13,28`, `mu/tickets/LIFECYCLE.md` (six gate one-liners),
  `mu/skills-lock.json` (7 skills: `bmad`, `bmad-architecture`, `bmad-build`, `bmad-product-brief`,
  `bmad-spec`, `bmod-core-tools`, `bmod-method`), `mu/scripts/worktree-guard.sh`
  (sha256 `b059ea80…c6cfafc2`), `openspec/specs/cli-repo-birth/spec.md:1-40`.

### AD-16 — Migration is destructive-last, per class

- **Binds:** every slice.
- **Prevents:** deleting the only working corpus before the replacement is proven, and leaving dead
  references after deletion (a role var pointing at a `dotfiles/` path that no longer exists is a
  green-looking provision that copies nothing — `synchronize` against a missing `src` is silent).
- **Rule:** per class, in this order: land in the assets repo → gates green → tag → rewire the
  installer to read `<spine>/assets/<tag>/<class>/` → **prove by execution** (provision or the
  closest executable proof) → delete the in-tree copy **and every reference it orphaned**
  (`roles/*/vars`, `verify` mirrors, `deploy-coverage` expectations, `.gitignore`, prose, the
  runtime's dev-override fixture paths) **in the same slice** → merge. The next class waits for that
  merge. Rollback = pin bump to the previous tag (or none) + `git revert` of the deletion commit;
  a published tag is never deleted or moved.
- **Evidence:** cli-repos spine AD-13; `roles/assets/tasks/main.yml:26-32` (the documented silent
  no-op for a missing mirror source); `scripts/deploy-coverage.py:1360-1398` (the
  absence-guard shape to copy).

### AD-17 — `dotfiles-v3` ends as the composition repo

- **Binds:** the final shape of `dotfiles-v3` (S7).
- **Prevents:** the composition repo re-growing a corpus copy ("just this one wallpaper") and the
  installer repo silently becoming a monorepo by absorbing the host's pins.
- **Rule:** after S7 `dotfiles-v3` contains, and authors, only:

  | Kept | Path | Why it must stay here |
  | --- | --- | --- |
  | pins | `dotfiles/provisioning/*.yaml` (`cli-tools`, `assets`, `config-copies`, `filesystem`, `packages`) | they are host policy: what THIS machine installs and at which tag |
  | host inventory + vars | `src/provisioning/ansible/inventory/`, `group_vars/` | distro/user/host facts the installer cannot know |
  | bootstrap entry | `bootstrap.sh` | the fresh-machine entry point |
  | composition gates | `Makefile` `GATES` (`gates-ci`, `deploy-coverage`, `ci-gates-parity`, …) | they assert the composed shape, not a package's internals |
  | docs | `ARCHITECTURE.md`, `docs/`, `_bmad-output/`, `openspec/changes/archive/**` | provenance |

  and **not**: any asset corpus file, any `src/<package>` source other than a pin, any per-file
  skeleton registration whose source is now assets. Consequence for the installer (S6): because the
  pins stay here, the installer must accept the manifests and inventory **from outside its own
  checkout** — today **8 roles** derive the repo root from their own playbook location, each with the
  same literal `{{ playbook_dir }}/../../../..`: `roles/assets/vars/main.yml:19`,
  `roles/compositor_configs/vars/main.yml:25`, `roles/config_copies/vars/main.yml:45`,
  `roles/btop_config/vars/main.yml:57`, `roles/cli_tools/vars/main.yml:8`,
  `roles/gui_tools/vars/main.yml:80`, `roles/zsh_config/vars/main.yml:19`,
  `roles/wlogout_config/vars/main.yml:10` (the last two name it `*_template_root`). That seam is
  **new work** with an exact gate in S6.
- **Evidence:** `AGENTS.md` §2 (the one permitted local `source:` is `dotfiles-runtime`);
  `scripts/deploy-coverage.py:1771-1819` (`assert_manifest_source_scope`);
  `dotfiles/provisioning/cli-tools.yaml:8-15`; `ARCHITECTURE.md:38-52`.

## Consistency Conventions

| Concern | Convention |
| --- | --- |
| Names | classes are exactly `icons`, `templates`, `configs`, `content`, `desktop`; spine dirs unchanged (AD-7); the repo name is OPEN-1 (working name `dotfiles-assets`) |
| Tag format | annotated `vMAJOR.MINOR.PATCH`, one per repo release, monotonic, never moved (AD-4) |
| Schema version | `schema_major` integer per schema file; independent of the tag (AD-12) |
| Branch / worktree | `ticket/<id>-<slug>` in `.worktrees/<id>/` via `scripts/worktree-guard.sh` |
| Commits | planning vs implementation separate; one class = land commit + pin/rewire commit + deletion commit |
| Manifest | `assets:` block is authoritative; role + verify mirrors are parity-locked (AD-6) |
| Deploy shape | `synchronize` with `delete: true` for directory classes (mirror, prune), `unarchive` for wallpapers, `copy` 0755 for scripts — the existing module choices, unchanged (`roles/assets/tasks/main.yml:90-136`) |
| Verify | required **minimum set** of named members, never counts, never full equality (AD-7) |
| Fetch idempotency | the clone is guarded on the tag dir being present (`creates:`-style stat, the `cli_tools` shape at `roles/cli_tools/tasks/main.yml:128-134`), so a converged run does not re-clone; the `pinned` record IS re-asserted every run — one expected `changed`, exactly like `cli_tools`' three (`ARCHITECTURE.md:286-290`) |
| Supply chain | anonymous HTTPS, no credential helper, no submodule, no LFS pointer, immutable annotated tags. The corpus is public by design (`ARCHITECTURE.md:560-561`); nothing secret may enter it, and `desktop/scripts/**` is shell-reviewed + `shellcheck`-gated because it is deployed 0755 |
| User-local files | never sources, never pruned: `kitty/local.conf` (`force: false`, `roles/kitty_config/tasks/main.yml:48-52`), a pre-existing `~/.zshenv` (timestamped backup, `roles/zsh_config/tasks/main.yml:111-121`), and `btop/active-theme` while OPEN-5 is open |
| Errors | a missing checkout, a bad schema, or a missing required binary fails loud with the path named; a missing optional degrades loudly (skip + report) |
| Docs | each repo's README states its public surface + how it is pinned; no doc names a path in another repo |
| Evidence | every repo `AGENTS.md` carries the Evidence + Verify rule verbatim from `mu` |

## Stack

| Name | Version | Note |
| --- | --- | --- |
| Python (installer/runtime) | `>=3.12` | unchanged (`src/provisioning/pyproject.toml:5`) |
| uv | `0.9.22` | host-observed `uv --version`; pinned in `bootstrap.sh` |
| ansible-core | `>=2.16` | unchanged (`src/provisioning/pyproject.toml:10`) |
| Jinja | via ansible-core | the render engine; no new templating library |
| JSON Schema | draft 2020-12 | the current published draft (`json-schema.org/specification`: "The current version is 2020-12", verified 2026-10-21); new use here — the icons + vars schemas; validator runs in assets CI only |
| shellcheck | CI-only | layer 1 of desktop validation (AD-10) |
| hitchhiker / `desktop-file-validate` | CI-only, optional | `.desktop` spec check; a stdlib `configparser`-based validator is the zero-dependency fallback |
| CI runner | GitHub Actions `ubuntu-latest` | one `gates.yml` per repo |

No new runtime dependency is introduced: the assets repo is data, and the installer renders with
the Jinja it already ships. Tool versions are read from the current tree (brownfield), not
re-verified on the web.

## Structural Seed

### Install-spine layout contract (what the installer writes, what the runtime reads)

```text
<install>/                                 # $XDG_DATA_HOME/dotfiles
  assets/
    pinned                                 # one line: vX.Y.Z
    <tag>/                                 # shallow clone at the tag, .git removed
      icons/{templates,mappings,schema.json}
      templates/**  configs/**  content/**  desktop/**
  icon-templates/                          # ← assets/icons/templates      [runtime reads]
  icon-mappings/                           # ← assets/icons/mappings       [runtime reads]
  wallpapers/default.png                   # ← assets/content/wallpapers   [runtime reads]
  config/
    hypr/ hyprpaper/ rofi/ wlogout/ nvim/ starship/   # ← assets/configs   [compositors read]
    zsh/.zshrc  kitty/kitty.conf  btop/btop.conf      # ← assets/templates RENDERED
    btop/themes/*.theme                    # ← assets/content/btop-themes + runtime pointer
    ags -> ../ags-apps/<tag>/bar           # ags_apps live link (NOT assets)
    color-scheme-generator/templates/      # ← csg pin checkout (NOT assets, AD-14)
    weg/effects.yaml                       # ← `weg dump-effects` (NOT assets, AD-14)
    {…}/settings.toml                      # ← settings role (NOT assets, AD-11)
$XDG_DATA_HOME/applications/*.desktop      # ← assets/desktop (layer-2 resolved)
$XDG_BIN_HOME/toggle-touchpad              # ← assets/desktop/scripts (0755)
<state>/dotfiles/{current,cache}           # runtime-owned (NOT assets)
```

**Read/write split.** The installer writes everything under `<install>/`, `$XDG_DATA_HOME` and
`$XDG_BIN_HOME` above. The runtime **reads** `icon-templates/`, `icon-mappings/`,
`wallpapers/`, `config/btop/themes/` and writes **only** `<state>/dotfiles/` + the consumer
pointers inside the spine (`current/`, `colors.*`, `config/ags/colors.css`). The assets repo is a
third party to both: it never writes anything.

### Provisioning order (unchanged except the assets roles' new source)

```text
packages → cli_tools → runtime_daemon → runtime_clipboard → filesystem
→ assets            # fetch <spine>/assets/<tag>/ ONCE, deploy icons + content + desktop
→ ags_platform → ags_apps
→ compositor_configs  # configs class (hypr/hyprpaper/rofi) + icons.json generation
→ gui_tools → config_copies  # configs class (nvim/starship/wlogout-layout/zsh dir)
→ settings → zsh_tools → zsh_config → wlogout_config → kitty_config → btop_config
                    # templates class, rendered
→ config_links → runtime_seed → display_manager  # templates class, rendered (become: true)
→ gloview_plugin → verify
```

`assets` must stay before every consumer of the corpus, and after `cli_tools` (the csg checkout copy
is fetched there). Order is load-bearing and already documented in
`playbooks/bootstrap.yaml:6-87`.

### Template render contract (one picture)

```text
assets repo                          installer repo                       spine
templates/kitty/kitty.conf.j2   ──>  roles/kitty_config/tasks: template  ──>  config/kitty/kitty.conf
templates/kitty/kitty.conf.         src: <assets checkout>/…                 (rendered, owned by
  vars.schema.json                  vars: kitty_config_state_current_dir       the installer)
   schema_major: 1                  (required[] parity-locked by test)
   required: [{name: STATE_DIR, …}]
   optional: []
```

## Class Contract and Lifecycle

| Class | Contents (measured today) | Contract (what a consumer may rely on) | Version trigger | Owner of the *values* |
| --- | --- | --- | --- | --- |
| `icons` | 117 SVGs / 12 groups (107 with `{{COLOR_*}}` placeholders, 10 static brand icons); 8 YAMLs (7 group maps + `defaults.yaml` vocabulary); `schema.json` | group → variants → `template` path relative to the templates root; placeholder vocabulary `COLOR_*` resolved by `defaults.yaml` > group > variant | MAJOR on a placeholder/vocabulary rename or a removed template path; MINOR on a new icon; PATCH on art | itr (tokens), runtime (hash input) |
| `templates` | zsh `.zshrc.j2` (11 vars), kitty `kitty.conf.j2` (1), btop `btop.conf.j2` (1), wlogout `style.css.tpl` (5), DM ×5 (1–3 each) | `<name>.j2` + `<name>.vars.schema.json`; no `default('')` on required; installer supplies every var (AD-8) | MAJOR on a required-var removal/retype or `schema_major` bump; MINOR on a new template; PATCH on wording | installer roles |
| `configs` | hypr 13 Lua, hyprpaper 1, rofi 1, wlogout `layout` 1, nvim 8, starship 1 | static file set, addressable per file; skeletons are repo-authoritative (`force: true`) | MAJOR on a path move; MINOR on a new file; PATCH on content | installer roles (no render) |
| `content` | `wallpapers.tar.gz` (82.6 MB, must contain `default.png`); `btop-themes/` (empty today) | tarball contract = a top-level `default.png`; theme files are `*.theme` matched by filename | MAJOR on the tarball contract change; MINOR on a new wallpaper/theme; PATCH on re-encode | runtime (`wallpaper set`), btop |
| `desktop` | 6 `.desktop` entries (zero `TryExec` today); 1 script (`toggle-touchpad`); `desktop.yaml` | spec-valid entry; `requires[]`/`optional[]` declared; scripts `shellcheck`-clean and 0755; every keybind-invoked name exists | MAJOR on a filename that must shadow a packaged entry; MINOR on a new entry; PATCH on flags | rofi `drun`, hypr keybinds |

## External Asset Exclusions

| Excluded | Where it lives instead | Why it cannot live in assets |
| --- | --- | --- |
| csg palette templates (`colors.*.j2`) | `csg` repo; read from `<install>/cli-tools/csg/<tag>/…` | they are part of `csg`'s own release (`dotfiles/provisioning/assets.yaml:18-28`) |
| AGS app assets (bar/overlays, icon-registry sources) | `ags-apps` unit; live links | deployed WHOLE, one tag, one owner (`roles/ags_apps/vars/main.yml:1-90`) |
| `icons.json`, rendered settings, palette/`current/` | spine, produced by `compositor_configs` / `settings` / runtime | derived or mutable — committing them creates a second truth (AD-11) |
| `btop/active-theme` | composition repo host vars **or** spine state (OPEN-5) | mutable user preference; a pinned corpus cannot hold it (AD-11) |
| Launcher wrappers (`rofi-ui`, `capture-ui`, …) | installer `cli_tools` role (Jinja) | they bake installed-binary paths; not static data (AD-10) |

## Resolved Decisions

**Owner:** inumaki · **Date:** 2026-10-21 · **Status:** nothing blocks S0; the five open questions
below are scoped so no slice depends on their answer before its own step that needs it.

| # | Question | Resolution | Source |
| --- | --- | --- | --- |
| — | Five entities / dependency edges | fixed, AD-1 | run constraint |
| — | Class structure (not version boundaries) | fixed, AD-3 | run constraint |
| — | One semver tag; schema versions separate | fixed, AD-4 + AD-12 | run constraint |
| — | Manifest shape; fetch-once into `<spine>/assets/<tag>/` | fixed, AD-5 + AD-6 | run constraint |
| — | DM templates move; installer keeps selection/packages/enablement | fixed, AD-9 | run constraint |
| — | Desktop three-layer validation | fixed, AD-10 | run constraint |
| — | Exclusions (csg templates, AGS assets, generated) | fixed, AD-14 | run constraint |
| — | mu-strict 13-item birth | fixed, AD-15 | run constraint |
| — | Destructive-last; dotfiles-v3 charter | fixed, AD-16 + AD-17 | run constraint |

## Deferred

| Deferred | Why it can wait |
| --- | --- |
| Splitting `configs` into per-tool directories inside the class | a directory layout choice, reversible inside one MINOR; S2 fixes it empirically |
| Git LFS / per-wallpaper files instead of one 82.6 MB tarball | 82.6 MB is under GitHub's 100 MB hard limit (over the 50 MB warning). Revisit only if the corpus grows past it (constraint in `SLICES.md` S1) |
| `verify` asserting asset **file hashes** (not just presence) | content-addressed proof is valuable but couples verify to every PATCH; presence + the runtime's own hashing covers today's risk |
| Publishing the corpus to a registry/CDN | git tag + shallow clone is the established channel (`ARCHITECTURE.md:560-561`) |
| Migrating `git history` per class (`subtree split`) | the corpus is data with low-value history; a single import commit per class is honest and cheaper (S1/S2/S3 record why) |
| Signing / SBOM for the corpus | no consumer verifies a signature today |

## OPEN QUESTIONS

Only genuinely unresolved items. Each names the slice that must not block on it.

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| OPEN-1 | **Assets repo name and hosting.** GitHub owner `RandomGenericUsername` is the established precedent and all pins are anonymous-HTTPS; the *name* (working name `dotfiles-assets`) and visibility are not decided. | S0 step 1 only | `dotfiles-assets`, public, owner `RandomGenericUsername` — matches the seven existing repos |
| OPEN-2 | **Does `configs` merge with `content`?** Both are static, non-templated blobs; separating them buys CI scoping and costs a class boundary that a later MINOR cannot undo cheaply. | S2 (which may fold proactively) | keep separate — the manifest already models five classes and merging is a MAJOR later |
| OPEN-3 | **Tag cadence for one repo spanning five classes.** Release on *any* class change (simple, frequent re-pins) vs batched releases (fewer bumps, a content fix waits for an unrelated template change). | S1 (first release) | release on any change; a PATCH is cheap and a batched tag hides which class changed |
| OPEN-4 | **Runtime schema support window.** How many `schema_major` majors the installer/verify accept concurrently (one-at-a-time vs N-1). | S5 (the compatibility assertion) | accept exactly one major (`schema_major == expected`); widen only when a real second major must coexist |
| OPEN-5 | **Where `btop/active-theme` lives.** It is a mutable preference inside a git-tracked repo today; assets cannot hold it (AD-11). Composition host vars or a spine/state file are both defensible. | S2 (it must not be copied as config) and S7 | move it to the spine as a host-owned file written by the studio, read by the renderer; do **not** put it in assets |

## Evidence Index

Per-decision evidence pointers: `EVIDENCE-INDEX.md`. Executable migration steps: `SLICES.md`.
Run memory: `.memlog.md`.
