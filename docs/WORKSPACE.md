# Workspace map — the dotfiles ecosystem

The system is intentionally split into pinned repos. This is the one-page map of **who owns what**
and **which tag each consumer pins**. It is the cross-project companion to each repo's README.

## Layout

```text
~/Development/dotfiles/
├── dotfiles-v3                 composition: app list, program tuple, manifests, gates, bootstrap
├── dotfiles-provision          installer engine: Ansible tree + Python orchestrator
├── dotfiles-runtime            host runtime: wallpaper/state/cache, daemon, clipboard
├── dotfiles-assets             pinned corpus: icons, templates, configs, content, desktop
├── ags-platform                pinned AGS platform: ports, shared adapters, event client
├── ags-bar                     standalone AGS bar (AGS instance `ags`)
├── ags-notifications           standalone notification overlay
├── ags-capture-tool            standalone capture tool (+ capture-tool backend)
├── ags-clipboard               standalone clipboard overlay
├── ags-wallpaper-selector      standalone wallpaper selector
├── ags-icme                    standalone icon color mapping editor
├── ags-btop-theme-studio       standalone btop Theme Studio
├── ags-apps                    retired migration workshop (archive after publish)
├── contracts                   event contract + state/app schemas
├── cli-output                  shared CLI rendering package
├── color-scheme-generator      `csg`
├── wallpaper-effects-generator `weg`
├── icon-templates-renderer     `itr`
├── config-assembler-engine     `cae` (consumed inside the CLIs)
└── oci-runtime                 container engine abstraction (consumed inside csg/weg)
```

## Ownership

| Repo | Owns | Does **not** own |
| --- | --- | --- |
| `dotfiles-v3` | app list + program tuple, manifests, composition gates, `bootstrap.sh` | engine roles, runtime, corpus bytes, app source, CLI source |
| `dotfiles-provision` | Ansible roles/playbooks/inventory, Python orchestrator, engine tests | composition manifests, runtime, corpus, app source |
| `dotfiles-runtime` | host runtime: wallpaper/state/cache, daemon, clipboard, manifest-driven refresh | composition manifests, installer roles, corpus, app/CLI source |
| `dotfiles-assets` | the five corpus classes and their validators | destinations, consumers, runtime state |
| `ags-platform` | reusable ports, shared adapters, event-contract client | app policy, dotfiles paths |
| `ags-bar` / the six `ags-*` app repos | their app package, manifest, `palette-refresh` handler and tests | platform ports/adapters, dotfiles provisioning |
| `ags-apps` | retired migration workshop; archive after the local tags are published | any live deployment surface |
| `contracts` | event contract JSON/XML/spec + state/app schemas | consumers |
| `cli-output` | CLI rendering views/adapters | tool policy |
| `csg` / `weg` / `itr` / `tpr` | their CLI + container/backend logic (tpr = default palette producer) | composition pins |

## Pins (live)

| Consumer | Pinned artifact | Tag | Declared in |
| --- | --- | --- | --- |
| `dotfiles-v3` | installer engine `dotfiles-provision` | `v0.1.27` | `dotfiles/provisioning/installer.pin` |
| `dotfiles-v3` | corpus `dotfiles-assets` | `v0.6.2` | `dotfiles/provisioning/assets.yaml` |
| `dotfiles-v3` | CLIs `csg`/`weg`/`itr`/`tpr` + runtime `dotfiles-runtime` | `csg v0.2.2` / `weg/itr v0.2.0` / `tpr v0.4.0` / `runtime v0.4.1` | `dotfiles/provisioning/cli-tools.yaml` |
| `dotfiles-v3` | program tuple `ags-platform` / `contracts` / `dotfiles-assets` | `v0.3.0` / `v0.3.0` / `v0.6.2` | `dotfiles/provisioning/program-tuple.yaml` |
| `dotfiles-v3` | seven AGS app units (bar + notifications/capture/clipboard/wallpaper-selector/icme/btop-theme-studio) | `ags-bar v0.1.3`; five `v0.1.0`; `ags-btop-theme-studio v0.1.2` | `dotfiles/provisioning/apps.yaml` |
| `dotfiles-runtime` | `cli-output` | `v0.1.0` | runtime `pyproject.toml` |
| `dotfiles-runtime` | `contracts` | `v0.4.0` | runtime `pyproject.toml` |
| `theme-producer` | `contracts` | `v0.4.0` | tpr `pyproject.toml` |
| `dotfiles-provision` | `ags-platform` unit | `v0.3.0` | `ansible/roles/ags_platform/vars/main.yml` |
| `dotfiles-assets` repo | its own release | `v0.6.2` | git tag (composition consumes the same) |

A tag is never moved. A fix ships as a new tag. Consumer pin bumps edit the declared file first,
then the mirrors; `make deploy-coverage` fails on a half-edit.

Runtime note: engine `v0.1.27` consumes and verifies `dotfiles-runtime v0.4.1`,
`csg v0.2.2` and `theme-producer v0.4.0` in `cli_tools` and `verify`; runtime and
engine pins are aligned. The composition selects `tpr` as the default producer
by exporting `RUNTIME_PALETTE_PRODUCER=tpr` in `bootstrap.sh`; the engine renders
`config/dotfiles-runtime/producer.json`. An explicit
`RUNTIME_PALETTE_PRODUCER=csg` is the documented rollback.

## AGS app ownership and cutover

`dotfiles/provisioning/apps.yaml` is the **single** AGS app list and ownership
source (AD-31/AD-32). Each app appears once with `owner: standalone` and every
surface it owns (install dir, config/spine/XDG links, optional bin link,
launcher, autostart, launch policy, palette pointer, cutover id).
`dotfiles/provisioning/program-tuple.yaml` names the one
`ags-platform`/`contracts`/`dotfiles-assets` tag triple for the install.

- **Final all-standalone topology.** All seven entries are `owner: standalone`;
  `ags_apps_units` is the only installer/owner. The retired `ags_apps` monorepo
  role/playbook no longer exists.
- **One owner per app.** Each app installs at
  `<install>/apps/<installDir>/<tag>/` and resolves the ONE shared
  `<install>/apps/node_modules/ags-platform` shortcut. No second per-app list,
  deny-list or legacy role.
- **Surfaces come from the list.** The engine's `ags_apps_units` role creates
  the spine/XDG links, optional bin link and launcher; the assets-owned
  `autostart.lua` starts only the declared identities, exactly once, through
  `ags-run-locked`.
- **Cutover is an epoch**, one app per composition commit: quiesce the old
  instance (confirmed quit, no process, no D-Bus name) → flip `owner` →
  install/repoint/start → verify identity and every surface → rollback is the
  reverse. See [`102-ags-app-consumption.md`](./102-ags-app-consumption.md).
- **No permanent meta repo.** `ags-apps` is retired; publish the local tags and
  archive the repo as the external closeout step.

## Direction rules

- Apps → platform → contracts. Never app → app.
- Composition → pinned engine/corpus/CLIs. Never a path or `editable` install.
- Engine → composition only through the CLI seam (`--manifests-dir`, `--composition-root`); no
  role derives a composition path from `playbook_dir`.
- The corpus names no destination; the composition manifest owns deployment paths.
- `apps.yaml` is the only app list; a role derives its surfaces from it, never from a
  parallel per-app registry.

## Local development

Each repo has its own `AGENTS.md`, gates and worktree guard. Run gates from the repo you edit; the
composition's `make gates-ci` reads the cached engine checkout and does not vendor it.
