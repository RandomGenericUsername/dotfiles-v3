# ARCHITECTURE.md — `dotfiles-v3`

## 1. Status

| | |
|---|---|
| Written | 2026-10-21 |
| Updated | 2026-10-23 (REQ-002: runtime extracted to its own pinned repo; composition-only) |
| Base commit | `e94fe8dc` (parent of the commit that adds this file; `git log -1`) |
| Scope | the host repo only — it consumes, it does not own, the pinned external repos |
| Kind | index over sources of truth, not a source of truth itself |

This file is the entry point, not the authority. Every section points at the file or
command that *is* authoritative. When this document and a cited file disagree, the
cited file wins and this document is the bug.

**How to keep this true**

```bash
make gates-ci          # the four executable gates (section 9)
make deploy-coverage   # provisioning shape only; prints the pinned manifests it read
openspec validate --all # 2026-10-23: 53 passed, 1 failed (pre-existing active change); see section 9
```

Anything else is prose drift. The two places that change most often are
`dotfiles/provisioning/cli-tools.yaml` (pins) and
`dotfiles/provisioning/installer.pin` (the engine tag; its verify role, read from
the cached checkout, says what a provisioned host must prove); update those
first, then this index.

## 2. What this repo is now

**One sentence: `dotfiles-v3` is an orchestration spine that provisions a Linux
desktop from pinned external artifacts; the runtime it drives (`dotfiles-runtime`)
is another pinned sibling.**

It authors no code. `make deploy-coverage` asserts `src/` is absent and the CLI
manifest carries zero local `source:` entries
(`scripts/deploy-coverage.py`, `assert_manifest_source_scope`). The installer engine
— its Python package AND its Ansible tree — is the pinned external
`dotfiles-provision` repo (`dotfiles/provisioning/installer.pin`); the runtime is
`dotfiles-runtime` at `v0.2.3`.

| The repo owns | The repo consumes |
|---|---|
| Declarative manifests (`dotfiles/provisioning/*.yaml`) and the installer pin (`installer.pin`) | The installer engine `dotfiles-provision` (its Python package + `ansible/` tree) as a pinned tag; its roles/playbooks are read from the cached checkout by the composition gates |
| Nothing under `src/` — the tree is asserted absent | `dotfiles-runtime` (CLI, daemon, clipboard watcher, cache/state) as a pinned repo; its `cli-output` / `cli-invocation-contract` pins live there; `config-assembler-engine` + `oci-runtime` as git-tag pins inside the CLI repos; the three CLIs + the runtime as `{name,repo,tag}` manifest entries (section 4) |
| Inputs: configs + Hyprland Lua + templates are the pinned `dotfiles-assets` classes; the btop active-theme is host state in the install spine (R-07) | `ags-apps` monorepo as one pinned unit (seven AGS apps + the capture-tool backend) |
| Gates and their scripts (`Makefile`, `scripts/*.py`) | `ags-platform` as one pinned unit (bare specifier, `node_modules` shortcut) |
| Docs, planning, and the historical record (`docs/`, `_bmad-output/`, `openspec/`) | System packages: pacman/apt + AUR (`roles/packages` in the pinned engine); a user-provided container engine (podman or docker) — **never installed by a role** (`bootstrap.sh:45-57`) |

Consequences that surprise newcomers:

- **No engine source lives here.** The installer's Python package and `ansible/`
  tree are the pinned `dotfiles-provision` tag; `bootstrap.sh` installs the pinned
  checkout and the composition gates read `.dev/dotfiles-provision-<tag>/`.
  The retired in-repo provisioning root is asserted absent.
- **No GUI source lives here.** The bar, clipboard overlay, notifications, capture
  tool, wallpaper selector, ICME and btop studio all deploy *whole* from the
  `ags-apps` unit (`ansible/roles/ags_apps/vars/main.yml:1-90` in the pinned engine).
- **No CLI or runtime source lives here.** `csg`/`weg`/`itr` and the runtime are
  `{name, repo, tag}` manifest entries; `src/cli-tools/`, `src/shared/` and `src/runtime/` are asserted absent (`scripts/deploy-coverage.py`).
- **The contract is not authored here either.** The event-contract conformance
  copies live in the `dotfiles-runtime` repo; that repo's
  `dotfiles-runtime:src/runtime/adapters/CONTRACT_PIN` (`dbdc5b8`) is the pin. The composition
  carries no `contracts/` directory.

## 3. Topology

```
                    system packages (pacman/apt/AUR)
                                |
   +---------------------+      |      +-----------------------+
   | dotfiles-v3 (host)  |<-----+      | ags-platform v0.2.0   |
   | provisioning        |             | ports + adapters      |
   | manifests, gates    |-- bare spec -> node_modules shortcut (unit)
   |                     |             +-----------+-----------+
   +----------+----------+                         ^ imports
              |                                    |
              | {name,repo,tag} / git tags  +------+-------------+
              v                             | ags-apps v0.4.0    |
   +----------+---------------------+       | bar, hypr-pano,    |
   | contracts v0.2.0               |       | notifications,     |
   |  event contract (Events1/2)    |       | capture-tool,      |
   |  cli-invocation-contract+kit   |       | wallpaper-selector,|
   +--+--------+--------+--------+--+       | icme, btop-studio  |
      |        |        |        |          +--------------------+
      v        v        v        |           live links: <install>/config/ags*
   +------+ +------+ +------+    |
   | itr  | | weg  | | csg  |    |
   | v0.2 | | v0.2 | | v0.2 |    |
   +--+---+ +--+---+ +--+---+    |
      +--------+--------+--------+
               v
   cli-output v0.1.0 · config-assembler-engine v0.1.0 · oci-runtime v0.5.0
   dotfiles-runtime v0.2.3 (pinned sibling; consumes contracts + cli-output)
```

**Direction rules (enforced by test, not by convention)**

| Rule | Where it is enforced |
|---|---|
| Libraries depend on no sibling repo; CLIs depend on libs + `contracts` only; no CLI imports/invokes another CLI | `_bmad-output/.../ARCHITECTURE-SPINE.md` AD-1; each repo's `tests/architecture/test_layering.py` |
| `dotfiles-v3` consumes CLIs/libs as pinned artifacts, never as a path, editable install, submodule or workspace | `scripts/deploy-coverage.py` (`assert_no_in_tree_cli_output`, `assert_pin_set`: no `path`, no `editable`) |
| The runtime never imports a CLI package — it spawns the console | `dotfiles-runtime` `tests/architecture/test_layering.py`; adapters use `subprocess.run` |
| Runtime never imports provisioning *code* (it reads provisioning output) | `dotfiles-runtime` `_FORBIDDEN_CROSS_PACKAGE = {provisioning, core, infrastructure}` |
| AGS apps import the platform, never each other | `docs/101-ags-platform-architecture.md` §3.1; `docs/HANDOFF-ags-platform.md` §5.1 (0 cross-app imports measured) |

## 4. The pinned repos

The ten pins this repo's manifests and gates declare directly: one contract repo + three libraries + three CLIs + the runtime + one data corpus + one installer engine. The two AGS units are pinned in the engine roles (section 6.5). All public, fetched
anonymously over HTTPS by tag (`openspec/changes/archive/2026-10-21-cli-tools-repos/POST-MIGRATION.md`
§1). Tags are annotated, monotonic, never moved; a fix is a new tag.

| Repo | Provides | First tag + semantics | Consumed how | Gates it owns |
|---|---|---|---|---|
| `contracts` | `event-contract.{json,xml,md}` + `generated/` bindings **and** `invocation-contract.json` + `cli_invocation_contract` (+ `testkit`) | `v0.2.0` — invocation contract DATA_VERSION 2 adds itr's required `ICON_RENDERER__TEMPLATES__DIR`; dual role, see below | Git tag in the runtime repo's `pyproject.toml`; event contract vendored into that repo's `src/runtime/domain/contract_generated.py` | `validate`, `generate`, `check-symmetry` / `contracts-drift`, `test`, `build` (`contracts/Makefile`) |
| `cli-output` | `cli_output` package — rendering/views only | `v0.1.0` (version continuity with in-tree 0.1.0) | Git tag in the runtime repo's `pyproject.toml` and in the pinned engine repo's own `pyproject.toml`, plus each CLI | `test lint hermetic lock-check docs-check` |
| `config-assembler-engine` | `config_assembler_engine` — resolution strategies, config assembly | `v0.1.0` | Git tag **only inside the three CLI repos** (not a dotfiles dependency) | same five |
| `oci-runtime` | `oci_runtime` — engine abstraction, build/run/exec, `resolve_build_context` | `v0.5.0` (imported code was 0.4.0; forward-only) | Git tag in `csg` and `weg` only | same five |
| `icon-templates-renderer` | console `itr` (pure Python, no container mode) | `v0.2.0` (reports `contract 0.2.0`) | `{name, repo, tag}` manifest + role mirror + verify pin | same five |
| `wallpaper-effects-generator` | console `weg` + `Dockerfile.imagemagick` + `image` verb | `v0.2.0` (reports `contract 0.2.0`) | same | same five + `image` |
| `color-scheme-generator` | console `csg` + four Dockerfiles + template catalog + `image` verb | `v0.2.1` — stale-labelled wrapper sweep (BUG-001); reports `contract 0.2.0` | same | same five + `image` |
| `dotfiles-assets` | **data corpus** (no package, no console script): `icons/` (templates + one group map + vocabulary), `templates/` (9 Jinja sources + 9 vars schemas), `configs/`, `content/`, `desktop/` (6 entries + `toggle-touchpad` + `desktop.yaml` `requires`/`optional` contract) | `v0.6.1` — **all five classes populated**, including the SDDM Wayland template and the wlogout Logout `uwsm stop` fix (BUG-005); `icons/schema.json`, every `templates/**/*.vars.schema.json` and `desktop/desktop.yaml` at `schema_major: 1` | `assets:` block in `dotfiles/provisioning/assets.yaml` + role/verify mirrors (+ a per-render-role pin mirror); fetched once into `<install>/assets/<tag>/` | `validate validate-icons validate-content validate-templates validate-desktop lint hermetic` |
| `dotfiles-runtime` | **host runtime** (console `dotfiles-runtime`): wallpaper apply/derive/reconcile, state/history, content cache, D-Bus daemon, clipboard watcher | `v0.2.3` — an absent optional intent root is informational (`optional_absent`), only required roots degrade (BUG-005); the mandatory palette order and icon-contrast prefs round-trip are kept | `{name, repo, tag}` in `dotfiles/provisioning/cli-tools.yaml`; installed from the tag-bearing checkout; verify asserts the checkout, `pinned` and `version` | `test lint contracts-check hermetic lock-check docs-check` (runtime repo) |
| `dotfiles-provision` | **installer engine** (console `dotfiles-provision`): the Python hexagon (`provisioning` package) + the Ansible tree (roles, playbooks, inventory, group_vars). The composition repo owns the manifests and gates; this repo owns nothing the engine also authors | `v0.1.17` — engine tag, annotated | `dotfiles/provisioning/installer.pin` (one semver tag, read by `bootstrap.sh` and the Python gates); installed self-contained from `git+…@tag` into `UV_TOOL_BIN_DIR` (the wheel carries `provisioning/_ansible`, R-15 closed); gates read the cached `.dev/dotfiles-provision-<tag>/` | `gates` (`test lint hermetic lock-check docs-check`) + CI-only `assets-parity`, plus its own CI |

**Two consumption shapes only** (`POST-MIGRATION.md` §2):

```toml
# 1. libraries + contract — each consumer's pyproject.toml
[tool.uv.sources]
cli-output = { git = "https://github.com/RandomGenericUsername/cli-output", tag = "v0.1.0" }
# 2. CLIs — dotfiles/provisioning/cli-tools.yaml
#    entries: [{name: csg, repo: …/color-scheme-generator, tag: v0.2.1}, …]
```

**`contracts` carries two contracts, and that is deliberate** (spine AD-4, OPEN-7
resolution): the **event contract** (`org.dotfiles.Events`, versioned `Events1`/`Events2`)
for the runtime ↔ AGS seam, and the **CLI invocation contract** (argv, env keys,
artifact names, exit codes, default timeout) for the runtime ↔ `csg`/`weg`/`itr` seam.
They share one repo and one tag because both are cross-repo seams with the same
charter. The **same-tag rule** follows: one `contracts` tag is pinned by the runtime
and by all three CLIs, and `verify` asserts each CLI's `--version` contract token
equals `0.2.0` (`roles/verify/vars/main.yml:221-272`).

### 4.1 The composition pin set (S7)

One table for every pin the composition repo owns. "Declared in" is the single
source of truth; everything under "Mirrors / lock" is a hand-maintained copy that
`make deploy-coverage` proves agrees. A pin bump edits the declared file first,
then its mirrors, then this table (`deploy-coverage`'s `assert_pin_set` fails on a
half-edit, recipe (a) in section 11).

| Pin | Declared in (one source) | Value (2026-10-23) | Mirrors / lock | Validated by |
|---|---|---|---|---|
| Installer engine `dotfiles-provision` | `dotfiles/provisioning/installer.pin` | `v0.1.17` | `bootstrap.sh` reads the file (never repeats the tag) and re-checks the semver shape; `scripts/engine_checkout.py` resolves the cached checkout for every gate | `deploy-coverage` (`assert_pin_set` + the engine checkout it reads); `ansible-embedded-template-lint` reads the same pin |
| Assets corpus `dotfiles-assets` | `dotfiles/provisioning/assets.yaml` → `assets.tag` | `v0.6.1` | engine `roles/assets/vars/main.yml` (`assets_repo`, `assets_pinned_tag`, `assets_classes`, `assets_schema_support`); `roles/verify/vars/main.yml` (`verify_assets_pinned_tag`, class dirs, schema window); per-consumer `{compositor_configs,config_copies,zsh_config,kitty_config,btop_config,wlogout_config,display_manager}_assets_pinned_tag`, plus `assets_csg_pinned_tag` and `settings_weg_image_tag` | `deploy-coverage` (`assert_assets_shape`, `assert_pin_set`); engine parity tests |
| CLIs `csg` · `weg` · `itr` + runtime `dotfiles-runtime` | `dotfiles/provisioning/cli-tools.yaml` (`{name, repo, tag}`) | csg `v0.2.1`; weg/itr `v0.2.0`; runtime `v0.2.3` | engine `roles/cli_tools/vars/main.yml` (`cli_tools:`); `roles/verify/vars/main.yml` (`verify_<name>_version`, tag-bearing checkout path, `pinned` record, `verify_<name>_contract_version: 0.2.0`; runtime uses `verify_runtime_version`/`verify_runtime_tool_version`) | `deploy-coverage` (`assert_cli_provisioned_from_pinned_manifest` + `assert_pin_set`) |
| **Not pinned here** (named so the set is honest) | — | runtime's `cli-output v0.1.0` and `cli-invocation-contract v0.2.0` are pinned in `dotfiles-runtime`; `config-assembler-engine v0.1.0` and `oci-runtime v0.5.0` live only in the CLI repos' `pyproject.toml`; `ags-platform` / `ags-apps` are pinned in the engine roles; uv is `0.9.22`, sha256-verified | owned by those repos / the runtime / the engine / `bootstrap.sh` | their own gates; `bootstrap.sh:246-301` |
| Vendored event contract (**a commit, not a tag**, by design) | `dotfiles-runtime` `src/runtime/adapters/CONTRACT_PIN` | `dbdc5b8` | the runtime repo's `contracts/` + embedded schemas are byte-identical copies | `make contracts-check` / `make contract-pin-check` in `dotfiles-runtime` |

`make deploy-coverage` is the one executable check of this table: it reads the
declared file, then the mirrors, and fails naming the half-edit. The engine
checkout it needs is cached at `.dev/dotfiles-provision-<tag>/`; see section 12
for the offline caveat (R-16).

## 5. Repo map of `dotfiles-v3`

| Path | What it is | Status |
|---|---|---|
| `src/` | **absent since REQ-002** — the runtime is the pinned `dotfiles-runtime` repo (`{name, repo, tag}` in `cli-tools.yaml`) | **absent; `assert_composition_only` asserts it** |
| `dotfiles/provisioning/installer.pin` | The installer-engine tag (`v0.1.17`) — the ONE source read by `bootstrap.sh` and the Python gates. The engine's Python + `ansible/` tree is the pinned external `dotfiles-provision` repo, installed from `git+…@tag` and cached at `.dev/dotfiles-provision-<tag>/` (gitignored) for the gates | **live** (single source for the engine pin) |
| `dotfiles/config/` | **absent since R-07** — the btop active-theme preference is host state in the install spine (`<install>/config/btop/active-theme`, written by the studio); all static config is the pinned assets `configs` class and all templates are its `templates` class | **absent; `assert_composition_only` asserts it** |
| `dotfiles/provisioning/assets.yaml` | The assets pin (`repo`, `tag`, `classes`) — the corpus itself is `dotfiles-assets` | **live** (single source for the corpus pin) |
| `dotfiles/applications/`, `dotfiles/scripts/` | **retired at S4** — the six `.desktop` entries and `toggle-touchpad` ship in `dotfiles-assets` `desktop/` | **absent; `deploy-coverage` asserts it** (AD-10/AD-16) |
| `dotfiles/provisioning/` | Declarative manifests: `cli-tools.yaml`, `assets.yaml`, `config-copies.yaml`, `filesystem.yaml`, `packages.yaml` + `installer.pin` | **live** (single source for pins) |
| `scripts/` | Gates: `deploy-coverage.py`, `ci-gates-parity.py`, `ansible-embedded-template-lint.py`; plus `worktree-guard.sh` | **live** |
| `contracts/` | **absent since REQ-002** — the event-contract conformance copies live in the `dotfiles-runtime` repo, which owns the vendored binding, embedded schemas and pin-check | **absent; `assert_composition_only`/`src` guard** |
| `dev/` | Incus VM harness (`dev/vm`, `vm-fresh.sh`, …) for disposable provision runs | **live, local-only** (needs incus; not in CI) |
| `.dev/` | Gitignored on-demand `ags-platform` checkout for `make ags-platform-dev` | live, disposable |
| `openspec/` | `specs/` + `changes/`; `changes/archive/**` is immutable history (spine AD-15) | live + historical archive |
| `_bmad/`, `_bmad-output/` | BMAD harness; planning + implementation artifacts (incl. the cli-repos spine) | historical record |
| `prototypes/`, `spikes/` | Throwaway probes (canvas/Hyprland/DBus/schema) | **historical** |
| `.worktrees/` | Gitignored worktrees created by `scripts/worktree-guard.sh` | live, never committed |
| `AGENTS.md`, `CLAUDE.md` (symlink), `README.md`, `docs/WORKSPACE.md`, `Makefile`, `bootstrap.sh` | The operating contract, composition overview, cross-repo ownership/pin map, gate set, fresh-machine entry point | live |
| `LICENSE`, `CHANGELOG.md` | MIT license + the 0.x split summary (S7); the authoritative record stays the spine/slices/residual ledger | live (product metadata) |

`src/cli-tools/`, `src/shared/`, `src/gui-tools/`, `src/runtime/`, the retired
in-repo provisioning root and `dotfiles/config/ags/` no longer exist as sources.
Their absence is a gate, not a memory (`scripts/deploy-coverage.py`,
`assert_no_gui_tools_dir` / `assert_no_cli_tools_dir` /
`assert_composition_only`).

## 6. Provisioning

### 6.1 bootstrap stages

`bootstrap.sh` is the only fresh-machine entry point (`bootstrap.sh:12-24`):

| Stage | What | Failure mode |
|---|---|---|
| preflight | `$HOME` set, non-root, **usable** container engine (`podman`/`docker` info, 15 s timeout) | abort before the long run (`bootstrap.sh:154-212`) |
| 1. uv preseed | pinned uv `0.9.22`, sha256-verified tarball, version asserted | abort (`bootstrap.sh:224-293`) |
| 2. engine install | fetch the pinned `dotfiles-provision` checkout (`.dev/dotfiles-provision-<tag>/`) for collections/inventory, then `uv tool install git+…@<tag>` into `UV_TOOL_BIN_DIR`; assert the console script runs (the wheel is self-contained — R-15 closed) | loud abort (`bootstrap.sh:329-368`) |
| 3. collections | `ansible-galaxy collection install -r <engine>/ansible/requirements.yml`, then assert collections actually landed | loud abort (`bootstrap.sh:370-414`) |
| 4. bootstrap | `dotfiles-provision --manifests-dir <repo>/dotfiles/provisioning --composition-root <repo> --inventory <engine>/ansible/inventory/localhost.yaml bootstrap` (+ forwarded become flags) | abort (`bootstrap.sh:495`) |
| 5. verify | `dotfiles-provision ... verify --expected-engine-tag <pin>` with `check=False` — a real gate, including the R-17 engine assertion | abort (`bootstrap.sh:501`) |
| post | if Hyprland IPC is reachable, warn `DEGRADED` when GloView is not loaded | exit stays 0 (`bootstrap.sh:513-532`) |

After bootstrap, `make provision ARGS="verify"` (or `plan`/`apply`) is the short form: it runs the
installed console from `UV_TOOL_BIN_DIR`. The retired in-tree `uv run --directory` form has no
engine checkout to point at (R-13).

### 6.2 role order

`bootstrap.yaml` is imports-only; the order is load-bearing and documented in its
header (`ansible/playbooks/bootstrap.yaml:6-87` in the pinned engine checkout):

```
packages → cli_tools → runtime_daemon → runtime_clipboard → filesystem → assets
→ ags_platform → ags_apps → compositor_configs → gui_tools → config_copies
→ settings → zsh_tools → zsh_config → wlogout_config → kitty_config → btop_config
→ config_links → runtime_seed → display_manager → gloview_plugin → verify
```

Why the seams sit where they do: `cli_tools` must precede `runtime_daemon` (the
unit's `ExecStart` names the installed binary) and `assets` (csg templates are copied
from the pinned checkout); `ags_platform` + `ags_apps` must precede
`compositor_configs` (it generates `icons.json` *through* the live-bar link and runs
the unit's `ags-bar-validate`); `runtime_seed` must precede `verify` (the palette and
icons it derives are a done-criterion).

### 6.3 spine layout (`$XDG_DATA_HOME/dotfiles`, default `~/.local/share/dotfiles`)

```text
<install>/
  cli-tools/
    csg/<tag>/                 # shallow clone at the pin, .git removed
    weg/<tag>/
    itr/<tag>/
    csg/pinned                 # one-line tag record, NEXT TO the tag dir
    weg/pinned
    itr/pinned
  ags-platform/<version>/      # platform unit; `pinned` beside it
  ags-apps/<tag>/              # monorepo unit (bar/, hypr-pano/, …); `pinned`
  config/
    ags -> ../ags-apps/<tag>/bar           # live link, not a dir
    ags-hypr-pano, ags-notifications, ags-capture, ags-icme,
    ags-wallpaper-selector, ags-btop-studio            # same shape
    node_modules/ags-platform -> ../../ags-platform/<version>
    color-scheme-generator/{settings.toml,templates/}
    weg/{settings.toml,effects.yaml}
    itr/settings.toml
    hypr/ hyprpaper/ nvim/ starship/ wlogout/ zsh/ kitty/ btop/ gtk-3.0/ gtk-4.0/ rofi/
  wallpapers/ icon-templates/ icon-mappings/
```

`config/ags` is deliberately **not** in `filesystem_spine_dirs` — it is a symlink, and
`stat.isdir` is false through a link, which once broke a real bootstrap
(`roles/filesystem/vars/main.yml:60-64`, mirror note in `roles/verify/vars/main.yml:98-104`).

### 6.4 CLI install path and image builds

Per pinned entry, `roles/cli_tools` shallow-clones `<repo>@<tag>` into
`<install>/cli-tools/<name>/<tag>/`, removes `.git`, writes `<install>/cli-tools/<name>/pinned`,
and installs **from that checkout** — never from a `git+…@tag` URL, so PEP 610 records a
tag-bearing path (`dotfiles/provisioning/cli-tools.yaml:8-13`; `scripts/deploy-coverage.py:1630-1670`).

Container-mode CLIs (`csg`, `weg`) then build images whose **tag is the pin**, never
`latest` (spine AD-7):

| CLI | Transport of the tag | Images verify asserts |
|---|---|---|
| `weg` | `install --image-tag {{ item.tag }}` | `weg-<engine>:<tag>` |
| `csg` | `COLORSCHEME__CONTAINER__IMAGE_TAG={{ item.tag }}` (its `install` verb has **no** `--image-tag`) | `csg-{base,custom,pywal,wallust}-<engine>:<tag>` |

`roles/cli_tools/vars/main.yml:58-77` splits the two transports; `deploy-coverage`
asserts both carry `{{ item.tag }}` and that no literal tag appears in task code
(`scripts/deploy-coverage.py:1676-1735`).

### 6.5 assets, settings, verify

- **assets** shallow-clones the **pinned corpus** `dotfiles-assets@v0.6.1` into
  `<install>/assets/v0.6.1/`, drops the clone's `.git`, writes `<install>/assets/pinned`, and then
  copies `icons/templates` → `icon-templates/`, `icons/mappings` → `icon-mappings/`, and unpacks
  `content/wallpapers/wallpapers.tar.gz` → `wallpapers/` from that checkout. S2: the two config
  roles read the same checkout's `configs/` class — `compositor_configs` renders the 15 non-bar
  skeletons (13 hypr Lua, hyprpaper.conf, rofi config.rasi) into `<install>/config/{hypr,
  hyprpaper,rofi}/`, and `config_copies` copies `nvim/`, `starship/` and wlogout's `layout`
  per file into `<install>/config/{nvim,starship,wlogout}/`. `hypr/hyprland.lua` carries one
  render-time token (the module include dir); the other 14 pass through byte-identically. S3: the
  five rendering roles read the checkout's `templates/` class and keep only the VALUES —
  `zsh_config` → `templates/zsh/.zshrc.j2`, `kitty_config` → `templates/kitty/kitty.conf.j2`,
  `btop_config` → `templates/btop/btop.conf.j2` (same pin as its authored themes: one mirror),
  `wlogout_config` → `templates/wlogout/style.css.tpl`, `display_manager` →
  `templates/display-manager/{sddm.conf,config.toml}.j2` (the other three DM files are retained
  fallback contracts, unrendered). Each role carries `<role>_assets_pinned_tag` +
  `<role>_assets_templates_dir`; its render `src` is `<that dir>/<group>/<file>` and every `dest`,
  `mode`, `become` and supplied var is unchanged from the pre-split task. `wlogout_config` also
  **prunes** the pre-S3 `<spine>/config/wlogout/style.css.tpl` (an idempotent `state: absent`),
  and `verify` asserts it stays absent. S4: `compositor_configs` also reads the checkout's
  `desktop/` class — six `.desktop` entries into `$XDG_DATA_HOME/applications/` and
  `toggle-touchpad` 0755 into the user bin dir — and **resolves `desktop.yaml` before the copy**
  (AD-10 layer 2): a missing `requires` binary fails naming entry and binary, a missing `optional`
  one is reported and that entry is skipped. `verify` re-asserts the deployed set, resolves every
  deployed `Exec` binary on PATH, and checks all seven keybind-invoked launchers are executable
  (layer 3). csg templates come
  from their own **pinned checkout**
  (`<install>/cli-tools/csg/<tag>/src/color_scheme_generator/defaults/templates`), and
  `config/weg/effects.yaml` is emitted via `weg dump-effects` (`roles/assets/vars/main.yml`). It
  mirrors the manifest's `assets:` block (`assets_repo`, `assets_pinned_tag`, `assets_classes`) and
  its csg pin (`assets_csg_pinned_tag`); parity tests lock both. A missing checkout fails loud
  before the first copy.
- **settings** is the only author of the three `settings.toml` files, rendered from role-internal
  Jinja into the spine (`roles/settings/vars/main.yml:1-90`); it carries a third pin mirror
  (`settings_weg_image_tag`).
- **verify** is read-only and checks **provisioned locations only** — never the repo
  (`roles/verify/tasks/main.yml:1-60`). Its job is the fourteen done-criteria plus the pin
  assertions a green `command -v` would hide: tag-bearing checkout path, `pinned` record,
  installed version = tag minus `v`, `--version` contract token = `0.2.0`, and every image at
  the tag-qualified reference (`roles/verify/vars/main.yml:221-272`).

### 6.6 manifest, mirror, parity

The pin mirrors are **hand-maintained copies**, not generated, because Ansible
roles cannot read the composition manifests. Every copy is gate-locked, so a pin
bump is a multi-file edit and a half-edit fails. Section 4.1 is the full pin set;
this table is the asset/CLI mirror inventory in detail.

| Copy | File | Locked by |
|---|---|---|
| Manifest (authoritative) | `dotfiles/provisioning/cli-tools.yaml` | — |
| Role mirror | `ansible/roles/cli_tools/vars/main.yml:104-114` (pinned engine) | `deploy-coverage` (`assert_cli_provisioned_from_pinned_manifest`) + structural parity test |
| Verify mirror | `ansible/roles/verify/vars/main.yml:231-272` (pinned engine) | same parity family |
| Assets manifest (authoritative for the corpus) | `dotfiles/provisioning/assets.yaml` (`assets:`) | — |
| Assets role mirror | `roles/assets/vars/main.yml` (`assets_repo` / `assets_pinned_tag` / `assets_classes`) | `TestAssetsVars.test_parity_with_manifest` |
| Assets verify mirror | `roles/verify/vars/main.yml` (`verify_assets_pinned_tag`) | `TestVerifyVars.test_assets_pin_mirrors_the_manifest` |
| Installer engine pin | `dotfiles/provisioning/installer.pin` | `bootstrap.sh` reads the file and re-checks semver; `deploy-coverage` `assert_pin_set` fails if the tag is repeated as a literal or the file is not read |
| Runtime library + invocation-contract pins | `dotfiles-runtime:pyproject.toml` `[tool.uv.sources]` | `deploy-coverage` `assert_pin_set` (git + semver only) + `uv.lock` |

Plus per-consumer mirrors where a role cannot read the manifest: `assets_csg_pinned_tag`,
`settings_weg_image_tag`, `btop_config_assets_pinned_tag` (ONE pin for the authored themes AND the
btop render template — both read the same checkout), `compositor_configs_assets_pinned_tag` and
`config_copies_assets_pinned_tag` (the static config corpus reads `configs/` from the same
checkout), and — since S3 — `{zsh,kitty,wlogout,display_manager}_assets_pinned_tag` (the four other
rendering roles read `templates/`). The five render-role mirrors plus the required-var parity are
locked by `tests/unit/test_template_vars_parity.py` against `assets.tag`, and their shape (each
render task reading `<install>/assets/<tag>/templates/`) by `deploy-coverage`. A pin bump is
therefore a multi-file edit: the manifest (+ its three literal entry sources), the role/verify
mirrors, and these per-consumer mirrors. The gate that proves it is `make deploy-coverage`
(section 11, recipe (a)).

### 6.7 become vs user scope

Only two plays escalate: `packages` (`become: true`,
`playbooks/packages.yaml:34`) and `display_manager` (system services,
`playbooks/display-manager.yaml:14`). Everything else — cli_tools, runtime units,
filesystem, assets, settings, config links, verify — is **user-scoped with no become**;
`cli_tools` states why: a root run would install into the wrong home
(`playbooks/cli-tools.yaml:4`).

### 6.8 Idempotency semantics

"Idempotent" here means **no state drift**, not "no `changed` report". The second
converged run legitimately reports `changed=7` on `cli_tools` and `changed=0`
everywhere else (`POST-MIGRATION.md` §A1.5). The changes (seven, grouped):

1. three `pinned` record writes (the claim is re-asserted every pass);
2. one `uv tool install --force` of `dotfiles-runtime` (`--force` always changes);
3. one transient smoke-probe tempfile;
4. the two image build loops (`csg` base+backends, `weg`) — **no `creates:`** on purpose:
   image existence does not imply freshness (`roles/cli_tools/tasks/main.yml:304-311`).

## 7. Runtime

`dotfiles-runtime` is its own pinned repo (console script `runtime.cli.main:app`) and a
hexagon: `domain` (pure, zero-I/O, stdlib allowlist), `ports`, `adapters`,
`application`, `cli` — each layer's allowed imports are a test
(`dotfiles-runtime:tests/architecture/test_layering.py:60-72`).

### 7.1 CLI surface

`wallpaper set` · `inspect {status,daemon,history,cache list}` · `icons {regenerate,preference}` ·
`gtk4 restart` · `daemon run` · top-level `reconcile`, `doctor`, `capture`, `clipboard`, `version`
(`dotfiles-runtime:src/runtime/cli/main.py`). `wallpaper set` is the visible-first apply → derive →
reconcile chain; `daemon run` is the resident hub, i.e. the `systemd ExecStart` surface.

### 7.2 CLI adapters — argv/env/artifacts, never stdout

The runtime couples to a CLI by **subprocess, exit status, artifact filenames and hashes**. It
does not import the CLI, does not parse stdout as JSON, and does not `command -v` to choose a binary.

| Adapter | argv | Injected env | Artifacts verified |
|---|---|---|---|
| `csg_adapter.py:280-300` | `csg generate <wallpaper> --format yaml --format conf --format gtk.css --format adw.css --format sequences --format rasi --format kitty --format btop.theme` | `COLORSCHEME__OUTPUT__DIRECTORY`, `COLORSCHEME__OUTPUT__OVERWRITE=true` | eight palette files, hashed |
| `weg_adapter.py:332-338` | `weg batch all -- <wallpaper>` | `WALLPAPER__OUTPUT__DIRECTORY` etc. | effect images, hashed |
| `itr_adapter.py:411-428` | `itr render [<icons.yaml>]` | `ICON_RENDERER__OUTPUT__OUTPUT_DIR`, `ICON_RENDERER__COLOR_SCHEME__PATH`, `ICON_RENDERER__TEMPLATES__DIR` | SVGs, hashed |

The env passed is an **allowlist**, not `dict(os.environ)`: exact keys (`PATH`,
`HOME`, `XDG_*`, locale/TLS/proxy), prefixes `COLORSCHEME__`, `WALLPAPER__`,
`ICON_RENDERER__`, `XDG_`, and a secret blocklist (`TOKEN`, `SECRET`, `PASSWORD`,
`AWS_`, `GITHUB_`) — `dotfiles-runtime:src/runtime/adapters/env.py:22-87`. Both sides
assert the same record through `cli_invocation_contract.testkit`
(`dotfiles-runtime:tests/unit/test_cli_invocation_contract.py:16-17`).

**ITR: `templates_dir` is BOTH a hash input and a render instruction** (contracts
`v0.2.0`). `ItrAdapter.render` hashes the `templates_dir` argument into the entry hash
(`itr_adapter.py:237`, then `icons_entry_hash` at `:321`) **and** forwards it as
`ICON_RENDERER__TEMPLATES__DIR` (`:411-418`) alongside
`ICON_RENDERER__OUTPUT__OUTPUT_DIR` and `ICON_RENDERER__COLOR_SCHEME__PATH`; argv is
`itr render [<icons.yaml>]` (`:420-428`) — still **no** `--template-dir`. The key is
`required` in the invocation record, so a consumer that omits it fails conformance
(`test_cli_invocation_contract.py`), and the adapter's literal wins over any host env
value because `build_env` applies its override map last (`env.py:87`): `itr` renders
from exactly the corpus `ih` covers.

The override ordering is the point: `itr` would otherwise resolve its
render templates from its own config chain — `[templates] dir` in
`~/.config/itr/settings.toml`, rendered by provisioning to `<spine>/icon-templates`
(`roles/settings/templates/itr-settings.toml.j2:8-9`) — which on a provisioned host is
the same path but on `DOTFILES_DEV_INPUTS_ROOT` (since S1: an assets checkout,
`icons/templates`) or behind a stale host var is not, leaving `ih`
describing a corpus the render never read. Each `variants[].template` is still joined
under that root with the group `template_dir` default `"."` (`itr`
`src/icon_templates_renderer/adapters/yaml_icon_config_loader.py:78,101`), so mapping
entries are spelled **relative to the templates root**
(`status-bar/battery/battery-0/default/icon.svg`) — a mapping-local `battery/` subdir
resolves to `<templates>/battery/…` and fails. The real-`itr` integration test no longer
monkeypatches the env (`test_itr_adapter_integration.py`): it hashes and renders the
checked-in corpus through the production path, so a dropped forward fails the test
instead of being papered over by the host environment.

### 7.3 Config resolution chain (CLI-side, unchanged by the split)

`--config` → env (`<PREFIX>__SECTION__KEY`) → cwd traversal → XDG
(`~/.config/<subdir>/settings.toml`) → packaged default (`docs/investigation/S3-config-flow.md` §0).
Provisioning does not fight this: it renders into the spine and symlinks `~/.config/<tool>` at it,
so native XDG discovery finds the rendered file. The *runtime's* input resolution is stricter — it
resolves the **install spine only**, consulting a repo checkout solely via the explicit
`DOTFILES_DEV_INPUTS_ROOT` override (`dotfiles-runtime:src/runtime/application/derive.py:12-13`).

### 7.4 State and cache

```text
$XDG_STATE_HOME/dotfiles/                 # json_state_repository.py:96-106
  current.json                            # the desired state
  current/                                # symlinks: colors.{conf,yaml,gtk.css,adw.css,
                                          #   sequences,rasi,kitty,btop.theme}, icons/
  cache/<layer>/<sha256>/meta.json        # layers: wallpapers,palettes,effects,icons
  history.jsonl                           # append-only, atomic, symlink-guarded
```

Cache layout is validated, not assumed: layer ∈ `{wallpapers,palettes,effects,icons}`, entry
name is 64-char lowercase hex, `meta.json` must carry `hash_algorithm: sha256`
(`dotfiles-runtime:src/runtime/adapters/cache.py:51-143`). Symlink repoints are atomic (tmp link +
`os.replace`, `seeder.py:88-102`); consumer pointers are a static table (`ags`, `gtk-3.0`,
`gtk-4.0`, `rofi`, `btop`) — adding one is a spec line plus its `@import`
(`adapters/consumer_path_spec.py:1-13`).

Clipboard history is separate: `$XDG_STATE_HOME/hypr-pano/history.json`, images under
`$XDG_CACHE_HOME/hypr-pano/` (`adapters/json_history_store.py:52-58`).

### 7.5 Daemon and clipboard services

| Unit | Type | Ordering / supervision |
|---|---|---|
| `dotfiles-runtime-daemon.service` | `Type=dbus`, `BusName=org.dotfiles.Events` | `Restart=always` (name loss is a *clean* stop), `RestartSec=5s`, `StartLimit 3/60s`, `TimeoutStartSec=90s`, `WatchdogSec=30` |
| `dotfiles-runtime-clipboard.service` | `Type=simple` (owns no bus name) | `After=dotfiles-runtime-daemon.service`, `Restart=always`, same StartLimit shape |

Both are installed into `~/.config/systemd/user/` and **symlinked into
`graphical-session.target.wants/`** rather than `systemctl enable`d, because the provisioner may
run with no user manager (`roles/runtime_daemon/tasks/main.yml:101-112`,
`roles/runtime_clipboard/tasks/main.yml:91-102`). The daemon ships `--activate` by default
(`runtime_daemon_activate: true`), i.e. it mutates; bare `daemon run` is observe-only
(`roles/runtime_daemon/vars/main.yml:14-24`).

Event bus: `org.dotfiles.Events` (interface `org.dotfiles.Events1`), job control via
`/org/dotfiles/Job` + `org.dotfiles.Job1.Control(action)`; the bar and the GTK4 subscriber consume
the same surface (`adapters/dbus_event_bus.py`, `bar_subscriber.py`, `gtk4_app_subscriber.py`).

### 7.6 `doctor`

Three-way drift detection over store, symlinks and cache entries — plus (R-5) store vs newest
`history.jsonl` record — classified `ok|missing|diverged|dangling`; read-only by default,
`--repair` quarantines and reconverges (`application/doctor.py:1-12`, `cli/main.py:1638-1645`).
Health depth is structural (existence + parse + presence), not artifact re-hashing.

## 8. Contracts

| | Event contract | CLI invocation contract |
|---|---|---|
| Question answered | what the runtime and AGS apps may say to each other | how the runtime invokes `csg`/`weg`/`itr` |
| Canonical home | `contracts` repo: `event-contract.{json,xml,md}` + `generated/` | `contracts` repo: `invocation-contract.json` + `cli_invocation_contract` package |
| Versioning | breaking change = new interface (`Events2`); both may coexist | `contract_version` in the JSON; a change is a new tag every consumer re-pins |
| In this repo | none — the runtime repo owns the vendored binding (`src/runtime/domain/contract_generated.py`) and conformance copies | the runtime repo's `pyproject.toml` |
| Drift gate | runtime repo `make contracts-check` → embedded schemas byte-equal canonical, wire XML agrees with JSON, baked tables equal generated bindings | runtime repo `make contracts-check` + `make contract-pin-check` |

The runtime repo owns the conformance gates. `make contract-pin-check` diffs each vendored copy
against `contracts/generated/` and **fails on a hand-edit**; it is deliberately not in that repo's
`GATES` (a CI runner has no sibling `contracts` checkout, so it would only skip). The negative
test proving it fails on a hand-edit is hermetic and runs via `contracts-check`.

**Same-tag rule:** one `contracts` tag (`v0.2.0`) is pinned by the runtime and all three CLIs,
and each CLI's `--version` token must equal it; neither side duplicates the contract data in
tests (spine AD-4).

## 9. Gates

### 9.1 `gates-ci` = `GATES` (no exclusions today)

| Target | What it proves |
|---|---|
| `ansible-embedded-template-lint` | no `{{ }}` nested inside a Jinja *expression* string (`assert.that`, `when`, …) — the construct ansible-core 2.23 disables |
| `deploy-coverage` | provisioning **shape**, read from the PINNED engine checkout: no per-file bar/app sources, both external units installed + live links, pinned CLI manifests installed from tag-bearing checkouts, image tag = pin, retired trees absent, **zero local `source:` entries**, the installer engine pinned in `installer.pin` (not a CLI entry), the whole **composition pin set** semver + mirrored (installer ↔ bootstrap, assets ↔ role/verify, CLI + runtime tags ↔ manifest/role/verify), and the terminal composition-only shape (`src/` absent; `dotfiles/` = `provisioning/`) |
| `ci-gates-parity` | `.github/workflows/gates.yml` job set equals `gates-ci` in both directions, modulo declared `RENAMES` / `CI_ONLY_EXEMPT` / `CI_EXCLUDED_GATES` (all empty) |
| `per-app-drift-symbol-suites` | currently a legible no-op: every in-repo drift suite moved to `ags-apps` with its app |

`make hermetic` is **intentionally a no-op PASS**: `HERMETIC_PACKAGES` is empty — the seven
extracted packages run their own `make hermetic` in their pinned repos; the target stays so a
future in-repo package can be listed. The installer engine runs its own `make hermetic` in the
pinned `dotfiles-provision` repo.

### 9.2 Per-repo gate sets

The seven extracted repos run their own gate sets: the six packages use
`test lint hermetic lock-check docs-check` (plus `image` for `csg`/`weg`, `test-all` for `itr`)
and `ci-gates-parity`; `dotfiles-runtime` uses
`test lint contracts-check hermetic lock-check docs-check` and `ci-gates-parity`. All are measured
green from a foreign cwd with `make -C <repo> gates`. `ags-apps` owns the GUI gates
(`bar-typecheck`, `ags-test`, per-app typecheck/test/drift) — not this repo's, and never to be
re-added here.

### 9.3 Known pre-existing failures (name them, do not rediscover them)

| Failure | Count / shape | Status |
|---|---|---|
| `dotfiles-runtime` suite | moved with the runtime repo; its own CI owns the suite, including the recording-indicator bar check | tracked in `dotfiles-runtime` |
| `dotfiles-runtime` integration | `test_weg_adapter_integration_real_binary` passes on a provisioned host and skips when the CLI binary is unavailable | environment-dependent by design; tracked in `dotfiles-runtime` |
| `openspec validate --all` | `53 passed, 1 failed (54 items)` on 2026-10-23 — the pre-existing active change `redesign-ags-audio-panel`; `--strict` reports 30 warnings (24 passed) from the legacy spec-shape class | pre-existing; the REQ-002 change validates strictly |
| REQ-002 host verify | `make provision ARGS="verify --expected-engine-tag v0.1.12"` → exit 0 on 2026-10-24; engine 0.1.9, runtime 0.1.0, all verify tasks ok | proven on the live host |
| REQ-002 fresh-machine proof | `dev/vm` bootstrap + `verify` was **not run** (`incus` absent) | pending on a VM-capable host |

Re-measured 2026-10-24 after the engine `v0.1.12` wheel fix: `make gates-ci` exit 0 (four gates), `make provision ARGS="verify --expected-engine-tag v0.1.12"` exit 0 on the live host;
`openspec validate --all` → `Totals: 53 passed, 1 failed (54 items)`; `make deploy-coverage`
exit 0 with engine `v0.1.12` and runtime `v0.1.0`; `make hermetic` PASS. The 2026-10-22 baseline
was `108 passed, 27 failed (135 items)` after the assets split; the active-change/spec-shape
failures are unchanged in class.

## 10. Operating discipline

1. **Never work on `master`.** `bash scripts/worktree-guard.sh check-clean` then
   `bash scripts/worktree-guard.sh create <id> <slug>` → `.worktrees/<id>/` on
   `ticket/<id>-<slug>` (gitignored, inside the repo). Merge only on green gates (`AGENTS.md` §1).
2. **Evidence rule.** Every non-trivial claim carries a command + observed result, or a path +
   line range; if the evidence does not exist yet, say so (`AGENTS.md` §3).
3. **Planning vs implementation in separate commits** (`AGENTS.md` §4).
4. **Gates by execution, never by reading a diff.** `make gates-ci` plus the per-file gate.
5. **Retire a gate by deleting it**, never by leaving it pointing at a tree the repo no longer
   owns (`docs/LESSONS-ags-apps-migration.md` §5; spine AD-14).
6. **Destructive-last loop** (spine AD-13), per target: create repo + import + tag → rewire
   consumption to the pin → **prove by execution** → delete the in-tree copy *and every
   reference it orphaned* **in the same slice** → merge; the next target waits for that merge.
   Rollback = pin bump + revert of the deletion commit; a published tag is never moved.

### 10.1 mu-strict repo birth checklist

A repo is not a valid extraction target until all of these are in the initial import
commit (harness) or the first release commit (product metadata). Source: `_bmad-output/.../ARCHITECTURE-SPINE.md` § "Repo Birth Checklist (mu-strict)" — *that
section has 13 numbered rows; this is all 13, not a subset.*

| # | Item | Proved by |
|---|---|---|
| 1 | `AGENTS.md` with evidence + worktree + planning-vs-code rules, copied from `mu` | `rg -c "Evidence:\|Verify:" AGENTS.md` ≥ 2 |
| 2 | `CLAUDE.md` → `AGENTS.md` symlink | `test -L CLAUDE.md` |
| 3 | `tickets/` (INDEX, LIFECYCLE, `_template/`, `_fixtures/`) | `rg -c "Gate .*:" tickets/LIFECYCLE.md` ≥ 6 |
| 4 | executable `scripts/worktree-guard.sh`, byte-identical to `mu` | `check-clean` exit 0 |
| 5 | `.agents/skills/` + `skills-lock.json` (7 hash-pinned skills) | hashes match `mu` |
| 6 | `_bmad/` | `python3 _bmad/scripts/memlog.py --help` exit 0 |
| 7 | `openspec/` (config + specs + changes) | `openspec validate --specs` exit 0 |
| 8 | `pyproject.toml` (hatchling, version, console script where applicable) + committed `uv.lock` | `uv lock --check`, `uv build` |
| 9 | `Makefile` with `help sync test lint format gates build install`, anchored on `$(CURDIR)` | `make sync && make gates` on a fresh clone |
| 10 | hermetic fixture + canary | `make hermetic` with empty XDG/HOME, foreign cwd |
| 11 | `.github/workflows/gates.yml` + `ci-gates-parity` | parity script PASS |
| 12 | `README.md` (public surface + how dotfiles pins it), `CHANGELOG.md`, `LICENSE` | `make gates` docs check |
| 13 | `docker/` only for csg/weg | `make image`; no `src/shared`/`src/cli-tools` in a Dockerfile |

The six packages and `dotfiles-runtime` satisfied the checklist by execution (the runtime's
`v0.1.0` birth follows the same rows), with the two paperwork gaps closed by the POST-MIGRATION
addendum (`POST-MIGRATION.md` §A2). `contracts` predates the checklist
and ships `validate`/`generate`/`check-symmetry`/`contracts-drift`/`test`/`build`
rather than a `gates` target. `dotfiles-v3` is a composition repo, not a birth
target, but it now carries the same product metadata rows 12 requires — MIT
`LICENSE` + `CHANGELOG.md` (S7) — and `make deploy-coverage` validates its pin set
(section 4.1).

### 10.2 Two rituals, one checklist each

- **Pin bump:** the declared file in section 4.1 is authoritative and every mirror is gate-locked (section 6.6); the end-to-end checklist is recipe (a) in section 11.
- **Destructive-last:** item 6 above. Rollback is always a pin bump plus a revert of the deletion commit — never a retag.
- **Composition-only:** a new corpus file goes to the pinned `dotfiles-assets` repo (bump its tag); a new role/playbook goes to the pinned `dotfiles-provision` repo (bump `installer.pin`); a new library or CLI goes to its own repo. This repo extends a pin — `assert_composition_only` fails on a new authored tree under `src/` or `dotfiles/`.

## 11. Extension recipes

### (a) Bump a pin end-to-end

1. Tag the source repo (annotated `vX.Y.Z`; never move the old tag).
2. Manifest: `dotfiles/provisioning/cli-tools.yaml` (`tag:` for a CLI).
3. Role mirror: `roles/cli_tools/vars/main.yml` (`cli_tools:`).
4. Verify mirror: `roles/verify/vars/main.yml` (`verify_<name>_version`, checkout path, pin file, `verify_<name>_contract_version` if the contract moved).
5. Role-local mirrors the source feeds: `roles/assets/vars/main.yml` (`assets_csg_pinned_tag`), `roles/settings/vars/main.yml` (`settings_weg_image_tag`), `roles/btop_config/vars/main.yml` (`btop_config_assets_pinned_tag`).
5a. **Assets corpus**: tag `dotfiles-assets`, then bump `assets.tag` in `dotfiles/provisioning/assets.yaml`, the three `<install>/assets/<tag>/...` entry sources, `roles/assets/vars/main.yml` (`assets_pinned_tag`), `roles/verify/vars/main.yml` (`verify_assets_pinned_tag`), and the five per-consumer mirrors: `roles/{compositor_configs,config_copies}/{vars}` plus `roles/{zsh_config,kitty_config,btop_config,wlogout_config,display_manager}/vars/main.yml` (`<role>_assets_pinned_tag`; btop's one mirror feeds both its themes dir and its render template). The parity tests named in 6.6 fail on any half-edit.
6. If a library or `contracts` moved: bump `[tool.uv.sources]` in the `dotfiles-runtime` repo, then `uv lock` there. If the INSTALLER engine moved, bump the tag in `dotfiles/provisioning/installer.pin` (the one source `bootstrap.sh` and both composition gates read).
7. If the contract moved: re-vendor the binding in `dotfiles-runtime`, update `CONTRACT_PIN`, run `make contract-pin-check` against a sibling `contracts` checkout.
8. Prove: `make deploy-coverage` (the pin-set assertion in section 4.1 fails on any half-edit), `make gates-ci`, the runtime repo's `make gates`, and on a host `dotfiles-provision verify` (the only place the pin is asserted *by execution*). Update the value in the section 4.1 table last.

### (f) Bump the installer engine pin

1. Tag `dotfiles-provision` (annotated `vX.Y.Z`; never move the old tag) and release it.
2. `dotfiles/provisioning/installer.pin` — the ONE source. `bootstrap.sh` and both composition gates read this file; never paste the tag into `bootstrap.sh` (`assert_pin_set` rejects the literal).
3. Warm the cache at the new tag: `git clone --depth 1 --branch vX.Y.Z https://github.com/RandomGenericUsername/dotfiles-provision .dev/dotfiles-provision-vX.Y.Z` (or let the gate fetch it once with network access).
4. Prove: `make deploy-coverage` (`CHECK pinned installer engine vX.Y.Z at …/`) and `make gates-ci`; on a host, `bootstrap.sh` then `dotfiles-provision verify`. R-17 records that `verify` does not yet assert the engine tag itself — step 4's `CHECK` line is currently the only pin-vs-tag proof for the engine.

### (b) Add a new CLI tool

1. Create the repo with the birth checklist (section 10.1): one package, repo root = package root, console script, `contracts` pin if it joins the invocation contract.
2. Add `{name, repo, tag}` to `dotfiles/provisioning/cli-tools.yaml`.
3. Mirror it in `roles/cli_tools/vars/main.yml` (`cli_tools:`); add it to `cli_tools_image_build_names` only if it has container mode.
4. Add its pins to `roles/verify/vars/main.yml` and its binary to `verify_cli_tools`.
5. If it ships assets, add an `assets_*` mirror + parity test (`roles/assets/vars/main.yml`).
6. If the runtime drives it, add an adapter — subprocess + allowlisted env + artifact hashing, never stdout parsing (section 7.2).
7. Prove: `make deploy-coverage`; add an assertion only for a special transport (like csg's env-var image tag).

### (c) Extract another in-repo thing

1. Work the destructive-last loop (section 10.2): create → import (history) → tag → rewire → prove → delete **and** remove the orphaned references (docs, `.gitignore`, fallbacks) → merge.
2. Add both halves to `scripts/deploy-coverage.py`: directory gone **and** no `pyproject.toml` pins it by `path` (copy `assert_no_in_tree_cli_output`, `:1360-1398`).
3. Move its gates to the new repo and delete the corresponding entries here (a gate pointing at a moved tree is a gate nobody runs).
4. Update `AGENTS.md` §2, this file, and the `docs/` tables that named the tree.

### (d) Add a config skeleton file

Mandatory for the **non-bar** skeletons (hypr / hyprpaper / rofi):

1. Add the source under `configs/<tool>/` in the pinned `dotfiles-assets` repo and tag it.
2. Register it in the pinned engine repo's `ansible/roles/compositor_configs/vars/main.yml` (`compositor_configs_skeleton_files`) and bump `dotfiles/provisioning/installer.pin`.
3. Mirror it in the engine's `ansible/roles/verify/vars/main.yml` (`verify_compositor_skeleton_files`) if verify must assert it.
4. Prove: `make deploy-coverage` (reads the cached engine checkout) and the engine repo's own role tests.

Do **not** register a bar file: the bar deploys whole from `ags-apps`, and a per-file entry would template into the unit tree through the live link.

### (e) Add a gate

1. Add the target to `GATES` in the `Makefile` (never a second list; `gates-ci` inherits it).
2. Add one matching job to `.github/workflows/gates.yml` (or a `RENAMES` entry in `scripts/ci-gates-parity.py`).
3. If it cannot run on a stock runner, declare it in `CI_EXCLUDED_GATES` / `CI_SELF_HOSTED_GATES` with a reason — never leave it silently absent.
4. Prove: `make ci-gates-parity` and `make gates-ci` both exit 0.

**Docs/gate-only corrections (R-12).** Batch documentation corrections before tagging. After a
tag, never move it: cut a new PATCH. If the corrected file is not a consumed surface (README,
CHANGELOG, gate script), record the correction and leave consumer pins unchanged; bump the pin
only when the corrected file is a consumed surface (`catalog.yaml`, a schema, or corpus bytes).
`dotfiles-assets v0.5.1` (the `validate-configs` gate, zero corpus bytes) is the dry run.

## 12. Known constraints and residuals

- **No PyPI, no registry.** Consumers pin git tags; images build at provision time from the pinned checkout and are never published or digest-pinned (spine OPEN-2/OPEN-3; `POST-MIGRATION.md` §A1.3).
- **Pins must be public and anonymously fetchable.** Provisioning clones over anonymous HTTPS with no credential helper; a private repo breaks `ansible.builtin.git` (`roles/ags_apps/vars/main.yml:88-90`; `openspec/specs/cli-repo-birth/spec.md:98-120`). Every pinned repo was verified public.
- **The engine install is a tag artifact** (R-15 closed in engine `v0.1.1`). The wheel carries
  `ansible/` as `provisioning/_ansible`, so `bootstrap.sh` installs `git+…@<tag>`; the cached
  `.dev/dotfiles-provision-<tag>/` checkout remains for `ansible-galaxy`/inventory and the gates.
- **Composition gates need the cached engine checkout** (R-16). `deploy-coverage` and
  `ansible-embedded-template-lint` resolve `.dev/dotfiles-provision-<tag>/` on demand; with no
  cache and no network they fail loudly naming the pin and cache path (they never fall back to an
  in-repo copy). Set `DOTFILES_PROVISION_OFFLINE=1` to turn a miss into one sentence with no clone
  attempt; a pre-populated cache still gates offline.
- **The engine tag is asserted by `verify`** (R-17 closed in engine `v0.1.1`). `bootstrap.sh`
  passes `--expected-engine-tag <pin>`; the role compares the installed console version and fails
  naming both tags. `engine_checkout.py` still validates the cached checkout for the gates.
- **Builds happen on the host, at provision time**, so `verify` needs a working container engine; `bootstrap.sh` refuses to start without one.
- **No VM in CI.** `dev/` drives an incus VM, but `incus` is absent on this host and no workflow
  references it; the fresh-machine VM run is **deferred/accepted** (2026-10-23), not scheduled
  (`POST-MIGRATION.md` §A3 gap (a); `RESIDUALS.md` R-10). Host apply, host `verify`, and the CI
  gates are the executed evidence; do not claim VM evidence until `make vm-verify` runs in a guest.
- **Host-specific systemd pitfall.** A unit `ExecStart` line ending in a Jinja *block* tag (e.g. `{% endif %}`) swallows the next line (Ansible `trim_blocks`) → systemd runs `daemon run# …` → `No such command 'run#'` → `start-limit-hit`. Keep `runtime_daemon_run_flags` single-line (`roles/runtime_daemon/vars/main.yml:26-35`).
- **Stale uv-tool envs after moving/deleting a tree.** `uv tool list` can report the right version while the env's `direct_url.json` points at a deleted path, so every console dies with `ModuleNotFoundError`. After a tree-deletion merge: `rm -rf <retired root>` in the checkout you are about to gate, then `make deploy-coverage` *there* — absence guards read the filesystem, not `git ls-files` (`POST-MIGRATION.md` §1 note, §A1.2).
- **`csg install` has no `--image-tag`** (the tag travels via `COLORSCHEME__CONTAINER__IMAGE_TAG`); `csg install --image-tag …` exits 2. The tag gate is clone + `verify`, not option parsing (`POST-MIGRATION.md` gap (c)).
- **`openspec validate --all` keeps 27 failures** — 19 legacy change-level + 8 legacy spec-shape defects, none `cli-tools-repos` or `assets-repo-split` (`POST-MIGRATION.md` gap (e); re-measured 2026-10-22: `108 passed, 27 failed (135 items)`).
- **Literal stale-path text remains** in the guard, its negative-test fixtures and read-only investigation docs — 338 lines in 9 files on 2026-10-21 (`POST-MIGRATION.md` gap (f)). The **test-side** half of that residue is removed + guarded by `dotfiles-runtime:tests/architecture/test_no_retired_sources.py` (`94b3f4a0`): the retired-tree discovery walks in `dotfiles-runtime:tests/integration/test_csg_determinism.py`, `tests/integration/test_itr_adapter_integration.py`, `tests/unit/test_csg_adapter.py` and `tests/unit/test_itr_adapter.py` are gone, and the two integration files share explicit resolution in `tests/integration/conftest.py` (`resolve_csg_templates_dir` / `resolve_icon_templates_dir`: env override → pinned CLI corpus / the provisioned spine's `icon-templates` (assets checkout override, since S1) → loud skip, never a silent pass). The guard fails on any reintroduced contiguous `src/cli-tools` / `src/shared` / `src/gui-tools` literal **or** the `"src" / "<retired>"` path-join form (`rg` misses the latter), in production or tests, and names the spine / pinned-repo fix. It runs in `gates-ci` as the `runtime-architecture` gate (`d67849ba`), so it is enforced on every push rather than only when someone runs pytest by hand.
- **CSG templates dir is a required caller input — residual resolved** (`e8fc0916`). The retired repo-relative discovery is gone: `_find_default_templates_dir` — which walked file ancestors for the stale in-tree csg checkout under the retired `src/cli-tools/color-scheme-generator/...` — and its `generate` call site were deleted. `CsgAdapter.generate` now raises a `FileNotFoundError` that names the cause and the fix (`templates_dir` must be resolved from the provisioning spine and passed by the caller) **before** hashing or spawning a subprocess, while `__init__` stays side-effect-free so `CsgAdapter().is_available()` remains legitimate. The regression test in the runtime repo asserts the message names `templates_dir` and that `subprocess.run` was never called; the guard (`test_no_retired_sources.py`) runs in that repo's `make gates`.
- **Per-app repo split is deferred** (GUIDE §7 exit gate unmet); `ags-apps` stays a monorepo consumed as one unit (`docs/HANDOFF-ags-platform.md` §2).

## 13. Documentation index

Repo docs (`docs/`), one line each. "Normative" = a live source of truth; "historical" =
provenance, not to be edited into agreement with today. Spine artifacts sit under
`_bmad-output/planning-artifacts/architecture/architecture-cli-repos-2026-10-19/`
(the CLI split) and `…/architecture-assets-split-2026-10-21/` (the corpus + engine
split; its `RESIDUALS.md` is the live residual ledger and
`openspec/changes/archive/2026-10-22-assets-repo-split/POST-MIGRATION.md` is the
closure record).

| Document | What it is | Status |
|---|---|---|
| `docs/99-dotfiles-hexagonal-architecture.md` | Dual-domain vision + Domain 1 as-built; runtime phases 2–6 are **planned, not built** | normative (Domain 1) / historical (Domain 2) |
| `docs/01-dotfiles-provisioning-phase1-plan.md` | Phase-1 provisioning plan + Epic-4 amendment (removes `default_palette`/`icons`/`generated/`) | historical, amended |
| `docs/02-config-in-spine-pattern.md` | Config-in-spine decision record (spine + symlinks + backup guard) | normative |
| `docs/100-ags-bar-rearchitecture.md` | Bar re-architecture exploration + prototype log | historical |
| `docs/101-ags-platform-architecture.md` | AGS platform design of record (ports, schemas, icon contract); the bar pin note is `v0.4.1` (the `ags-apps` monorepo unit) | normative |
| `docs/HANDOFF-ags-platform.md` | Roadmap, working manner, environment facts, pin ladder (lags `v0.4.0`) | historical |
| `docs/HANDOFF-bar-rearchitecture.md` | Context handoff for the bar work | historical |
| `docs/GUIDE-ags-app-repos-refinement.md` | Decided topology + the deferred per-app-split exit gate | normative (topology) |
| `docs/GUIDE-ags-overlay-performance.md` | Conditional rule for on-demand overlay open cost (AD-24) | normative, conditional |
| `docs/LESSONS-ags-apps-migration.md` | Process lessons (one unit/one gate, retire gates by deletion, `$(CURDIR)`) | normative |
| `docs/Adding an Icon — ITR and Provisioning Pipeline.md` | How adding an icon flows template → asset → render | normative guide |
| `docs/Hyprland Screenshot & Screen Recording Tool — Full Project Plan.md` | Capture-tool project plan (app now in `ags-apps`) | historical |
| `docs/ags-restart-vs-live-theme-refresh.md` | Restart an AGS app vs live-refresh its CSS | normative |
| `docs/ags_tray_statusnotifier.md` | Tray investigation + implementation notes | mixed |
| `docs/tray-app-integration-playbook.md` | Precedent playbook for tray menu/icon failures | normative |
| `docs/POLKIT_AGENT_INTEGRATION.md` | PolicyKit agent — **blocked** on an Arch package ABI issue | historical |
| `docs/hyprspace_guide.md` | Hyprspace plugin install/config guide | reference |
| `docs/linux-wayland-pipewire-ags-audio-control.md` | Audio-control design (PipeWire/WirePlumber/AGS) | reference |
| `docs/ags_global_menu_investigation.md` | Hyprland has no KDE AppMenu protocol — feasibility finding | historical |
| `docs/Animated_Icon_Loader_Findings.md` | Investigation; interim decision = `Gtk.Spinner` | historical |
| `docs/investigation/S1-runtime-cli-addressing.md` | Evidence-only: how the runtime addresses/invokes the CLIs | historical (pre-split) |
| `docs/investigation/S2-provisioning-addressing.md` | Evidence-only: the pre-split provisioning addressing chain | historical |
| `docs/investigation/S3-config-flow.md` | Evidence-only: CLI settings resolution chain | normative evidence |
| `docs/investigation/S4-reference-inventory.md` | Evidence-only: pre-split reference/deletion blast radius | historical |
| `…/architecture-cli-repos-2026-10-19/ARCHITECTURE-SPINE.md` | Binding decisions AD-1…AD-16 + birth checklist | **normative** |
| `…/architecture-cli-repos-2026-10-19/SLICES.md` | Executable migration slices S0a–S6 | historical plan |
| `…/architecture-cli-repos-2026-10-19/EVIDENCE-INDEX.md` | Per-decision evidence pointers | historical index |
| `openspec/changes/archive/2026-10-21-cli-tools-repos/POST-MIGRATION.md` | Closure record: what landed, with commands + observed output | **normative for the split** |

Normative non-documents: `AGENTS.md`, `Makefile`, `openspec/specs/**`, and each role's `vars/`.

## 14. Glossary

| Term | Meaning here |
|---|---|
| **spine** (this repo) | `dotfiles-v3` as the orchestration host: provisioning + runtime + manifests + gates |
| **spine** (filesystem) | `<install>` = `$XDG_DATA_HOME/dotfiles` — the single home for managed config/data; `~/.config/<tool>` symlinks into it |
| **pin** | An immutable annotated git tag (`vX.Y.Z`) that a consumer addresses; a fix is a new tag |
| **manifest entry** | One `{name, repo, tag}` record in `dotfiles/provisioning/cli-tools.yaml`; `{name, source}` is permitted only for `dotfiles-runtime` |
| **live link** | `<install>/config/ags*` → the pinned `ags-apps` unit subdir; the live app *is* the tag, so no per-file copy can drift |
| **unit** | A whole versioned install directory (`ags-platform/<version>/`, `ags-apps/<tag>/`), consumed as one thing, rolled back by repointing |
| **hermetic** | Test run with `HOME` + the four `XDG_*` vars scrubbed into a throwaway tree; in *this* repo `make hermetic` has no in-repo packages and prints PASS |
| **destructive-last** | Migrate, rewire, prove, *then* delete — in the same slice (spine AD-13) |
| **ags-apps** | The monorepo of seven AGS apps (`bar`, `hypr-pano`, `notifications`, `capture-tool`, `wallpaper-selector`, `icme`, `btop-theme-studio`) plus the capture-tool Python backend, consumed as one pinned unit |
| **contract** | Either the **event contract** (`org.dotfiles.Events`, runtime ↔ AGS) or the **CLI invocation contract** (argv/env/artifacts/exit codes, runtime ↔ CLIs); both live in the `contracts` repo and share one tag |
| **mirror** | A hand-maintained copy of a pin inside a role (`cli_tools`, `verify`, `assets`, `settings`) that Ansible cannot read from the manifest; parity is gate-locked |
