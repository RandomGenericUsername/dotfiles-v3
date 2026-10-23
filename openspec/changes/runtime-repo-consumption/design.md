# Design — runtime repo consumption

## D1. The engine tag is the carrier

The role mirror and `verify` block live in the pinned engine, not in this repo. `v0.1.7` carries
the `{repo, tag}` entry for `dotfiles-runtime` and the checkout/pin/version assertions. The
composition's only lever is `installer.pin`; it must move to `v0.1.7` before the manifest entry
changes, or `deploy-coverage` would compare a new manifest against old role vars.

Evidence: `dotfiles-provision` `roles/cli_tools/vars/main.yml` and `roles/verify/{vars,tasks}/main.yml`
at `v0.1.7`; release assets exist.
Verify: `gh release view v0.1.7 -R RandomGenericUsername/dotfiles-provision --json assets`.

## D2. The runtime is one more pinned entry

The manifest becomes four `{name, repo, tag}` entries. The generic `cli_tools` pinned branch does
the clone/install; `verify` adds `dotfiles-runtime` to `verify_cli_tools` and asserts the
tag-bearing checkout, the `pinned` record and `dotfiles-runtime version` = `0.1.0`.

Evidence: `dotfiles/provisioning/cli-tools.yaml`; engine `roles/cli_tools/tasks/main.yml`.
Verify: `make deploy-coverage` → the runtime pinned-shape assertion passes.

## D3. Delete the tree and every orphan in the same change

`src/runtime/` is the last authored tree. Its deletion orphans:
- `contracts/` (only the runtime conformance tests read it; the runtime repo now owns the copy),
- `scripts/contract-pin-check.py` and the three runtime-only Makefile targets,
- the `contracts` and `runtime-architecture` CI jobs and the `contracts-check -> contracts`
  rename in `ci-gates-parity`,
- the `.gitignore` entry for the runtime's determinism artifact,
- the `src/` allowlist and the "one local source" carve-out in `deploy-coverage`.

All of these land in the same commit; leaving any one behind is a stale reference, not a
convenience.

Evidence: `ARCHITECTURE.md` §9/§10 discipline; `deploy-coverage` `assert_composition_only`.
Verify: `test ! -e src && test ! -e contracts && test ! -e scripts/contract-pin-check.py`.

## D4. The composition runs shape, not the runtime's tests

`contracts-check` and `runtime-architecture` ran `uv run --directory src/runtime pytest …`. After
deletion there is nothing to run. The runtime repo's own `make gates` (test, lint, contracts-check,
hermetic, lock-check, docs-check) and its CI own those tests. The composition still proves the
runtime by **execution**: `deploy-coverage` asserts the pin, `verify` asserts the installed tool,
and `runtime_seed` actually invokes `wallpaper set` during a provision.

Evidence: `dotfiles-runtime` `Makefile` / `.github/workflows/gates.yml`.
Verify: `make -C ~/Development/dotfiles/dotfiles-runtime gates`.

## D5. Proof boundary

`make deploy-coverage` and `make gates-ci` are the local executable proof. A real
bootstrap/verify needs a disposable VM; this host has no `incus`, so that proof is recorded as
`Evidence: MISSING — run dev/vm` rather than claimed. The engine's own `v0.1.7` CI and its verify
fixture are green, so the remaining risk is host-level, not shape-level.

Evidence: `command -v incus` → no output.
Verify: `command -v incus`; after a VM run, `dev/vm-verify`.

## Verification plan

| Claim | Command | Expected |
| --- | --- | --- |
| Pin bump | `cat dotfiles/provisioning/installer.pin` | `v0.1.7` |
| All entries pinned | `rg -n 'source:' dotfiles/provisioning/cli-tools.yaml` | exit 1, no matches |
| Runtime pinned shape | `make deploy-coverage` | exit 0; runtime checkout/pin asserted |
| Composition-only | `test ! -e src && test ! -e contracts` | exit 0 |
| Gates | `make gates-ci` | exit 0 |
| Parity | `make ci-gates-parity` | `PASS …` |
| Engine seam | `dotfiles-provision --manifests-dir dotfiles/provisioning --composition-root . manifests` | exit 0, 5 manifests |
| VM proof | `dev/vm-*` | `Evidence: MISSING` on this host (no incus) |
