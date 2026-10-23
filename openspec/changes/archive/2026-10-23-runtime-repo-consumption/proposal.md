# runtime-repo-consumption

## Why

`dotfiles-runtime` is now its own repo (`RandomGenericUsername/dotfiles-runtime`), tagged `v0.1.0`
with its 148-commit history. The composition still authors it at `src/runtime/`, carries its
vendored event-contract copy under `contracts/`, and runs its two pytest subsets as composition
gates. That is the last authored tree in a repo whose spec says "composition-only",
`make deploy-coverage` still carves it out as "exactly one local `source:`", and the engine's
`v0.1.7` release now consumes the runtime as a pinned CLI entry.

This change is the destructive-last slice: rewire the pin, prove the shape, then delete the
in-tree runtime and every reference it orphaned in the same change.

Evidence: the runtime repo is public and green at `v0.1.0`
(`gh release view v0.1.0 -R RandomGenericUsername/dotfiles-runtime`); the engine consumes it as
`{repo, tag}` at `v0.1.7` (`dotfiles-provision` `roles/cli_tools/vars/main.yml`).
Verify: `git ls-remote https://github.com/RandomGenericUsername/dotfiles-runtime 'refs/tags/v0.1.0'`
→ one line; `gh release view v0.1.7 -R RandomGenericUsername/dotfiles-provision --json assets`.

## What Changes

- `dotfiles/provisioning/installer.pin`: `v0.1.6` → `v0.1.7`.
- `dotfiles/provisioning/cli-tools.yaml`: `dotfiles-runtime` becomes
  `{name: dotfiles-runtime, repo: https://github.com/RandomGenericUsername/dotfiles-runtime,
  tag: v0.1.0}`; no entry carries `source`.
- `scripts/deploy-coverage.py`: the manifest has **zero** local sources; the runtime is asserted
  with the generic pinned-CLI shape (repo+tag, tag-bearing checkout, no `src/runtime/`); the
  composition-only terminal allowlist requires `src/` to be absent; the runtime pyproject pin
  block is removed (the runtime owns its pins and `uv.lock`).
- `Makefile` / `.github/workflows/gates.yml` / `scripts/ci-gates-parity.py`: retire
  `contracts-check`, `runtime-architecture` and `contract-pin-check`. The runtime repo runs those
  gates; the composition keeps `ansible-embedded-template-lint`, `deploy-coverage`,
  `ci-gates-parity` and `per-app-drift-symbol-suites`.
- Delete `src/runtime/`, the composition's `contracts/` conformance copy and
  `scripts/contract-pin-check.py`.
- Update `AGENTS.md`, `README.md`, `ARCHITECTURE.md`, `docs/WORKSPACE.md`, `CHANGELOG.md` and the
  affected OpenSpec specs to state the new boundary: the composition authors manifests and gates
  only; the runtime is a pinned sibling.
- Prove: `make deploy-coverage`, `make gates-ci`, `make ci-gates-parity`, and the engine's
  `manifests` read-only seam against the new manifest. A fresh-machine bootstrap/verify is
  `Evidence: MISSING` here because incus is not available on this host; it must run before release.

## Capabilities

- **Modified Capabilities:** `composition-closeout`, `cli-provisioning-addressing`,
  `assets-repo-boundaries`, `cli-invocation-contract`, `cli-repo-boundaries`.
- **New Capabilities:** none (the runtime repo's own `repo-harness` already covers its harness).

## Non-goals

- **Not** changing the runtime repo, its `v0.1.0` tag, or its package.
- **Not** changing `csg`/`weg`/`itr` pins or images.
- **Not** renaming the runtime's import package (`runtime`).
- **Not** fixing the pre-existing 27 `openspec validate --all` failures; this change validates its
  own delta and leaves the legacy set unchanged.

## Impact

- Modified: `dotfiles/provisioning/{installer.pin,cli-tools.yaml}`, `scripts/deploy-coverage.py`,
  `Makefile`, `.github/workflows/gates.yml`, `scripts/ci-gates-parity.py`, `.gitignore`,
  `AGENTS.md`, `README.md`, `ARCHITECTURE.md`, `docs/WORKSPACE.md`, `CHANGELOG.md`.
- Deleted: `src/runtime/`, `contracts/`, `scripts/contract-pin-check.py`.
- Unchanged: every provisioning manifest except `cli-tools.yaml`, every role in the pinned engine
  (the role/tag/verify change shipped in `dotfiles-provision` `v0.1.7`), and every runtime command.
