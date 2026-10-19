# Design — cli-tools-repos

## Context

See `proposal.md` — Why. The design is the migration mechanics for the spine at
`_bmad-output/planning-artifacts/architecture/architecture-cli-repos-2026-10-19/ARCHITECTURE-SPINE.md`
(AD-1…AD-16), with the executable step list in its `SLICES.md` companion and the
evidence pointers in `EVIDENCE-INDEX.md`.

Two facts shape every choice below:

1. The runtime does not import a CLI package. Coupling is `subprocess.run` plus
   exit status, artifact filenames and hashes (S1 §0 facts 1-7, §2.1-2.2), so the
   split changes distribution and addressing, not runtime internals.
2. The only runtime dependency on a checkout is the container build-context
   locator (S3 closing section); settings, templates, effects and the backend
   catalog resolve through CLI/env/cwd/XDG/packaged defaults.

`contracts` is an existing repo at `/home/inumaki/Development/contracts` with its
own `AGENTS.md`, ticket discipline and gates. It has no `pyproject.toml` and zero
tags today, so S0a creates both the package and the first tag.

## Goals / Non-Goals

**Goals:**

- Six packages with one owner, one release ritual and one version per repo.
- Every cross-repo edge is an immutable tag, resolvable without this checkout.
- The runtime↔CLI invocation contract has exactly one source and one conformance
  kit, executed by the runtime and all three CLIs.
- Provisioning can install, verify and build a tool from `{name, repo, tag}`
  alone, and a wrong tag fails a gate rather than passing `command -v`.
- The migration is reversible per target (pin bump + revert of the deletion
  commit) and leaves no dead reference after deletion.

**Non-Goals:**

- Extracting `dotfiles-runtime` (OPEN-7) or changing runtime behavior.
- Publishing to PyPI, a private index, or a container registry (OPEN-2/OPEN-3).
- Preserving the monorepo layout inside a new repo (AD-2).
- Migrating historical archives, `_bmad-output/`, or old OpenSpec changes
  (AD-15).
- Making `itr` container-capable; it has no container mode.

## Decisions

### D1 — One package per repo; repo root is the package root (AD-1, AD-2)

Each repo has exactly one root `pyproject.toml`, one import package at
`src/<import_name>/`, tests at `tests/`, and no nested project root or second
`openspec/` inside `src/`. Container assets live at
`src/<import_name>/adapters/docker/` for csg and weg only.

*Alternative rejected:* a `src/cli-tools` + `src/shared` layout inside each new
repo. It would reproduce the assumption the split exists to remove, and AD-5's
marker change would still be needed.

### D2 — The invocation contract lives in `contracts`, not `cli-output` (AD-4)

`contracts` gains distribution `cli-invocation-contract`, import package
`cli_invocation_contract`, data `invocation-contract.json` (one entry per CLI:
argv template, required env keys, required artifact names/suffixes, exit-code
semantics, default timeout) and `cli_invocation_contract.testkit` with exactly
two assertions: a consumer's recorded invocation matches the record; a CLI
accepts the recorded invocation and writes the required artifacts (runner
injected). The loader is stdlib-only (`json` + dataclasses).

*Alternative rejected:* host the contract in `cli-output`. That gives a
presentation package a charter it was not designed for and couples every CLI's
rendering dependency to protocol data. *Alternative rejected:* keep duplicated
literals per repo; S1 §6.1 proves those already drift silently.

**Decision owner:** user, 2026-10-19, recorded in the spine's Resolved Decisions.
Consequence: `contracts` gains its first `pyproject.toml` and its first tag in
S0a; `cli-output`'s charter is unchanged.

### D3 — Consumption is by immutable tag; the tag chain is a slice invariant (AD-3, AD-9)

A sibling dependency is `{ git = "https://…/<repo>", tag = "vX.Y.Z" }` plus a
compatibility range in `[project].dependencies`, with a committed `uv.lock` that
records the resolved commit. No `path =`, `editable = true`, submodule or
cross-repo workspace. Tags are annotated, monotonic and never moved; a fix is a
new tag. Release ritual: gates green on the ticket branch → version bumped in
`pyproject.toml` + `CHANGELOG.md` → annotated tag → CI attaches sdist/wheel to the
GitHub Release → consumer pin bump in its own commit.

First tags and the chain (no slice consumes a tag an earlier slice did not
produce):

| Slice | Produces | Consumes |
| --- | --- | --- |
| S0a (`contracts`) | `contracts v0.1.0` → `cli-invocation-contract` 0.1.0 | — |
| S0b (`dotfiles-v3`) | none | `contracts v0.1.0` |
| S1 | `cli-output v0.1.0` | `contracts v0.1.0` |
| S2 | `config-assembler-engine v0.1.0` | `contracts v0.1.0` |
| S3 | `oci-runtime v0.5.0` | `contracts v0.1.0` |
| S4 | `itr v0.1.0` | `contracts v0.1.0`, `cli-output v0.1.0`, `cae v0.1.0` |
| S5 | `weg v0.1.0` | all of the above |
| S6 | `csg v0.1.0` | all of the above |

`oci-runtime` starts at `v0.5.0` (imported code is 0.4.0) because the
build-context API ships in its first tag; versions never move backwards. The four
consumers of the contract — runtime, csg, weg, itr — pin the **same** `contracts`
tag, not a range; changing the contract is a new tag re-pinned in the same slice
(AD-4).

### D4 — Build-context cutover belongs to the `oci-runtime` slice (AD-5, AD-6, AD-7)

`oci-runtime` is the last shared lib and S3 deletes `src/shared/`, which breaks
every Dockerfile that still `COPY`s it. The cutover is therefore part of S3, not a
later cleanup:

- New API `resolve_build_context(*, package, override=None, env_var=None, env=None)`
  with marker `pyproject.toml` **and** `src/<import_name>`; the same priority
  order override → env → PEP 610 → package walk.
- `resolve_source_root` stays exported as a deprecated alias for one minor and
  accepts either marker set, so in-tree consumers keep working through the
  migration (AD-16).
- The CLI verb gains `--context`; `--source-root` stays as an alias. It also
  gains `--image-tag` (default `v` + the checkout's `pyproject.toml` version),
  validated against that version, so a pin that no tag produced fails closed
  instead of tagging an image `verify` will reject.
- Both Dockerfiles copy only in-repo paths (`pyproject.toml`, `uv.lock`, `src/`)
  and the build stage carries `uv` at the pinned version plus `git` and CA
  certificates, because pinned git dependencies are fetched at build time. An
  unreachable pin fails the build closed.
- The CLI repo owns Dockerfiles and the build verb; provisioning owns the pin,
  the clone at that tag and the post-build image-existence check. Provisioning
  never writes or patches a Dockerfile.
- While the CLI trees are still in-tree, the provisioning build task passes
  `<dotfiles>/src/cli-tools/<pkg>` as `--context`; the S5/S6 slices switch it to
  the pinned checkout.

*Alternative rejected:* cut over in S5/S6. It would leave the tree in an invalid
half-state — `src/shared/` deleted while the Dockerfiles still need it — which
S3's rollback rule explicitly forbids.

### D5 — Provisioning addresses `{name, repo, tag}`; images carry the tag (AD-10, AD-11)

`dotfiles/provisioning/cli-tools.yaml` is the single source of truth. For each
extracted CLI: shallow-clone `repo@tag` with `depth: 1`, `single_branch: true`,
retries; install `repo/dest` into `<install>/cli-tools/<name>/<tag>/`; remove
`.git`; write a one-line `pinned` record; install the tool **from that checkout**
(not from the git URL) with `UV_TOOL_BIN_DIR` pinned, so PEP 610 records a
tag-bearing path. Asset entries that read a package tree — notably
`csg-templates` — read the same checkout path and declare a dependency on the
`fetch` task list, so they cannot run before the tree exists.

`roles/verify` carries independent literal pins mirroring the role and the
manifest, and asserts by execution: the checkout HEAD equals the remote tag's
commit, the checkout path contains the tag, the installed package version equals
the tag with the leading `v` stripped, each CLI's `--version` contract token
equals the `contracts` tag `dotfiles-v3` pins, and the expected image exists at
the tag-qualified image tag. `deploy-coverage` asserts the repo-side shape
(entries have `repo` + `tag`; role/verify/manifest agree; no `path =`/`editable =
true`; each deleted tree absent at its own slice; no `src/cli-tools` asset source;
no runtime fallback), then the terminal catch-all for both retired trees after
S6.

**Scope note (resolved by OPEN-7).** The manifest's fourth entry,
`dotfiles-runtime → src/runtime` (S2 §1.1), is not one of the six and keeps its
local `source:` under OPEN-7. After the last CLI slice the rule is: **no
extracted-package `source:` path exists**, and `dotfiles-runtime -> src/runtime`
is the only allowed in-repo source. `deploy-coverage` asserts exactly that
(`rg -n 'source:' dotfiles/provisioning/cli-tools.yaml` → one match), rather
than a no-local-source manifest that would contradict OPEN-7.

### D6 — Test hermeticity is fixed before the first extraction (AD-8)

Every extracted suite must pass with `HOME` and all four XDG variables pointed at
empty temp dirs and an unrelated cwd. Enforcement is an autouse fixture in each
repo's `tests/conftest.py` (set five variables, `chdir` to a temp dir) plus a
canary test asserting the fixture is active, plus a scrubbed CI invocation and a
developer `make hermetic`.

The two observed failures — csg
`test_resolve_falls_back_to_package_defaults`, itr `test_resolves_bundled_default`
— resolve the provisioned spine and pass with an empty `XDG_CONFIG_HOME` (S3
§5.1). The fix goes in the tests, never in the resolvers: XDG-over-packaged-default
is the intended production precedence (S3 §1.4, §5.4).

*Alternative rejected:* scrub the environment only in CI. A developer's spine
would still make the suite red or falsely green locally.

### D7 — Destructive-last, per target, with an absence guard (AD-11, AD-13, AD-14, AD-15)

Each target slice executes the same loop and does not start the next target until
its merge:

1. Create the repo from the birth checklist.
2. Import the package at its current path as the repo root, preserving history
   with `git subtree split -P <path>`.
3. Repoint in-repo dependencies to tags and keep the `contracts` pin; regenerate
   locks.
4. Tag and let CI release.
5. Rewire `dotfiles-v3` consumption to the tag.
6. Prove by execution: install, run, and for container CLIs build an image.
7. Delete the in-tree copy in the same slice, plus every reference the deletion
   orphaned (runtime fallbacks, asset/manifest sources, `.gitignore`, docs prose).
8. Merge.

The deletion is not complete until the absence is executable: each slice adds
its own tree to `deploy-coverage`'s absence assertion in the deletion commit
(`test ! -e` alone is not a gate), and the terminal slice adds the catch-all for
`src/cli-tools/` and `src/shared/`, mirroring the `src/gui-tools` precedent
(S4 §5.2-5.4: one commit deletes the tree, retires the orphaned references and
adds the guard; the merge adds nothing beyond that payload). No dotfiles gate may
point at a moved suite; the retired-gate rule applies.
`openspec/changes/archive/**` stays as immutable history, and package specs move
with their code (AD-15).

*Alternative rejected:* delete first and re-add if something breaks. Rollback
would then be a restore from history plus a pin rollback, and every intermediate
commit would be untrustworthy.

### D8 — Repo birth is mu-strict from the first commit (AD-12)

Harness files are copied from `mu` (same `skills-lock.json` hashes, same
`scripts/worktree-guard.sh`), not re-authored. The birth checklist in the spine
is the gate: `AGENTS.md` evidence contract, `CLAUDE.md` symlink, `tickets/`
(INDEX, LIFECYCLE, templates, fixtures), executable worktree guard, `.agents/skills`
+ `skills-lock.json`, `_bmad/`, `openspec/`, root `pyproject.toml` + committed
`uv.lock`, `Makefile` with `help/sync/test/lint/format/gates/build/install`
anchored on `$(CURDIR)`, hermetic fixture + canary, `.github/workflows/gates.yml`
with one job per `make gates` target and `ci-gates-parity`, `README.md` +
`CHANGELOG.md` + `LICENSE` (MIT), and `docker/` only where a container mode exists.

*Alternative rejected:* "harness later". The per-app split guide names that as the
reason earlier splits were deferred; a repo without gates is not an extraction
target.

## Risks / Trade-offs

- **Git-tag-only distribution needs network at build time.** → The build stage
  installs `git` + CA certificates; an unreachable pin fails closed instead of
  resolving something newer. Accepted because PyPI/registry is a non-goal.
- **A wrong-tag install can still look healthy to `command -v`.** → `verify`
  asserts the checkout tag, installed version, contract token and image tag by
  execution (D5); `deploy-coverage` asserts manifest/role/verify parity.
- **The S3 cutover is the highest-blast-radius step.** → It has its own gates:
  new locator acceptance, deprecated alias import, no sibling `COPY`, both images
  build from a single package dir, real container generation, then deletion.
  Rollback reverts pin + Dockerfile/verb + deletion together; a half-state is
  explicitly invalid.
- **A provisioned spine can mask test failures.** → S0b's fixture + canary is an
  entry criterion for every extraction, not a follow-up.
- **`contracts v0.1.0` is new work in another repo.** → S0a runs in a worktree of
  that repo under its own `AGENTS.md` and ticket/OpenSpec routing; no dotfiles
  file changes in that slice, so the two repos' planning commits stay separate.
- **Manifest scope for `dotfiles-runtime`.** → D5 records the interpretation; see
  Open Questions.
- **One copied S1 gate was broader than its slice.** `SLICES.md` S1's
  `rg … 'editable = true'` pattern also matches the still-in-tree
  `config-assembler-engine` and `oci-runtime` path pins, which S2/S3 migrate
  later. Task 3.3 scopes the gate to
  `rg -n 'cli-output = \{ path = "\.\./shared/cli-output"'` instead of copying
  the broad pattern: CAE and OCI stay editable until 4.2 and 5.2 respectively,
  and the unscoped catch-all is a post-S3 assertion (5.5) owned by
  `deploy-coverage`. Do not "fix" this by migrating those libs early.

## Migration Plan

The slice order is fixed by `SLICES.md`, and each slice's acceptance gates are
the executable proof:

1. **S0a** — create `cli-invocation-contract` in `contracts`, tag `v0.1.0`.
2. **S0b** — hermetic fixtures + canary, two test fixes, `--version`, pin
   `contracts v0.1.0` in runtime and the three in-tree CLIs, delete the two
   boundary specs now owned by `contracts`, add `make hermetic`.
3. **S1** — `cli-output` → repo, tag `v0.1.0`, rewire runtime/provisioning/CLIs,
   delete `src/shared/cli-output`.
4. **S2** — `config-assembler-engine` → repo, tag `v0.1.0`, rewire the three
   CLIs, delete the tree.
5. **S3** — `oci-runtime` → repo with `resolve_build_context`, tag `v0.5.0`,
   rewrite Dockerfiles/build verbs, delete `src/shared/`.
6. **S4** — `itr` → repo, tag `v0.1.0`, first `{name, repo, tag}` manifest entry,
   delete the tree and runtime fallbacks.
7. **S5** — `weg` → repo, tag `v0.1.0`, checkout install + `--context` build +
   tag-qualified `image_tag`, delete the tree.
8. **S6** — `csg` → repo, tag `v0.1.0`, move the nested OpenSpec root into the
   csg archive, re-address the templates asset to the checkout, delete
   `src/cli-tools/`; terminal absence guard.

Rollback for every slice is a pin bump to the previous tag (or none) plus
`git revert` of the deletion commit. A published tag is never deleted or moved,
and a deleted tree is recoverable from the merge base.

## Open Questions

- **Which concrete image names the tag-qualified check matches.** The slices
  specify `grep -E 'weg.*:v0\.1\.0$'` / `'(csg|color-scheme).*:v0\.1\.0$'`; the
  exact repository names follow the existing backends and are only pinned when
  S5/S6 build them. No spec behavior depends on the name pattern beyond
  "tag-qualified, not `latest`".
- **Which concrete image names the tag-qualified check matches.** The slices
  specify `grep -E 'weg.*:v0\.1\.0$'` / `'(csg|color-scheme).*:v0\.1\.0$'`; the
  exact repository names follow the existing backends and are only pinned when
  S5/S6 build them. No spec behavior depends on the name pattern beyond
  "tag-qualified, not `latest`".
