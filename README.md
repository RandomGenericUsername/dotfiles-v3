# dotfiles-v3 — the composition repo

`dotfiles-v3` is the **composition** of the dotfiles system. It owns the declarative manifests,
the Python runtime, the composition gates, and the fresh-machine entry point. It does **not** own
the installer engine, the asset corpus, the AGS unit, or the CLI sources — those are pinned
siblings (see [`docs/WORKSPACE.md`](docs/WORKSPACE.md)).

## Workspace

The sibling repos are expected under `~/Development/dotfiles/`:

```text
dotfiles-v3          this repo: manifests, runtime, gates, bootstrap
dotfiles-provision   installer engine: Ansible tree + Python orchestrator
dotfiles-assets      pinned corpus: icons, templates, configs, content, desktop
ags-apps             pinned AGS unit: bar + the sibling apps
ags-platform         pinned AGS platform: ports, adapters, event client
contracts            event contract + schemas
cli-output           shared CLI rendering package
color-scheme-generator / wallpaper-effects-generator / icon-templates-renderer
config-assembler-engine / oci-runtime
```

The canonical ownership/pin map is [`docs/WORKSPACE.md`](docs/WORKSPACE.md); the executable pin
set is `ARCHITECTURE.md` §4.1 and `make deploy-coverage`.

## Quick start

```bash
./bootstrap.sh                 # fresh machine: uv → engine → collections → bootstrap → verify
make bootstrap ARGS="--ask-become-pass"   # same, through make
make provision ARGS="verify --expected-engine-tag v0.1.5"  # installed console
make gates-ci                  # six composition gates
make deploy-coverage           # pin-set + composition-only shape
openspec validate --all        # spec/change baseline
```

`bootstrap.sh` reads `dotfiles/provisioning/installer.pin` (currently `v0.1.5`), installs the
engine from `git+…@tag`, fetches the pinned assets corpus (`v0.5.0`), and runs the aggregate.
The engine is never edited here.

## What lives here

| Path | What it is |
| --- | --- |
| `dotfiles/provisioning/` | Manifests (`assets.yaml`, `cli-tools.yaml`, `config-copies.yaml`, `filesystem.yaml`, `packages.yaml`) + `installer.pin` |
| `src/runtime/` | `dotfiles-runtime`: hexagon, daemon, clipboard watcher, cache/state |
| `scripts/` | Composition gates (`deploy-coverage.py`, `ci-gates-parity.py`, `contract-pin-check.py`, `ansible-embedded-template-lint.py`, `engine_checkout.py`) |
| `contracts/` | Vendored event contract + schemas (conformance copies) |
| `dev/` | Local-only incus VM harness |
| `docs/` | Live design/runbook docs; historical documents are labelled |
| `openspec/` | Specs + active changes; `openspec/changes/archive/` is immutable history |
| `_bmad-output/`, `spikes/`, `prototypes/` | Historical planning/prototype record (not runtime input) |

There is **no in-repo engine, corpus, bar, or CLI source**. `make deploy-coverage` asserts that
shape; `dotfiles/config/` is absent since R-07 (the btop active-theme is host state in the
install spine).

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
