# Dotfiles System — Phase 1: Provisioning Plan

> **Epic 4 amendment (2026-09-04, single source of truth):** this plan
> describes Phase 1 as-built, including the `default_palette` / `icons`
> generation roles and the `<install>/generated/` tree. Those are REMOVED
> by Epic 4 (`_bmad-output/planning-artifacts/epics-runtime-single-source.md`):
> provisioning deploys inputs only, the runtime (`wallpaper set` /
> first-run seed) is the single producer of palette/effects/icons, and
> `<install>/generated/` no longer exists. `generated/` references below
> are historical — do not reintroduce them.

**Status:** Approved — locked decisions applied (2026-08-03). Ready to drive a BMad flow.
**Companion docs:** [`99-dotfiles-hexagonal-architecture.md`](./99-dotfiles-hexagonal-architecture.md) · canonical contract: `_bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md` + `chaining-spine.md`
**Scope:** Phase 1 of the recommended development phases (§27 of the architecture doc). Provisioning only — no runtime reconciliation.

---

## 1. Objective

Establish the **operational environment** so the future runtime reconciliation layer (Phase 2+) can legitimately assume its preconditions exist (§12). This is "Machine State Reconciliation" (Domain 1), explicitly *not* "Desktop Runtime State Reconciliation" (Domain 2, §4).

The project is a **Desktop State Reconciliation Engine** (§3). Provisioning is the bottom layer that makes the machine *capable*; it does not reconcile the desktop.

---

## 2. Current Repository State (verified)

### Already built (compute providers + shared libs, §9/§21)

| Path | Contents |
|---|---|
| `src/cli-tools/color-scheme-generator/` | `csg` CLI, full uv package (pyproject, src, tests, docs) |
| `src/cli-tools/wallpaper-effects-generator/` | `weg` CLI, full uv package |
| `src/cli-tools/icon-templates-renderer/` | icon-renderer CLI, full uv package |
| `src/shared/cli-output/` | Hexagonal renderer (ports/adapters, json/plain/rich output) |
| `src/shared/config-assembler-engine/` | Hexagonal config resolution engine (strategies, env reader, override rules, pydantic coercion) |
| `src/shared/oci-runtime/` | Docker/podman execution layer (used by CSG/WEG `--runtime container`) |
| `dotfiles/assets/wallpapers/` | Wallpaper assets |
| `dotfiles/assets/icon-templates/` | SVG icon templates |
| `dotfiles/config/icon-template-color-scheme-mappings/` | Per-app icon color-mapping YAMLs (battery, network, power-menu, wallpaper-selector, wlogout, icons, etc.) |
| `dotfiles/config/{nvim,starship,wlogout,zsh}/` | Existing static configs |
| `scripts/orchestrate-v5.sh` | Existing openspec change-wave orchestrator |
| `openspec/` | Specs + changes (csg-*, weg-* config-resolution-chain & settings-schema specs exist) |

### Missing / not started

- `src/core/` — **empty** (runtime reconciliation domain, Phase 2)
- `src/infrastructure/` — **does not exist** (runtime adapters, Phase 2)
- `src/provisioning/` — **does not exist** (this phase)
- Root `dotfiles` CLI — does not exist (Phase 2)
- `dotfiles/config/{hypr,hyprpaper,waybar}/` — missing compositor config dirs
- `dotfiles/provisioning/` — declarative manifests, does not exist

---

## 3. Locked Decisions

| Decision | Choice | Notes |
|---|---|---|
| **Phase order** | Provisioning first (Phase 1), runtime core second | Per §27; runtime legitimately assumes env exists |
| **Provisioning backend** | **Ansible** | Matches `src/provisioning/ansible/` in §9 repo tree |
| **Distro support** | Multi-distro: Arch (pacman + AUR) + Debian family (apt) | Distro branching is Ansible-native (`ansible_facts` + `group_vars/{arch,debian-family}.yml`); Python side stays distro-agnostic |
| **CLI tool install** | Ansible task using `uv tool install` against repo paths | Lives inside the `cli_tools` role — not a separate Python adapter |
| **Bootstrap** | `scripts/bootstrap.sh` pre-seeds Python+uv, then runs `uv run --directory ./src/provisioning dotfiles-provision bootstrap` | Solves the chicken-and-egg of running a Python provisioner; the provisioner runs from its source dir via `uv run` — no pre-install step |
| **Ansible install** | `ansible-core` is a runtime dep of `src/provisioning` (`pyproject.toml`) | Resolved by `uv` from the lockfile; no system-wide install. External collections (`community.general`, `ansible.posix`, `kewlfft.aur`) declared in `ansible/requirements.yml` and resolved via `ansible-galaxy` at bootstrap start |
| **AUR helper (Arch)** | `packages` role self-bootstraps `yay`: pacman installs `base-devel`+`git`, a guarded task builds `yay-bin` via `makepkg -si` (skips if `yay` present), then `kewlfft.aur.aur` drives all AUR installs | Distro logic stays in `vars/arch.yml` — never in `bootstrap.sh` or Python |
| **Install dir** | `$XDG_DATA_HOME/dotfiles/` (default `~/.local/share/dotfiles/`) | Provisioning resolves it at plan time and bakes absolute paths into rendered settings files |
| **Settings authoring** | Provisioning-authored Jinja templates rendered by Ansible's `template` module | The `csg/weg dump-*` commands are NOT used by provisioning; they remain user-facing conveniences. The default palette IS generated at apply time by invoking `csg generate -f conf` (see §5/§6) |
| **Persistence** | **None in Phase 1** | Ansible is the state authority (idempotent playbooks); `verify` re-derives state on demand. A `provisioning-state.json` receipt is deferred to Phase 2+ only if a drift-history need surfaces |
| **§11 boundary** | `src/provisioning` is its own uv package | Imports `cli-output` only; never `core`/`infrastructure`/CLI-tool packages; knows machine state only. Enforced mechanically by `tests/architecture/test_layering.py` (in-package hexagon + cross-package forbidden set) |

---

## 4. Tool Settings Facts (verified — what provisioning must generate)

All three tools resolve a `settings.toml` through the shared `config-assembler-engine`. Discovery precedence everywhere is: **CLI `--config` > `ENV` path var > directory traversal > XDG `$XDG_CONFIG_HOME/<subdir>/` > bundled package default**. Override precedence is **CLI > ENV > settings file > discovery/default**. Env prefix naming: `<PREFIX>__SECTION__KEY` (e.g. `ICON_RENDERER__OUTPUT__OUTPUT_DIR`).

### CSG — `~/.config/color-scheme-generator/settings.toml`

- Env prefix: `COLORSCHEME`; XDG subdir `color-scheme-generator`; config file env: `COLORSCHEME_CONFIG_FILE_PATH`.
- **Path settings provisioning must set:**
  - `[output] directory` — where palettes/formats are written. Default `/tmp/color-scheme`.
- Other relevant settings: `output.default_formats`, `output.overwrite`, `output.verbosity`, `generation.backend`, `runtime.mode`, `container.*`.
- **Templates dir is NOT a settings field** — separate resolver chain: CLI `--templates-dir` → env `COLORSCHEME_TEMPLATES_TEMPLATES_DIR` → directory traversal `templates/` → XDG `~/.config/color-scheme-generator/templates/` → bundled `<pkg>/defaults/templates`. **Locked (config-in-spine 2026-08-16): provisioning deploys the bundled templates to `<install>/config/color-scheme-generator/templates/`; Phase 2 runtime invokes CSG with `--templates-dir <install>/config/color-scheme-generator/templates/`** (see §9). The XDG stop is `color-scheme-generator/templates/` — unified with the settings subdir (one config dir per tool; the earlier `~/.config/color-scheme/templates` split was a flaw, resolved 2026-08-15).
- **Hyprland format exists** — CSG now ships a 9th format `conf` (`colors.conf.j2` → `colors.conf`), emitted via `-f conf` (verified working). Provisioning's `default_palette` role uses it to emit the Hyprland `colors.conf` directly — no compositor-format template needed in provisioning. The rendered `default_formats = []` means interactive `csg generate` emits ALL catalog formats; the chain passes explicit `-f conf -f gtk.css -f yaml`.
- Wallpaper input is always a positional CLI arg (no setting).
- Dump commands: `csg dump-config` (bundled default settings.toml, stdout or `--output`), `csg dump-templates` (copies bundled `.j2` templates to a dir, `--output`, `--overwrite`).

### WEG — `~/.config/weg/settings.toml`

- Env prefix: `WALLPAPER`; XDG subdir `weg`; config file env: `WALLPAPER_CONFIG_FILE_PATH`.
- **Path settings provisioning must set:**
  - `[output] directory` — where effect images are written. Default `/tmp/wallpaper-effects`.
  - `[processing] temp_dir` — temp dir for intermediate work. Default `/tmp/.wallpaper-effects-tmp`. No CLI flag — only reachable via settings/env.
- Other relevant settings: `version`, `execution.*`, `output.verbosity`, `backend.binary`, `runtime.mode`, `container.*`.
- **Second chain:** `effects.yaml` at `~/.config/weg/effects.yaml` (env `WALLPAPER_EFFECTS_CONFIG_FILE_PATH`, CLI `--effects`). Defines the effect catalog — no paths to override. **Locked (config-in-spine 2026-08-16): provisioning emits a custom effects catalog via `weg dump-effects --output <install>/config/weg/effects.yaml` and the WEG effects chain points at it** (`WALLPAPER_EFFECTS_CONFIG_FILE_PATH` or `--effects`); the file lives in the spine under the tool's config dir, and the `~/.config/weg` symlink makes the XDG stop resolve there too.
- Wallpaper input is a positional CLI arg.
- Dump commands: `weg dump-config` (bundled default settings.toml), `weg dump-effects` (bundled default effects.yaml). Both stdout or `--output`.

### ITR — `~/.config/itr/settings.toml`

- Env prefix: `ICON_RENDERER`; XDG subdir `itr`; config file env: `ICON_RENDERER_CONFIG_FILE_PATH`.
- **Resolver is now ACTIVE** (all commands call `config_resolver.resolve()` via `cli/_helpers.py:resolve_roots`).
- **Path settings provisioning must set:**
  - `[output] output_dir` — where rendered SVGs are written. Default `/tmp/icon-templates-renderer`. Required; empty rejected.
  - `[templates] dir` — SVG templates root. Default `None` → discovery (then XDG `~/.config/itr/templates`).
  - `[color_scheme] path` — color-scheme file. Default `None` → discovery (then XDG `~/.config/itr/colors.yaml`).
- Other: `output.verbosity`.
- CLI flags: `--config`, `--template-dir`, `--color-scheme`, `--output-dir`, `--icon`, `--unsafe`. All path flags feed the override rules as `cli_overrides`.
- **ITR has NO dump command** — provisioning writes its settings.toml directly (small, 4 keys).
- The color-mapping YAMLs (per-app, in `dotfiles/config/icon-template-color-scheme-mappings/`) declare per-group `template_dir`/`output_dir`/`color_scheme`/`variants`; a top-level `templates_root`/`outputs_root`/`color_scheme` is also supported. Current repo YAMLs use `template_dir: .` / `output_dir: .` (relative to the YAML dir) and `color_scheme: ~` (null) — so rendering requires the settings `color_scheme.path` (or a CLI flag) to supply the palette path.

---

## 5. The Chaining Spine (the install dir)

Provisioning creates `$XDG_DATA_HOME/dotfiles/` with this subtree. It is the data-flow glue that chains the three compute providers:

```
$XDG_DATA_HOME/dotfiles/
├── config/                              # config-in-spine: ALL managed configs (symlinked into ~/.config)
│   ├── hypr/  waybar/  hyprpaper/       # compositor skeletons + palette fragments
│   ├── nvim/  starship/  wlogout/  zsh/ # config copies (real dirs in the spine)
│   ├── color-scheme-generator/          # settings.toml + templates/ (CSG tool config)
│   ├── weg/                             # settings.toml + effects.yaml (WEG tool config)
│   └── itr/                             # settings.toml (ITR tool config)
├── wallpapers/                          # unpacked from dotfiles/assets/wallpapers/wallpapers.tar.gz (default.png included)
├── icon-templates/                      # deployed from dotfiles/assets/icon-templates/
├── icon-mappings/*.yaml                # deployed from dotfiles/config/icon-template-color-scheme-mappings/
└── generated/
    ├── palettes/                        # CSG writes colors.yaml + colors.conf + formats here ([output] directory)
    ├── effects/                         # WEG writes effect images here ([output] directory)
    ├── icons/                           # ITR writes rendered SVGs here ([output] output_dir)
    └── .weg-tmp/                        # WEG temp dir ([processing] temp_dir)
```

The tools chain through it:
- CSG: reads wallpaper (CLI arg) → writes palette to `<install>/generated/palettes/`; reads templates from `<install>/config/color-scheme-generator/templates/` via `--templates-dir` (the config-links symlink also makes `~/.config/color-scheme-generator/templates` resolve there)
- WEG: reads wallpaper (CLI arg) → writes effects to `<install>/generated/effects/`, temps to `<install>/generated/.weg-tmp/`; reads its effects catalog from `<install>/config/weg/effects.yaml`
- ITR: reads SVG templates from `<install>/icon-templates/` → reads color scheme from `<install>/generated/palettes/colors.yaml` (**chains to CSG output**) → writes rendered SVGs to `<install>/generated/icons/` (invoked by the icons role at apply time)

**Default palette (sync invariant):** the `default_palette` role invokes `csg generate <install>/wallpapers/default.png` (`-f conf` + standard formats) at apply time, writing to `<install>/generated/palettes/`. Replacing `wallpapers.tar.gz` in the repo → next `apply` regenerates the palette from the new default. The `overwrite=true` semantic is scoped to that one task via `environment: COLORSCHEME__OUTPUT__OVERWRITE: "true"` — it is **never** written into the rendered `<install>/config/color-scheme-generator/settings.toml` (which keeps `overwrite = false`).

Phase 2's reconciler invokes the tools with `--config <provisioned-settings>` and they read/write against this spine without per-invocation path flags.

---

## 6. Repository Layout To Be Created

```
src/provisioning/
├── pyproject.toml                      # uv package; entry: dotfiles-provision
├── uv.lock
├── README.md
├── ansible/
│   ├── inventory/localhost.yaml         # runs against the local host
│   ├── requirements.yml                 # external collections: community.general, ansible.posix, kewlfft.aur
│   ├── group_vars/{all,arch,debian-family}.yml
│   ├── playbooks/
│   │   ├── bootstrap.yaml               # aggregate run
│   │   ├── packages.yaml
│   │   ├── cli-tools.yaml
│   │   ├── filesystem.yaml
│   │   ├── assets.yaml
│   │   ├── default-palette.yaml
│   │   ├── compositor-configs.yaml
│   │   ├── config-copies.yaml
│   │   ├── settings.yaml                # renders the three settings.toml templates
│   │   └── verify.yaml                  # asserts §12 preconditions
│   ├── roles/
│   │   ├── packages/     (tasks/main.yml, vars/{main,arch,debian}.yml — Arch self-bootstraps yay; kewlfft.aur for AUR)
│   │   ├── cli_tools/   (tasks/main.yml — `uv tool install` csg/weg/itr)
│   │   ├── assets/      (tasks/main.yml — unpacks wallpapers.tar.gz + deploys icon-templates + icon-mappings + csg-templates)
│   │   ├── default_palette/ (tasks/main.yml — `csg generate <install>/wallpapers/default.png -f conf`; env-scoped overwrite)
│   │   ├── compositor_configs/ (tasks/main.yml — deploys Hyprland/Waybar/Hyprpaper skeletons + color fragments)
│   │   ├── filesystem/ (tasks/main.yml)
│   │   ├── config_copies/ (tasks/main.yml — copies repo dotfiles/config/* → <install>/config/)
│   │   ├── settings/   (tasks/main.yml, templates/{csg,weg,itr}-settings.toml.j2, vars/main.yml)
│   │   ├── config_links/ (tasks/main.yml — symlinks ~/.config/<name> → <install>/config/<name>; backup guard)
│   │   ├── icons/      (tasks/main.yml — `itr render` resolved SVGs into generated/icons/)
│   │   └── verify/     (tasks/main.yml)
│   └── ansible.cfg
├── src/provisioning/
│   ├── domain/
│   │   ├── models.py                    # MachineState, ProvisionManifest, ProvisionResult, Spec dataclasses
│   │   └── enums.py                     # Distro, Capability, CapabilityKind, AssetKind
│   ├── ports/
│   │   ├── provision_executor.py        # IProvisionExecutor (abstracts ansible-playbook; check: bool)
│   │   ├── manifest_reader.py           # IManifestReader
│   │   └── fact_reader.py               # IFactReader.os_family() -> str (thin: selects group_vars, never inspects packages)
│   ├── application/
│   │   └── use_cases.py                 # ProvisionMachineUseCase (plan=check:True / apply=check:False), VerifyCapabilityUseCase, BootstrapUseCase
│   ├── adapters/
│   │   ├── ansible_executor.py          # shells to `ansible-playbook` (-i, --tags, --check, --extra-vars); surfaces per-task changed/ok
│   │   ├── yaml_manifest_reader.py      # reads dotfiles/provisioning/*.yaml
│   │   └── ansible_fact_reader.py       # parses `ansible -m setup` for ansible_os_family
│   └── cli/
│       ├── main.py                      # Typer app: dotfiles-provision {plan,apply,verify,bootstrap}
│       └── options.py
└── tests/
    ├── unit/                            # ports, use cases, manifest reader, executor
    ├── architecture/test_layering.py    # mirrors oci-runtime hexagon + Rule 5 cross-package §11 forbidden set
    └── integration/test_ansible_dryrun.py  # runs every playbook with --check

dotfiles/provisioning/                   # declarative desired-machine-state manifests
├── packages.yaml                        # desired packages per package manager
├── assets.yaml                          # wallpapers + icon templates + icon mappings to deploy
├── filesystem.yaml                      # XDG + install dir subtree layout
├── config-copies.yaml                    # copies repo dotfiles/config/* → <install>/config/* (symlinked into ~/.config by config_links)
└── cli-tools.yaml                       # csg/weg/itr install specs (uv tool install targets)

dotfiles/config/
├── hypr/                                # NEW — static skeleton hyprland.conf with `source = ~/.config/hypr/colors.conf`
├── hyprpaper/                           # NEW — flat static hyprpaper.conf pointing at <install>/wallpapers/default.png
├── waybar/                              # NEW — static config + style.css starting with `@import "colors.css";`
└── ... (existing dirs unchanged)

Compositor color-fragment contract:
- Hyprland `colors.conf` — emitted by the `default_palette` role via `csg generate -f conf` into `<install>/generated/palettes/colors.conf`, then copied to `~/.config/hypr/colors.conf`. Phase 2 overwrites it on palette change; the skeleton never changes.
- Waybar `colors.css` — comes from CSG's `gtk.css` format (`<install>/generated/palettes/colors.gtk.css`), copied to `~/.config/waybar/colors.css`. Phase 2 overwrites it on palette change. (Review finding 2026-08-12: the `css` format emits browser CSS custom properties that GTK/Waybar cannot read; `gtk.css` emits `@define-color`, which the Waybar skeleton consumes.)
- Hyprpaper — flat static; Phase 2 rewrites only when the wallpaper actually changes.

scripts/
├── orchestrate-v5.sh                    # EXISTING
└── bootstrap.sh                         # NEW
```

---

## 7. Reconciliation Shape (machine state, not desktop state)

```
dotfiles-provision plan      → load desired manifests (dotfiles/provisioning/*.yaml)
                                + read ansible_os_family (IFactReader) to select group_vars/{arch,debian-family}.yml
                                → run ansible-playbook bootstrap.yaml --check (Ansible owns the diff)
                                → render per-task changed/ok via cli-output
dotfiles-provision apply     → IProvisionExecutor.run(playbook, check=False)
                                → idempotent (Ansible is the state authority; no state file persisted)
dotfiles-provision verify    → runs verify.yaml → asserts §12 preconditions
dotfiles-provision bootstrap → run bootstrap.yaml end-to-end
```

Matches §17's desired → actual → diff → plan → execute loop, applied to the machine instead of the desktop. The diff engine is Ansible's native `--check` mode — the Python side never branches on distro for package inspection; it only uses `ansible_os_family` to choose which `group_vars` apply. There is no `persist` step in Phase 1 (see §3).

---

## 8. Done Criteria (refined)

Phase 1 is finished when `dotfiles-provision verify` and `dotfiles-provision bootstrap --check` are clean, asserting each of:

1. **Install dir established** — `$XDG_DATA_HOME/dotfiles/` exists with the full subtree (`wallpapers/`, `icon-templates/`, `icon-mappings/`, `config/` (+ tool subdirs), `generated/{palettes,effects,icons,.weg-tmp}/`).
2. **System binaries installed** — Hyprland, Hyprpaper, Waybar, fonts on PATH.
3. **Dotfiles CLI tools installed** — `csg`, `weg`, icon-renderer on PATH (via `uv tool install`).
4. **Assets deployed** — `wallpapers.tar.gz` unpacked → `<install>/wallpapers/` (incl. `default.png`); SVG **icon templates** in `<install>/icon-templates/`; icon **color mappings** (the YAMLs) in `<install>/icon-mappings/`; CSG bundled templates in `<install>/config/color-scheme-generator/templates/`; `weg-effects.yaml` emitted via `weg dump-effects --output` to `<install>/config/weg/effects.yaml`.
5. **Per-tool settings files render and parse** (in the config-in-spine home, exposed via `~/.config/<tool>` symlinks):
   - `~/.config/color-scheme-generator/settings.toml` parses; `output.directory` → `<install>/generated/palettes/`
   - `~/.config/weg/settings.toml` parses; `output.directory` → `<install>/generated/effects/`; `processing.temp_dir` → `<install>/generated/.weg-tmp/`
   - `~/.config/itr/settings.toml` parses; `output.output_dir` → `<install>/generated/icons/`; `templates.dir` → `<install>/icon-templates/`; `color_scheme.path` → `<install>/generated/palettes/colors.yaml`
   - Verified by invoking `csg info --config <path>`, `weg info --config <path>`, `itr list <install>/icon-mappings/icons.yaml --config <path>` — all exit 0. (Avoid `defaults.yaml` as the `itr list` target — it is a shared-defaults file without a `variants` field and is not listable.)
6. **Default palette generated** — `<install>/generated/palettes/colors.conf` + `colors.yaml` exist and parse; `$accent` equals `$color1` in the Hyprland fragment; the rendered `<install>/config/color-scheme-generator/settings.toml` keeps `overwrite = false`.
7. **Compositor configs placed** — skeletons + palette fragments written into `<install>/config/{hypr,hyprpaper,waybar}/` (exposed via the `~/.config/{hypr,hyprpaper,waybar}` symlinks); `hypr/colors.conf` and `waybar/colors.css` present.
8. **Filesystem structure exists** — XDG config/state/cache dirs, hypr/hyprpaper/waybar dirs, install dir subtree.
9. **Config copies present as spine symlinks** — every entry in `dotfiles/provisioning/config-copies.yaml` is a symlink at `~/.config/<target>` → `<install>/config/<target>` (5-layer check: islnk, exact target in the spine, resolves, content-through-link, functional parse). Nothing in the repo is referenced at runtime, so the machine keeps working after the repo is deleted.
10. **Icons rendered** — `<install>/generated/icons/` holds the resolved SVGs (the icons role invokes `itr render`); at least one known variant present (e.g. `battery-0.svg`).
11. **§12 capability preconditions** — the four runtime assumptions (binaries installed, assets placed, filesystem structure exists, settings files parseable) are assertable via `VerifyCapabilityUseCase` without reaching into provisioning internals.

---

## 9. Resolved Sub-Decision

**CSG templates dir placement** (templates dir is *not* a settings.toml field):

- **Option B (LOCKED, config-in-spine 2026-08-16):** deploy CSG's bundled templates to `<install>/config/color-scheme-generator/templates/`; Phase 2 runtime passes `--templates-dir <install>/config/color-scheme-generator/templates/` per invocation.

Chosen over Option A (XDG `~/.config/color-scheme/templates/`) to preserve spine containment — the install dir is the single place the tools read from. Consistent with the WEG effects catalog also living in the spine (`<install>/config/weg/effects.yaml`) and with the config-in-spine pattern (docs/02-config-in-spine-pattern.md): ALL managed configs live under `<install>/config/` and `~/.config` is an alias layer of symlinks. Matches the SPEC in `_bmad-output/specs/spec-dotfiles-provisioning-phase1/`.

---

## 10. What You Get After Implementing This Phase

- **Reproduce any machine from scratch:** `git clone <repo> && ./scripts/bootstrap.sh` → Python+uv bootstrapped → `dotfiles-provision` installed → drives Ansible to install Hyprland/Waybar/Hyprpaper/fonts, install `csg`/`weg`/icon-renderer, deploy assets, create the filesystem, copy configs, render the three settings files, verify everything.
- **Machine state as data:** `dotfiles-provision plan` shows desired-vs-actual diff before any mutation (Ansible `--check`); `apply` is idempotent and re-runnable (Ansible is the state authority — no state file).
- **A verified, tool-ready install layout:** the chaining spine (wallpapers / icon-templates / icon-mappings / config (managed configs) / generated palettes / effects / icons / temp) with all three tools' settings files pointing at it — the first `csg generate <img>` or `itr render --config ...` already knows where to read/write, with no path flags, no `/tmp` leaks, and ITR's color scheme chaining straight to CSG's palette output.
- **A hard verify gate:** `dotfiles-provision verify` green is the contract Phase 2 may assume; also a drift regression check.
- **Multi-distro portability:** same playbooks on Arch (pacman + AUR) or Debian-family (apt); distro differences isolated to `group_vars`.

**What you do NOT get yet:** the runtime core (`src/core/`), the root `dotfiles` CLI, content hashing/invalidation, and palette→config→reload desktop convergence. Those are Phase 2+. Phase 1 only makes the machine capable; it does not reconcile the desktop (§11).

---

## 11. Implementation Order

1. Scaffold `src/provisioning/pyproject.toml` (uv package; deps: `typer`, `pydantic`, `cli-output`, `ansible-core`; dev: `pytest`, `ruff`, `mypy`; `uv.sources` for `cli-output`). Mirror `src/shared/cli-output/pyproject.toml`.
2. `domain/` + `ports/` (pure, no Ansible, no I/O) + `tests/unit/` + `tests/architecture/test_layering.py` to lock the §11 boundary from day one — in-package hexagon (domain ← ports ← adapters ← application ← cli; domain stdlib allowlist; banned `subprocess`/`os`/`shutil` in domain; ports must be ABCs; no Path FS calls in domain) plus Rule 5: cross-package forbidden set (`core`, `infrastructure`, `color_scheme_generator`, `wallpaper_effects_generator`, `icon_templates_renderer`, `config_assembler_engine`, `oci_runtime`); only `provisioning` + `cli_output` allowed.
3. `adapters/{yaml_manifest_reader,ansible_executor,ansible_fact_reader}.py` + unit tests with fakes.
4. `application/use_cases.py` wiring ports → use cases (`ProvisionMachineUseCase` with `check` flag, `VerifyCapabilityUseCase`, `BootstrapUseCase`); unit tests with fakes.
5. `cli/main.py` (Typer) — `plan`, `apply`, `verify`, `bootstrap`; uses `cli-output` for rendering.
6. `dotfiles/provisioning/*.yaml` manifests (populated from the actual package set + existing assets).
7. Ansible content: `inventory`, `requirements.yml`, `group_vars/{all,arch,debian-family}.yml`, then roles in install order — `packages` → `cli_tools` → `filesystem` → `assets` → `default_palette` → `compositor_configs` → `config_copies` → `settings` → `config_links` → `icons` → `verify`; one playbook per role plus the aggregate `bootstrap.yaml`. (`default_palette` needs `csg` installed by `cli_tools` and wallpapers unpacked by `assets`; `compositor_configs` needs the palette generated by `default_palette`; `config_links` symlinks the managed configs into `~/.config` (config-in-spine); `icons` renders the resolved SVGs via `itr render`; `verify` re-checks all of it.)
8. The three Jinja settings templates under `roles/settings/templates/`.
9. Add `dotfiles/config/{hypr,hyprpaper,waybar}/`: Hyprland skeleton (`source = ~/.config/hypr/colors.conf`), Waybar skeleton (`@import "colors.css";`), flat static Hyprpaper (points at `<install>/wallpapers/default.png`).
10. `scripts/bootstrap.sh` (pre-seed Python+uv, then `uv run --directory ./src/provisioning dotfiles-provision bootstrap`).
11. Integration tests: `--check` runs of every playbook; a verify test that all done-criteria hold after a dry-run bootstrap; a settings-file-parity test invoking each tool with `--config <rendered>` and asserting it parses without error; a default-palette test asserting `csg generate -f conf` output matches the Hyprland syntax contract.

**Prerequisite (done):** CSG `conf` (Hyprland) output format — implemented and verified end-to-end (`openspec/changes/2026-08-03-csg-hyprland-format/`).

---

## 12. Deferred to Phase 2 (explicitly out of scope)

- `src/core/` (runtime reconciliation domain) + `src/infrastructure/` (adapters wrapping csg/weg/itr via `--config <provisioned-path>`)
- Root `dotfiles` CLI (architecture doc §28 Task Group F)
- JSON snapshot persistence *of desktop state* (separate from provisioning's state store)
- Content hashing / invalidation / derived-artifact tracking
- Writing derived colors into the Hyprland/Hyprpaper/Waybar templates provisioning just placed
- An `itr dump-config` command for parity with csg/weg (only if Phase 2 needs it; provisioning already writes ITR's settings.toml directly)
