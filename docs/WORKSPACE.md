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
├── ags-apps                    migration workshop: monorepo apps until each repo moves
├── ags-platform                pinned AGS platform: ports, shared adapters, event client
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
| `dotfiles-v3` | app list + program tuple, manifests, composition gates, `bootstrap.sh` | engine roles, runtime, corpus bytes, bar/apps source, CLI source |
| `dotfiles-provision` | Ansible roles/playbooks/inventory, Python orchestrator, engine tests | composition manifests, runtime, corpus, app source |
| `dotfiles-runtime` | host runtime: wallpaper/state/cache, daemon, clipboard, contract conformance | composition manifests, installer roles, corpus, app/CLI source |
| `dotfiles-assets` | the five corpus classes and their validators | destinations, consumers, runtime state |
| `ags-apps` | the migration workshop until the last app moves; then archived | platform ports/adapters, dotfiles provisioning |
| `ags-platform` | reusable ports, shared adapters, event-contract client | app policy, dotfiles paths |
| `contracts` | event contract JSON/XML/spec + state/app schemas | consumers |
| `cli-output` | CLI rendering views/adapters | tool policy |
| `csg` / `weg` / `itr` | their CLI + container/backend logic | composition pins |

## Pins (live)

| Consumer | Pinned artifact | Tag | Declared in |
| --- | --- | --- | --- |
| `dotfiles-v3` | installer engine `dotfiles-provision` | `v0.1.17` | `dotfiles/provisioning/installer.pin` |
| `dotfiles-v3` | corpus `dotfiles-assets` | `v0.6.1` | `dotfiles/provisioning/assets.yaml` |
| `dotfiles-v3` | CLIs `csg`/`weg`/`itr` + runtime `dotfiles-runtime` | `csg v0.2.1` / `weg/itr v0.2.0` / `runtime v0.2.3` | `dotfiles/provisioning/cli-tools.yaml` |
| `dotfiles-v3` | program tuple `ags-platform` / `contracts` / `dotfiles-assets` | `v0.3.0` / `v0.3.0` / `v0.6.1` | `dotfiles/provisioning/program-tuple.yaml` |
| `dotfiles-runtime` | `cli-output` | `v0.1.0` | runtime `pyproject.toml` |
| `dotfiles-runtime` | `contracts` | `v0.2.0` | runtime `pyproject.toml` |
| `dotfiles-provision` | `ags-apps` unit (legacy, until the last cutover) | `v0.4.3` | `ansible/roles/ags_apps/vars/main.yml` |
| `dotfiles-provision` | `ags-platform` unit (legacy shortcut, until adoption) | `v0.2.0` | `ansible/roles/ags_apps/vars/main.yml` |
| `ags-apps` | `ags-platform` | `v0.2.0` | `Makefile` (`AGS_PLATFORM_VERSION`) |
| `dotfiles-assets` repo | its own release | `v0.6.1` | git tag (composition consumes the same) |

A tag is never moved. A fix ships as a new tag. Consumer pin bumps edit the declared file first,
then the mirrors; `make deploy-coverage` fails on a half-edit.

## AGS app ownership and cutover

`dotfiles/provisioning/apps.yaml` is the **single** AGS app list and ownership
source (AD-31/AD-32). Each app appears once with `owner: legacy|standalone` and
every surface it owns (install dir, config/spine/XDG links, optional bin link,
launcher, autostart, launch policy, bar palette pointer, cutover id).
`dotfiles/provisioning/program-tuple.yaml` names the one
`ags-platform`/`contracts`/`dotfiles-assets` tag triple for the install.

- **One owner per app.** The old monorepo role filters `owner: legacy`; the
  per-app role filters `owner: standalone`. No second per-app list and no
  deny-list.
- **All seven apps are legacy today.** `make deploy-coverage` validates the list,
  the tuple, the one-owner invariant and the current legacy surfaces against the
  pinned engine; it also runs legacy/mixed/all-standalone fixtures.
- **Cutover is an epoch**, one app per composition commit: quiesce the old
  instance (confirmed quit, no process, no D-Bus name) → flip `owner` →
  install/repoint/start → verify identity and every surface → rollback is the
  reverse. See [`102-ags-app-consumption.md`](./102-ags-app-consumption.md) for
  the checklist and field semantics.
- **No permanent meta repo.** The old `ags-apps` pin/role is removed and the
  repo archived only after the last app moves.

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
