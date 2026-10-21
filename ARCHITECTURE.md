# ARCHITECTURE.md — `dotfiles-v3`

## 1. Status

| | |
|---|---|
| Written | 2026-10-21 |
| Base commit | `e94fe8dc` (parent of the commit that adds this file; `git log -1`) |
| Scope | the host repo only — it consumes, it does not own, the seven pinned repos |
| Kind | index over sources of truth, not a source of truth itself |

This file is the entry point, not the authority. Every section points at the file or
command that *is* authoritative. When this document and a cited file disagree, the
cited file wins and this document is the bug.

**How to keep this true**

```bash
make gates-ci          # the six executable gates (section 9)
make deploy-coverage   # provisioning shape only; prints the pinned manifests it read
openspec validate --all # 104 passed / 27 failed on 2026-10-21 — pre-existing, see section 9
make contract-pin-check # needs a sibling `contracts` checkout; skips (exit 0) without one
```

Anything else is prose drift. The two places that change most often are
`dotfiles/provisioning/cli-tools.yaml` (pins) and
`src/provisioning/ansible/roles/verify/vars/main.yml` (what a provisioned host must
prove); update those first, then this index.

## 2. What this repo is now

**One sentence: `dotfiles-v3` is an orchestration spine that provisions a Linux
desktop from pinned external artifacts, plus the one program (`dotfiles-runtime`)
that drives that desktop at runtime.**

It authors essentially nothing another repo also authors. The only in-repo Python is
`src/runtime/` and `src/provisioning/` (`Makefile:101-130`); `make deploy-coverage` asserts
exactly one local manifest source, `dotfiles-runtime -> src/runtime`
(`scripts/deploy-coverage.py:1771-1819`).

| The repo owns | The repo consumes |
|---|---|
| Ansible playbooks, roles, manifests (`src/provisioning/ansible/`, `dotfiles/provisioning/*.yaml`) | `cli-output` + `cli-invocation-contract` as git-tag pins (`src/runtime`; `cli-output` also in `src/provisioning`); `config-assembler-engine` + `oci-runtime` as git-tag pins inside the CLI repos; the three CLIs as `{name,repo,tag}` manifest entries (section 4) |
| `dotfiles-runtime` — CLI, daemon, clipboard watcher, cache/state (`src/runtime/`) | `ags-apps` monorepo as one pinned unit (seven AGS apps + the capture-tool backend) |
| Inputs: configs, assets, icon mappings, Hyprland Lua (`dotfiles/config/`, `dotfiles/assets/`) | `ags-platform` as one pinned unit (bare specifier, `node_modules` shortcut) |
| Gates and their scripts (`Makefile`, `scripts/*.py`) | System packages: pacman/apt + AUR (`roles/packages`) |
| Docs, planning, and the historical record (`docs/`, `_bmad-output/`, `openspec/`) | A user-provided container engine (podman or docker) — **never installed by a role** (`bootstrap.sh:45-57`) |

Consequences that surprise newcomers:

- **No GUI source lives here.** The bar, clipboard overlay, notifications, capture
  tool, wallpaper selector, ICME and btop studio all deploy *whole* from the
  `ags-apps` unit (`src/provisioning/ansible/roles/ags_apps/vars/main.yml:1-90`).
- **No CLI source lives here.** `csg`/`weg`/`itr` are `{name, repo, tag}` manifest
  entries; `src/cli-tools/` and `src/shared/` are asserted absent
  (`scripts/deploy-coverage.py:1752-1768`).
- **The contract is not authored here either.** `contracts/` in this repo is a
  vendored copy used by conformance tests; the pin is
  `src/runtime/src/runtime/adapters/CONTRACT_PIN` (`dbdc5b8`).

## 3. Topology

```
                    system packages (pacman/apt/AUR)
                                |
   +---------------------+      |      +-----------------------+
   | dotfiles-v3 (host)  |<-----+      | ags-platform v0.2.0   |
   | provisioning        |             | ports + adapters      |
   | src/runtime         |-- bare spec -> node_modules shortcut (unit)
   | manifests, gates    |             +-----------+-----------+
   +----------+----------+                         ^ imports
              |                                    |
              | {name,repo,tag} / git tags  +------+-------------+
              v                             | ags-apps v0.4.0    |
   +----------+---------------------+       | bar, hypr-pano,    |
   | contracts v0.1.0               |       | notifications,     |
   |  event contract (Events1/2)    |       | capture-tool,      |
   |  cli-invocation-contract+kit   |       | wallpaper-selector,|
   +--+--------+--------+--------+--+       | icme, btop-studio  |
      |        |        |        |          +--------------------+
      v        v        v        |           live links: <install>/config/ags*
   +------+ +------+ +------+    |
   | itr  | | weg  | | csg  |    |
   | v0.1 | | v0.1 | | v0.1 |    |
   +--+---+ +--+---+ +--+---+    |
      +--------+--------+--------+
               v
   cli-output v0.1.0 · config-assembler-engine v0.1.0 · oci-runtime v0.5.0
```

**Direction rules (enforced by test, not by convention)**

| Rule | Where it is enforced |
|---|---|
| Libraries depend on no sibling repo; CLIs depend on libs + `contracts` only; no CLI imports/invokes another CLI | `_bmad-output/.../ARCHITECTURE-SPINE.md` AD-1; each repo's `tests/architecture/test_layering.py` |
| `dotfiles-v3` consumes CLIs/libs as pinned artifacts, never as a path, editable install, submodule or workspace | `scripts/deploy-coverage.py:1360-1513` (no in-tree package, no `path` pin) |
| The runtime never imports a CLI package — it spawns the console | `src/runtime/tests/architecture/test_layering.py`; adapters use `subprocess.run` (`csg_adapter.py:304`, `weg_adapter.py:342`, `itr_adapter.py:423`) |
| Runtime never imports provisioning *code* (it reads provisioning output) | `_FORBIDDEN_CROSS_PACKAGE = {provisioning, core, infrastructure}` (`src/runtime/tests/architecture/test_layering.py:104-111`) |
| AGS apps import the platform, never each other | `docs/101-ags-platform-architecture.md` §3.1; `docs/HANDOFF-ags-platform.md` §5.1 (0 cross-app imports measured) |

## 4. The seven repos

One contract repo + three libraries + three CLIs. All public, fetched anonymously over HTTPS by
tag (`openspec/changes/archive/2026-10-21-cli-tools-repos/POST-MIGRATION.md` §1). Tags are
annotated, monotonic, never moved; a fix is a new tag.

| Repo | Provides | First tag + semantics | Consumed how | Gates it owns |
|---|---|---|---|---|
| `contracts` | `event-contract.{json,xml,md}` + `generated/` bindings **and** `invocation-contract.json` + `cli_invocation_contract` (+ `testkit`) | `v0.1.0` — first tag ever; dual role, see below | Git tag in `src/runtime/pyproject.toml:27`; event contract vendored into `contracts/` and `src/runtime/.../contract_generated.py` | `validate`, `generate`, `check-symmetry` / `contracts-drift`, `test`, `build` (`contracts/Makefile`) |
| `cli-output` | `cli_output` package — rendering/views only | `v0.1.0` (version continuity with in-tree 0.1.0) | Git tag in `src/runtime/pyproject.toml:26`, `src/provisioning/pyproject.toml:25`, and each CLI | `test lint hermetic lock-check docs-check` |
| `config-assembler-engine` | `config_assembler_engine` — resolution strategies, config assembly | `v0.1.0` | Git tag **only inside the three CLI repos** (not a dotfiles dependency) | same five |
| `oci-runtime` | `oci_runtime` — engine abstraction, build/run/exec, `resolve_build_context` | `v0.5.0` (imported code was 0.4.0; forward-only) | Git tag in `csg` and `weg` only | same five |
| `icon-templates-renderer` | console `itr` (pure Python, no container mode) | `v0.1.0` | `{name, repo, tag}` manifest + role mirror + verify pin | same five |
| `wallpaper-effects-generator` | console `weg` + `Dockerfile.imagemagick` + `image` verb | `v0.1.0` | same | same five + `image` |
| `color-scheme-generator` | console `csg` + four Dockerfiles + template catalog + `image` verb | `v0.1.0` | same | same five + `image` |

**Two consumption shapes only** (`POST-MIGRATION.md` §2):

```toml
# 1. libraries + contract — each consumer's pyproject.toml
[tool.uv.sources]
cli-output = { git = "https://github.com/RandomGenericUsername/cli-output", tag = "v0.1.0" }
# 2. CLIs — dotfiles/provisioning/cli-tools.yaml
#    entries: [{name: csg, repo: …/color-scheme-generator, tag: v0.1.0}, …]
```

**`contracts` carries two contracts, and that is deliberate** (spine AD-4, OPEN-7
resolution): the **event contract** (`org.dotfiles.Events`, versioned `Events1`/`Events2`)
for the runtime ↔ AGS seam, and the **CLI invocation contract** (argv, env keys,
artifact names, exit codes, default timeout) for the runtime ↔ `csg`/`weg`/`itr` seam.
They share one repo and one tag because both are cross-repo seams with the same
charter. The **same-tag rule** follows: one `contracts` tag is pinned by the runtime
and by all three CLIs, and `verify` asserts each CLI's `--version` contract token
equals `0.1.0` (`roles/verify/vars/main.yml:221-272`).

## 5. Repo map of `dotfiles-v3`

| Path | What it is | Status |
|---|---|---|
| `src/runtime/` | `dotfiles-runtime`: hexagon (domain/ports/adapters/application/cli), daemon, clipboard watcher, cache/state | **live, authored here** |
| `src/provisioning/` | `dotfiles-provision`: hexagon that drives Ansible + the `ansible/` tree (21 roles, 23 playbooks) | **live, authored here** |
| `dotfiles/config/`, `dotfiles/assets/` | Inputs: hypr Lua, hyprpaper, nvim, starship, wlogout, zsh, btop, rofi, icon mappings; wallpapers tarball, icon templates, btop themes | **live** (AGS subtree retired) |
| `dotfiles/applications/`, `dotfiles/scripts/` | `.desktop` files; `toggle-touchpad` | **live** |
| `dotfiles/provisioning/` | Declarative manifests: `cli-tools.yaml`, `assets.yaml`, `config-copies.yaml`, `filesystem.yaml`, `packages.yaml` | **live** (single source for pins) |
| `scripts/` | Gates: `deploy-coverage.py`, `ci-gates-parity.py`, `contract-pin-check.py`, `ansible-embedded-template-lint.py`; plus `worktree-guard.sh` | **live** |
| `contracts/` | Vendored event contract `{json,xml,md}` + four state JSON schemas; the runtime embeds byte-identical copies under `src/runtime/.../adapters/schemas/`, asserted by `contracts-check` | **live for conformance tests**; *not* the pin source (`src/runtime/.../test_event_contract_drift.py:59-68`) |
| `dev/` | Incus VM harness (`dev/vm`, `vm-fresh.sh`, …) for disposable provision runs | **live, local-only** (needs incus; not in CI) |
| `.dev/` | Gitignored on-demand `ags-platform` checkout for `make ags-platform-dev` | live, disposable |
| `openspec/` | `specs/` + `changes/`; `changes/archive/**` is immutable history (spine AD-15) | live + historical archive |
| `_bmad/`, `_bmad-output/` | BMAD harness; planning + implementation artifacts (incl. the cli-repos spine) | historical record |
| `prototypes/`, `spikes/` | Throwaway probes (canvas/Hyprland/DBus/schema) | **historical** |
| `.worktrees/` | Gitignored worktrees created by `scripts/worktree-guard.sh` | live, never committed |
| `AGENTS.md`, `CLAUDE.md` (symlink), `Makefile`, `bootstrap.sh` | The operating contract, gate set, fresh-machine entry point | live |

`src/cli-tools/`, `src/shared/`, `src/gui-tools/` and `dotfiles/config/ags/` no longer
exist as sources. Their absence is a gate, not a memory
(`scripts/deploy-coverage.py:1342-1358`, `:1752-1768`).

## 6. Provisioning

### 6.1 bootstrap stages

`bootstrap.sh` is the only fresh-machine entry point (`bootstrap.sh:12-24`):

| Stage | What | Failure mode |
|---|---|---|
| preflight | `$HOME` set, non-root, **usable** container engine (`podman`/`docker` info, 15 s timeout) | abort before the long run (`bootstrap.sh:154-212`) |
| 1. uv preseed | pinned uv `0.9.22`, sha256-verified tarball, version asserted | abort (`bootstrap.sh:224-293`) |
| 2. collections | `ansible-galaxy collection install -r ansible/requirements.yml`, then assert collections actually landed | loud abort (`bootstrap.sh:299-343`) |
| 3. bootstrap | `uv run --directory src/provisioning dotfiles-provision bootstrap` (+ forwarded become flags) | abort (`bootstrap.sh:415`) |
| 4. verify | `dotfiles-provision verify` with `check=False` — a real gate | abort (`bootstrap.sh:421`) |
| post | if Hyprland IPC is reachable, warn `DEGRADED` when GloView is not loaded | exit stays 0 (`bootstrap.sh:423-452`) |

### 6.2 role order

`bootstrap.yaml` is imports-only; the order is load-bearing and documented in its
header (`src/provisioning/ansible/playbooks/bootstrap.yaml:6-87`):

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
| `csg` | `COLORSCHEME__CONTAINER__IMAGE_TAG={{ item.tag }}` (its `v0.1.0` verb has **no** `--image-tag`) | `csg-{base,custom,pywal,wallust}-<engine>:<tag>` |

`roles/cli_tools/vars/main.yml:58-77` splits the two transports; `deploy-coverage`
asserts both carry `{{ item.tag }}` and that no literal tag appears in task code
(`scripts/deploy-coverage.py:1676-1735`).

### 6.5 assets, settings, verify

- **assets** copies `icon-templates`, `icon-mappings` and the config-copies inputs from the repo,
  plus csg templates from the **pinned checkout**
  (`<install>/cli-tools/csg/<tag>/src/color_scheme_generator/defaults/templates`), then emits
  `config/weg/effects.yaml` via `weg dump-effects` (`roles/assets/vars/main.yml:53-117`). It carries
  its own pin mirror (`assets_csg_pinned_tag: v0.1.0`); a parity test locks it.
- **settings** is the only author of the three `settings.toml` files, rendered from role-internal
  Jinja into the spine (`roles/settings/vars/main.yml:1-90`); it carries a third pin mirror
  (`settings_weg_image_tag`).
- **verify** is read-only and checks **provisioned locations only** — never the repo
  (`roles/verify/tasks/main.yml:1-60`). Its job is the fourteen done-criteria plus the pin
  assertions a green `command -v` would hide: tag-bearing checkout path, `pinned` record,
  installed version = tag minus `v`, `--version` contract token = `0.1.0`, and every image at
  the tag-qualified reference (`roles/verify/vars/main.yml:221-272`).

### 6.6 manifest, mirror, parity

There are three hand-maintained copies of the same pin, by design:

| Copy | File | Locked by |
|---|---|---|
| Manifest (authoritative) | `dotfiles/provisioning/cli-tools.yaml` | — |
| Role mirror | `src/provisioning/ansible/roles/cli_tools/vars/main.yml:104-114` | `deploy-coverage` (`assert_cli_provisioned_from_pinned_manifest`) + structural parity test |
| Verify mirror | `src/provisioning/ansible/roles/verify/vars/main.yml:231-272` | same parity family |

Plus per-consumer mirrors where a role cannot read the manifest: `assets_csg_pinned_tag`,
`settings_weg_image_tag`. A pin bump is therefore a multi-file edit, and the gate that
proves it is `make deploy-coverage` (section 11, recipe (a)).

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

`dotfiles-runtime` (`src/runtime/`, console script `runtime.cli.main:app`) is a
hexagon: `domain` (pure, zero-I/O, stdlib allowlist), `ports`, `adapters`,
`application`, `cli` — each layer's allowed imports are a test
(`src/runtime/tests/architecture/test_layering.py:60-72`).

### 7.1 CLI surface

`wallpaper set` · `inspect {status,daemon,history,cache list}` · `icons {regenerate,preference}` ·
`gtk4 restart` · `daemon run` · top-level `reconcile`, `doctor`, `capture`, `clipboard`, `version`
(`src/runtime/src/runtime/cli/main.py`). `wallpaper set` is the visible-first apply → derive →
reconcile chain; `daemon run` is the resident hub, i.e. the `systemd ExecStart` surface.

### 7.2 CLI adapters — argv/env/artifacts, never stdout

The runtime couples to a CLI by **subprocess, exit status, artifact filenames and hashes**. It
does not import the CLI, does not parse stdout as JSON, and does not `command -v` to choose a binary.

| Adapter | argv | Injected env | Artifacts verified |
|---|---|---|---|
| `csg_adapter.py:280-300` | `csg generate <wallpaper> --format yaml --format conf --format gtk.css --format adw.css --format sequences --format rasi --format kitty --format btop.theme` | `COLORSCHEME__OUTPUT__DIRECTORY`, `COLORSCHEME__OUTPUT__OVERWRITE=true` | eight palette files, hashed |
| `weg_adapter.py:332-338` | `weg batch all -- <wallpaper>` | `WALLPAPER__OUTPUT__DIRECTORY` etc. | effect images, hashed |
| `itr_adapter.py:410-419` | `itr render [<icons.yaml>]` | `ICON_RENDERER__OUTPUT__OUTPUT_DIR`, `ICON_RENDERER__COLOR_SCHEME__PATH` | SVGs, hashed |

The env passed is an **allowlist**, not `dict(os.environ)`: exact keys (`PATH`,
`HOME`, `XDG_*`, locale/TLS/proxy), prefixes `COLORSCHEME__`, `WALLPAPER__`,
`ICON_RENDERER__`, `XDG_`, and a secret blocklist (`TOKEN`, `SECRET`, `PASSWORD`,
`AWS_`, `GITHUB_`) — `src/runtime/src/runtime/adapters/env.py:22-87`. Both sides
assert the same record through `cli_invocation_contract.testkit`
(`src/runtime/tests/unit/test_cli_invocation_contract.py:16-17`).

**ITR: `templates_dir` is a hash input, not a render instruction.** `ItrAdapter.render`
hashes the `templates_dir` argument into the entry hash (`itr_adapter.py:232-239`, then
`icons_entry_hash` at `:317`) but forwards only `ICON_RENDERER__OUTPUT__OUTPUT_DIR` and
`ICON_RENDERER__COLOR_SCHEME__PATH` (`:403-408`); argv is `itr render [<icons.yaml>]`
(`:410-419`) — **no** `--template-dir`, **no** `ICON_RENDERER__TEMPLATES__DIR`. `itr`
therefore resolves its render templates from *its own* config chain: `[templates] dir`
in `~/.config/itr/settings.toml`, rendered by provisioning to `<spine>/icon-templates`
(`roles/settings/templates/itr-settings.toml.j2:8-9`), else its own discovery. Each
`variants[].template` is joined under that root with the group `template_dir` default
`"."` (`itr` `src/icon_templates_renderer/adapters/yaml_icon_config_loader.py:78,101`),
so mapping entries are spelled **relative to the spine root**
(`status-bar/battery/battery-0/default/icon.svg`) — a mapping-local `battery/` subdir
resolves to `<spine>/battery/…` and fails.

The two corpora coincide by *provisioning*, not by adapter enforcement: production passes
`find_icon_templates(install_spine)` = `<spine>/icon-templates`
(`application/derive.py:174-177, 1002`), i.e. the same path the settings role writes into
`itr`. If they diverge — `DOTFILES_DEV_INPUTS_ROOT` (checked-in
`dotfiles/assets/icon-templates`), or a host `ICON_RENDERER__TEMPLATES__DIR` /
`--template-dir` override — the hashed corpus is not the rendered one and `ih` stops
covering the artifacts. `src/runtime/tests/integration/test_itr_adapter_integration.py`
pins them together explicitly (the allowlisted `ICON_RENDERER__` prefix, `env.py:50`,
forwards a `monkeypatch.setenv` into the subprocess) and uses the real group shape, so the
only real-`itr` integration test renders instead of skipping.

### 7.3 Config resolution chain (CLI-side, unchanged by the split)

`--config` → env (`<PREFIX>__SECTION__KEY`) → cwd traversal → XDG
(`~/.config/<subdir>/settings.toml`) → packaged default (`docs/investigation/S3-config-flow.md` §0).
Provisioning does not fight this: it renders into the spine and symlinks `~/.config/<tool>` at it,
so native XDG discovery finds the rendered file. The *runtime's* input resolution is stricter — it
resolves the **install spine only**, consulting a repo checkout solely via the explicit
`DOTFILES_DEV_INPUTS_ROOT` override (`src/runtime/src/runtime/application/derive.py:12-13`).

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
(`src/runtime/src/runtime/adapters/cache.py:51-143`). Symlink repoints are atomic (tmp link +
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
| In this repo | vendored binding `src/runtime/.../domain/contract_generated.py` at `CONTRACT_PIN` = `dbdc5b8`; conformance copies in `contracts/` | git-tag pin in `src/runtime/pyproject.toml:27` |
| Drift gate | `make contracts-check` → embedded schemas byte-equal canonical, wire XML agrees with JSON, baked tables equal generated bindings | `contracts-check` (`test_cli_invocation_contract.py`) + `make contract-pin-check` |

`make contract-pin-check` diffs each vendored copy against `contracts/generated/` and **fails on a
hand-edit**; it is deliberately **not** in `GATES`, because a CI runner here has no sibling
`contracts` checkout and the gate would only skip (`Makefile:16-32`). The negative test proving it
fails on a hand-edit *is* hermetic and runs via `contracts-check`
(`src/runtime/tests/unit/test_contract_pin_check.py`).

**Same-tag rule:** one `contracts` tag (`v0.1.0`) is pinned by the runtime and all three CLIs,
and each CLI's `--version` token must equal it; neither side duplicates the contract data in
tests (spine AD-4).

## 9. Gates

### 9.1 `gates-ci` = `GATES` (no exclusions today)

| Target | What it proves |
|---|---|
| `contracts-check` | embedded state schemas are byte-identical to `contracts/schemas/`; D-Bus wire XML agrees with the event-contract JSON; the hub/bar tables equal the vendored generated bindings; the `history` trigger enum matches; the pin-check's negative test still fails on a hand-edit |
| `runtime-architecture` | the runtime's mechanical architecture guards: hexagonal layering (no layer imports a layer above it) and no retired-source references — no runtime source may name the deleted `cli-tools`/`shared`/`gui-tools` trees, contiguous or as a `"src" / "<retired>"` path-join (`src/runtime/tests/architecture/test_no_retired_sources.py`); 132 tests, ~2.3 s, stock-runner capable |
| `ansible-embedded-template-lint` | no `{{ }}` nested inside a Jinja *expression* string (`assert.that`, `when`, …) — the construct ansible-core 2.23 disables |
| `deploy-coverage` | provisioning **shape**: no per-file bar/app sources, both external units installed + live links, pinned CLI manifests installed from tag-bearing checkouts, image tag = pin, retired trees absent, exactly one local `source:` |
| `ci-gates-parity` | `.github/workflows/gates.yml` job set equals `gates-ci` in both directions, modulo declared `RENAMES` / `CI_ONLY_EXEMPT` / `CI_EXCLUDED_GATES` (all empty but one rename: `contracts-check -> contracts`) |
| `per-app-drift-symbol-suites` | currently a legible no-op: every in-repo drift suite moved to `ags-apps` with its app (`Makefile:154-198`) |

`make hermetic` is **intentionally a no-op PASS**: `HERMETIC_PACKAGES` is empty — the six extracted
packages run their own `make hermetic` in their pinned repos (`Makefile:95-141`); the target stays so
a future in-repo package can be listed.

### 9.2 Per-repo gate sets

The six extracted repos run `test lint hermetic lock-check docs-check` (plus `image` for
`csg`/`weg`, `test-all` for `itr`) and `ci-gates-parity`; measured green from a foreign cwd with
`make -C <repo> gates` (`POST-MIGRATION.md` §1). `ags-apps` owns the GUI gates (`bar-typecheck`,
`ags-test`, per-app typecheck/test/drift) — not this repo's, and never to be re-added here.

### 9.3 Known pre-existing failures (name them, do not rediscover them)

| Failure | Count / shape | Status |
|---|---|---|
| `src/runtime` suite | `tests/unit/test_recording_indicator.py::TestNoPollingInvariant::test_bar_widget_has_no_poll_loop` — `FileNotFoundError` on the retired `dotfiles/config/ags/bar/widgets/recording.tsx` | pre-existing; the bar moved to the unit, the test's hard-coded path did not |
| `src/runtime` integration | `test_weg_adapter_integration_real_binary` **passes** on a provisioned host (verified 2026-10-21: `1 passed` in ~18 s) and **skips** when the CLI binary is unavailable (e.g. `~/.local/bin` off `PATH`) — that skip is the designed behaviour, not a failure | environment-dependent by design |
| `src/provisioning` | `pytest tests/unit/test_verify_role.py -k TestVerifyRuntime` → `6 failed, 3 passed` — the simulated layout lacks `<install>/cli-tools/itr/pinned`, which verify now reads | pre-existing (same six at base `6e0633ba`) |
| `openspec validate --all` | `104 passed, 27 failed (131 items)`, exit 1; identical failing set at base `6e0633ba` (19 legacy change-level + 8 legacy spec-shape defects) | pre-existing, none of them `cli-tools-repos` |

Re-measured 2026-10-21 in the worktree for this document: `make gates-ci` exit 0 (six gates),
`openspec validate --all` → `Totals: 104 passed, 27 failed (131 items)`.

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

The six repos satisfied POST-MIGRATION tasks 0.1–0.6 by execution, with the two paperwork gaps closed by the
POST-MIGRATION addendum (`POST-MIGRATION.md` §A2). `contracts` predates the checklist
and ships `validate`/`generate`/`check-symmetry`/`contracts-drift`/`test`/`build`
rather than a `gates` target.

### 10.2 Two rituals, one checklist each

- **Pin bump:** the manifest is authoritative and every mirror is gate-locked (section 6.6); the end-to-end checklist is recipe (a) in section 11.
- **Destructive-last:** item 6 above. Rollback is always a pin bump plus a revert of the deletion commit — never a retag.

## 11. Extension recipes

### (a) Bump a pin end-to-end

1. Tag the source repo (annotated `vX.Y.Z`; never move the old tag).
2. Manifest: `dotfiles/provisioning/cli-tools.yaml` (`tag:` for a CLI).
3. Role mirror: `roles/cli_tools/vars/main.yml` (`cli_tools:`).
4. Verify mirror: `roles/verify/vars/main.yml` (`verify_<name>_version`, checkout path, pin file, `verify_<name>_contract_version` if the contract moved).
5. Role-local mirrors the source feeds: `roles/assets/vars/main.yml` (`assets_csg_pinned_tag`), `roles/settings/vars/main.yml` (`settings_weg_image_tag`).
6. If a library or `contracts` moved: bump `[tool.uv.sources]` in `src/runtime/pyproject.toml` and/or `src/provisioning/pyproject.toml`, then `uv lock` there.
7. If the contract moved: re-vendor the binding, update `CONTRACT_PIN`, run `make contract-pin-check` against a sibling `contracts` checkout.
8. Prove: `make deploy-coverage`, `make gates-ci`, and on a host `dotfiles-provision verify` (the only place the pin is asserted *by execution*).

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

1. Add the source under `dotfiles/config/<tool>/`.
2. Register it in `src/provisioning/ansible/roles/compositor_configs/vars/main.yml` (`compositor_configs_skeleton_files`).
3. Mirror it in `roles/verify/vars/main.yml` (`verify_compositor_skeleton_files`) if verify must assert it.
4. Prove: `make deploy-coverage` and `uv run --directory src/provisioning pytest tests/unit/test_compositor_configs_role.py tests/unit/test_verify_role.py -q`.

Do **not** register a bar file: the bar deploys whole from `ags-apps`, and a per-file entry would template into the unit tree through the live link.

### (e) Add a gate

1. Add the target to `GATES` in the `Makefile` (never a second list; `gates-ci` inherits it).
2. Add one matching job to `.github/workflows/gates.yml` (or a `RENAMES` entry in `scripts/ci-gates-parity.py`).
3. If it cannot run on a stock runner, declare it in `CI_EXCLUDED_GATES` / `CI_SELF_HOSTED_GATES` with a reason — never leave it silently absent.
4. Prove: `make ci-gates-parity` and `make gates-ci` both exit 0.

## 12. Known constraints and residuals

- **No PyPI, no registry.** Consumers pin git tags; images build at provision time from the pinned checkout and are never published or digest-pinned (spine OPEN-2/OPEN-3; `POST-MIGRATION.md` §A1.3).
- **Pins must be public and anonymously fetchable.** Provisioning clones over anonymous HTTPS with no credential helper; a private repo breaks `ansible.builtin.git` (`roles/ags_apps/vars/main.yml:88-90`; `openspec/specs/cli-repo-birth/spec.md:98-120`). All seven were verified public.
- **Builds happen on the host, at provision time**, so `verify` needs a working container engine; `bootstrap.sh` refuses to start without one.
- **No VM in CI.** `dev/` drives an incus VM, but `incus` is absent on this host and no workflow references it; the disposable-VM half of the closure is still open (`POST-MIGRATION.md` §A3 gap (a)).
- **Host-specific systemd pitfall.** A unit `ExecStart` line ending in a Jinja *block* tag (e.g. `{% endif %}`) swallows the next line (Ansible `trim_blocks`) → systemd runs `daemon run# …` → `No such command 'run#'` → `start-limit-hit`. Keep `runtime_daemon_run_flags` single-line (`roles/runtime_daemon/vars/main.yml:26-35`).
- **Stale uv-tool envs after moving/deleting a tree.** `uv tool list` can report the right version while the env's `direct_url.json` points at a deleted path, so every console dies with `ModuleNotFoundError`. After a tree-deletion merge: `rm -rf <retired root>` in the checkout you are about to gate, then `make deploy-coverage` *there* — absence guards read the filesystem, not `git ls-files` (`POST-MIGRATION.md` §1 note, §A1.2).
- **`csg install` has no `--image-tag`** (the tag travels via `COLORSCHEME__CONTAINER__IMAGE_TAG`); `csg install --image-tag …` exits 2. The tag gate is clone + `verify`, not option parsing (`POST-MIGRATION.md` gap (c)).
- **`openspec validate --all` keeps 27 failures** — 19 legacy change-level + 8 legacy spec-shape defects, none `cli-tools-repos` (`POST-MIGRATION.md` gap (e); re-measured 2026-10-21).
- **Literal stale-path text remains** in the guard, its negative-test fixtures and read-only investigation docs — 338 lines in 9 files on 2026-10-21 (`POST-MIGRATION.md` gap (f)). The **test-side** half of that residue is removed + guarded by `src/runtime/tests/architecture/test_no_retired_sources.py` (`94b3f4a0`): the retired-tree discovery walks in `src/runtime/tests/integration/test_csg_determinism.py`, `tests/integration/test_itr_adapter_integration.py`, `tests/unit/test_csg_adapter.py` and `tests/unit/test_itr_adapter.py` are gone, and the two integration files share explicit resolution in `tests/integration/conftest.py` (`resolve_csg_templates_dir` / `resolve_icon_templates_dir`: env override → pinned CLI corpus / checked-in `dotfiles/assets/icon-templates` → loud skip, never a silent pass). The guard fails on any reintroduced contiguous `src/cli-tools` / `src/shared` / `src/gui-tools` literal **or** the `"src" / "<retired>"` path-join form (`rg` misses the latter), in production or tests, and names the spine / pinned-repo fix. It runs in `gates-ci` as the `runtime-architecture` gate (`d67849ba`), so it is enforced on every push rather than only when someone runs pytest by hand.
- **CSG templates dir is a required caller input — residual resolved** (`e8fc0916`). The retired repo-relative discovery is gone: `_find_default_templates_dir` — which walked file ancestors for the stale in-tree csg checkout under the retired `src/cli-tools/color-scheme-generator/...` — and its `generate` call site were deleted. `CsgAdapter.generate` now raises a `FileNotFoundError` that names the cause and the fix (`templates_dir` must be resolved from the provisioning spine and passed by the caller) **before** hashing or spawning a subprocess, while `__init__` stays side-effect-free so `CsgAdapter().is_available()` remains legitimate. Every production construction already passed an explicit dir — seven `CsgAdapter(...)` sites at `src/runtime/src/runtime/cli/main.py:275, 648, 671, 966, 1287, 1518, 1611` and three `InvalidationQueryAdapter(...)` sites at `:1326, 1416, 1520`, all with `templates_dir=find_templates_dir(install_spine)` — so no provisioned path changes; only a bare `CsgAdapter()` can now fail loudly instead of silently discovering nothing. Regression test: `src/runtime/tests/unit/test_csg_adapter.py::test_csg_adapter_generate_without_templates_dir_raises` asserts the message names `templates_dir` and that `subprocess.run` was never called; the integration test no longer discovers either (it takes `DOTFILES_CSG_TEMPLATES_DIR`, else the on-PATH binary's `dump-templates` corpus, else skips with "discovery fallback removed"). Guard: `src/runtime/tests/architecture/test_no_retired_sources.py` — `rg -n 'src/cli-tools|_find_default_templates_dir' src/runtime` now matches only that guard file (its scan patterns), and the guard runs in `gates-ci` as `runtime-architecture` (`d67849ba`).
- **Per-app repo split is deferred** (GUIDE §7 exit gate unmet); `ags-apps` stays a monorepo consumed as one unit (`docs/HANDOFF-ags-platform.md` §2).

## 13. Documentation index

Repo docs (`docs/`), one line each. "Normative" = a live source of truth; "historical" =
provenance, not to be edited into agreement with today. Spine artifacts sit under
`_bmad-output/planning-artifacts/architecture/architecture-cli-repos-2026-10-19/`.

| Document | What it is | Status |
|---|---|---|
| `docs/99-dotfiles-hexagonal-architecture.md` | Dual-domain vision + Domain 1 as-built; runtime phases 2–6 are **planned, not built** | normative (Domain 1) / historical (Domain 2) |
| `docs/01-dotfiles-provisioning-phase1-plan.md` | Phase-1 provisioning plan + Epic-4 amendment (removes `default_palette`/`icons`/`generated/`) | historical, amended |
| `docs/02-config-in-spine-pattern.md` | Config-in-spine decision record (spine + symlinks + backup guard) | normative |
| `docs/100-ags-bar-rearchitecture.md` | Bar re-architecture exploration + prototype log | historical |
| `docs/101-ags-platform-architecture.md` | AGS platform design of record (ports, schemas, icon contract); its `bar-v0.1.1` pin note is stale | normative |
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
