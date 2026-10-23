# Tasks

## 1. Pin and manifest (≤1h)

- [ ] 1.1 Bump `dotfiles/provisioning/installer.pin` to `v0.1.7`.
  Verify: `cat dotfiles/provisioning/installer.pin` → `v0.1.7`.
- [ ] 1.2 Replace the runtime `source: src/runtime` entry with
  `{repo: https://github.com/RandomGenericUsername/dotfiles-runtime, tag: v0.1.0}`; update the
  header comments so no entry claims a local source.
  Verify: `rg -n 'source:' dotfiles/provisioning/cli-tools.yaml` → no matches.

## 2. Gates and shape (≤2h)

- [ ] 2.1 `scripts/deploy-coverage.py`: assert zero local sources; assert the runtime pinned shape
  and `src/runtime/` absence; require `src/` absent in `assert_composition_only`; remove the
  runtime pyproject pin block/constants.
  Verify: `make deploy-coverage` → exit 0.
- [ ] 2.2 `Makefile`, `.github/workflows/gates.yml`, `scripts/ci-gates-parity.py`: retire
  `contracts-check`, `runtime-architecture`, `contract-pin-check`, the two CI jobs and the
  `contracts-check -> contracts` rename.
  Verify: `make ci-gates-parity` → `PASS …`; `rg -n 'contracts-check|runtime-architecture' Makefile .github/workflows/gates.yml` → no matches.
- [ ] 2.3 Delete `src/runtime/`, `contracts/`, `scripts/contract-pin-check.py`; remove the
  `.gitignore` runtime artifact entry.
  Verify: `test ! -e src && test ! -e contracts && test ! -e scripts/contract-pin-check.py` → exit 0.

## 3. Docs and specs (≤1h)

- [ ] 3.1 Update `AGENTS.md`, `README.md`, `ARCHITECTURE.md`, `docs/WORKSPACE.md`, `CHANGELOG.md`
  for the new boundary and pin set (engine `v0.1.7`, runtime `v0.1.0`).
  Verify: `rg -n 'src/runtime' AGENTS.md README.md ARCHITECTURE.md docs/WORKSPACE.md` → only
  historical/absent references, no "authored here" claim.
- [ ] 3.2 This change's deltas update the five affected specs; run the change validation.
  Verify: `openspec validate runtime-repo-consumption --strict` → exit 0.

## 4. Proof (≤2h)

- [ ] 4.1 `make gates-ci`, `make deploy-coverage`, `make ci-gates-parity`,
  `openspec validate runtime-repo-consumption --strict`.
  Verify: exit 0; record counts/results.
- [ ] 4.2 Engine seam: run the pinned engine's `manifests` command against
  `dotfiles/provisioning` from the repo root.
  Verify: `dotfiles-provision --manifests-dir … --composition-root . manifests` → 5 manifests.
- [ ] 4.3 Fresh-machine proof: `dev/vm` bootstrap + `verify`. On this host `incus` is absent, so
  record `Evidence: MISSING` and do not claim it; run it before release on a VM-capable host.
  Verify: `command -v incus`; `dev/vm-verify`.

## 5. Closeout (≤0.5h)

- [ ] 5.1 Commit the planning and implementation separately; merge only on green; archive this
  change.
  Verify: `openspec validate --all --strict` (change delta green; legacy 27 failures unchanged).
