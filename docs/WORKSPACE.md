# Workspace map — the dotfiles ecosystem

The system is intentionally split into pinned repos. This is the one-page map of **who owns what**
and **which tag each consumer pins**. It is the cross-project companion to each repo's README.

## Layout

```text
~/Development/dotfiles/
├── dotfiles-v3                 composition: manifests, gates, bootstrap
├── dotfiles-provision          installer engine: Ansible tree + Python orchestrator
├── dotfiles-runtime            host runtime: wallpaper/state/cache, daemon, clipboard
├── dotfiles-assets             pinned corpus: icons, templates, configs, content, desktop
├── ags-apps                    pinned AGS unit: bar + notifications/capture/hypr-pano/…
├── ags-platform                pinned AGS platform: ports, shared adapters, event client
├── contracts                   event contract + state schemas
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
| `dotfiles-v3` | manifests, composition gates, `bootstrap.sh` | engine roles, runtime, corpus bytes, bar/apps source, CLI source |
| `dotfiles-provision` | Ansible roles/playbooks/inventory, Python orchestrator, engine tests | composition manifests, runtime, corpus, app source |
| `dotfiles-runtime` | host runtime: wallpaper/state/cache, daemon, clipboard, contract conformance | composition manifests, installer roles, corpus, app/CLI source |
| `dotfiles-assets` | the five corpus classes and their validators | destinations, consumers, runtime state |
| `ags-apps` | the AGS bar + sibling apps, their pure logic and tests | platform ports/adapters, dotfiles provisioning |
| `ags-platform` | reusable ports, shared adapters, event-contract client | app policy, dotfiles paths |
| `contracts` | event contract JSON/XML/spec + state schemas | consumers |
| `cli-output` | CLI rendering views/adapters | tool policy |
| `csg` / `weg` / `itr` | their CLI + container/backend logic | composition pins |

## Pins (live)

| Consumer | Pinned artifact | Tag | Declared in |
| --- | --- | --- | --- |
| `dotfiles-v3` | installer engine `dotfiles-provision` | `v0.1.11` | `dotfiles/provisioning/installer.pin` |
| `dotfiles-v3` | corpus `dotfiles-assets` | `v0.5.0` | `dotfiles/provisioning/assets.yaml` |
| `dotfiles-v3` | CLIs `csg`/`weg`/`itr` + runtime `dotfiles-runtime` | `v0.2.0` each / `v0.1.0` | `dotfiles/provisioning/cli-tools.yaml` |
| `dotfiles-runtime` | `cli-output` | `v0.1.0` | runtime `pyproject.toml` |
| `dotfiles-runtime` | `contracts` | `v0.2.0` | runtime `pyproject.toml` |
| `dotfiles-provision` | `ags-apps` unit | `v0.4.1` | `ansible/roles/ags_apps/vars/main.yml` |
| `dotfiles-provision` | `ags-platform` unit | `v0.2.0` | `ansible/roles/ags_apps/vars/main.yml` |
| `ags-apps` | `ags-platform` | `v0.2.0` | `Makefile` (`AGS_PLATFORM_VERSION`) |
| `dotfiles-assets` repo | its own release | `v0.5.1` | git tag (composition still consumes `v0.5.0`) |

A tag is never moved. A fix ships as a new tag. Consumer pin bumps edit the declared file first,
then the mirrors; `make deploy-coverage` fails on a half-edit.

## Direction rules

- Apps → platform → contracts. Never app → app.
- Composition → pinned engine/corpus/CLIs. Never a path or `editable` install.
- Engine → composition only through the CLI seam (`--manifests-dir`, `--composition-root`); no
  role derives a composition path from `playbook_dir`.
- The corpus names no destination; the composition manifest owns deployment paths.

## Local development

Each repo has its own `AGENTS.md`, gates and worktree guard. Run gates from the repo you edit; the
composition's `make gates-ci` reads the cached engine checkout and does not vendor it.
