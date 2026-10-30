# dotfiles-v3 — the composition repo

`dotfiles-v3` is the **composition** of the dotfiles system. It owns the declarative manifests,
the composition gates, and the fresh-machine entry point. It does **not** own the installer
engine, the asset corpus, the AGS unit, the runtime, or the CLI sources — those are pinned
siblings (see [`docs/WORKSPACE.md`](docs/WORKSPACE.md)).

## Workspace

The sibling repos are expected under `~/Development/dotfiles/`:

```text
dotfiles-v3          this repo: manifests, gates, bootstrap
dotfiles-provision   installer engine: Ansible tree + Python orchestrator
dotfiles-runtime     host runtime: wallpaper/state/cache, daemon, clipboard
dotfiles-assets      pinned corpus: icons, templates, configs, content, desktop
ags-platform         pinned AGS platform: ports, adapters, event client
ags-bar / ags-*      seven standalone AGS app repos (bar, notifications, capture-tool,
                     clipboard, wallpaper-selector, icme, btop-theme-studio)
contracts            event contract + schemas
cli-output           shared CLI rendering package
color-scheme-generator / wallpaper-effects-generator / icon-templates-renderer
theme-producer       semantic-role palette producer (`tpr`; composition default)
config-assembler-engine / oci-runtime
```

The canonical ownership/pin map is [`docs/WORKSPACE.md`](docs/WORKSPACE.md); the executable pin
set is `ARCHITECTURE.md` §4.1 and `make deploy-coverage`.

## Quick start

```bash
./bootstrap.sh                 # fresh machine: uv → engine → collections → bootstrap → verify
make bootstrap ARGS="--ask-become-pass"   # same, through make
make provision ARGS="verify --expected-engine-tag v0.1.27"  # installed console
make gates-ci                  # four composition gates
make deploy-coverage           # pin-set + composition-only shape
openspec validate --all        # spec/change baseline
```

`bootstrap.sh` reads `dotfiles/provisioning/installer.pin` (currently `v0.1.27`), installs the
engine from `git+…@tag`, fetches the pinned assets corpus (`v0.6.2`), and runs the aggregate.
The engine is never edited here; neither is the runtime (`dotfiles-runtime@v0.4.1`, the tag
engine `v0.1.27` consumes and verifies). The CLI set is `csg@v0.2.2`/`weg`/`itr` (compute
providers) plus `tpr` (`theme-producer@v0.4.0`, the default palette producer). The engine renders
`config/dotfiles-runtime/producer.json` from `RUNTIME_PALETTE_PRODUCER`, which `bootstrap.sh`
defaults to `tpr`; run `RUNTIME_PALETTE_PRODUCER=csg ./bootstrap.sh` to roll back to the csg
producer. Engine `v0.1.27` installs the final all-standalone
AGS topology: seven released app repos (`ags-bar v0.1.3`, five `v0.1.0`, and
`ags-btop-theme-studio v0.1.2`) from
`dotfiles/provisioning/apps.yaml`; the old `ags-apps` monorepo role is retired.

## What lives here

| Path | What it is |
| --- | --- |
| `dotfiles/provisioning/` | Manifests (`assets.yaml`, `cli-tools.yaml`, `config-copies.yaml`, `filesystem.yaml`, `packages.yaml`), app data (`apps.yaml`, `program-tuple.yaml`) + `installer.pin` |
| `scripts/` | Composition gates (`deploy-coverage.py`, `ags_app_consumption.py`, `ci-gates-parity.py`, `ansible-embedded-template-lint.py`, `engine_checkout.py`) |
| `dev/` | Local-only incus VM harness |
| `docs/` | Live design/runbook docs; historical documents are labelled |
| `openspec/` | Specs + active changes; `openspec/changes/archive/` is immutable history |
| `_bmad-output/`, `spikes/`, `prototypes/` | Historical planning/prototype record (not runtime input) |

There is **no in-repo engine, runtime, corpus, bar, or CLI source**. `make deploy-coverage`
asserts that shape (`src/` is absent); `dotfiles/config/` is absent since R-07 (the btop
active-theme is host state in the install spine).

## Docs map

- **Live:** [`ARCHITECTURE.md`](ARCHITECTURE.md), [`AGENTS.md`](AGENTS.md),
  [`docs/WORKSPACE.md`](docs/WORKSPACE.md), `docs/02-config-in-spine-pattern.md`.
- **Historical (kept for provenance):** `docs/99-*`, `docs/100-*`, `docs/101-*`,
  `docs/investigation/`, `_bmad-output/`, `spikes/`, `prototypes/`,
  `openspec/changes/archive/`.

## Release / license

Composition releases are pinned by consumers; the authoritative record is `ARCHITECTURE.md`,
`CHANGELOG.md`, and the residual ledger under `_bmad-output/planning-artifacts/architecture/`.
MIT — see [`LICENSE`](LICENSE).
