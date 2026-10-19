# cli-tools-repos

## Why

Six packages — `cli-output`, `config-assembler-engine`, `oci-runtime`,
`icon-templates-renderer` (`itr`), `wallpaper-effects-generator` (`weg`) and
`color-scheme-generator` (`csg`) — live inside `dotfiles-v3`, but nothing about
them is addressable as a product:

- **They are bound by relative filesystem paths.** Every consumer declares a bare
  dependency and then re-points it with `[tool.uv.sources] … path = …,
  editable = true` (`src/cli-tools/color-scheme-generator/pyproject.toml:39-42`;
  `src/runtime/pyproject.toml:24-25`). The committed locks freeze the same
  relative edit (`uv.lock:26,93,233`), and an installed tool's `.pth` files and
  `direct_url.json` point at the checkout (S2 §2.3). Moving or deleting the
  checkout breaks every install.
- **The container build model is a monorepo assumption.** `oci_runtime`'s
  `_REPO_MARKER_DIRS` requires a root containing both `src/cli-tools` and
  `src/shared` (`src/shared/oci-runtime/src/oci_runtime/source_locator.py:37-39`).
  An external checkout is rejected with `SourceRootNotFoundError` (S2 §2.3), so
  a post-split tree cannot build an image at all. Both Dockerfiles `COPY`
  repo-relative `src/cli-tools/*` and `src/shared/*` paths (S4 §2.5).
- **195 test modules are ungated.** `git ls-files 'src/cli-tools/*'
  'src/shared/*' | grep -E '/tests/.*test_[^/]*\.py$' | wc -l` → `195`
  (csg 49, weg 30, itr 32, cli-output 8, config-assembler-engine 16,
  oci-runtime 60). `Makefile` has no reference to any of them and `make
  gates-ci` runs five gates, none of which executes these suites (S4 §1.1; AD-14).
- **The invocation contract is duplicated literals.** Each runtime adapter's
  tests assert its own argv, env keys, artifact names and exit codes (S1 §6.1).
  Drift between the runtime and an installed CLI is therefore invisible until a
  real subprocess fails.

The split is a supply-chain change, not a rewrite: the runtime already couples to
the CLIs only through `subprocess.run`, exit status, artifact filenames and
hashes (S1 §0 facts 1-7). The `src/gui-tools` retirement already proved the
pinned-unit, destructive-last ritual and its absence guard (S4 §5; AD-13).

## What Changes

- **Six independent public repos**, owned by `RandomGenericUsername`, one package
  each: `cli-output v0.1.0`, `config-assembler-engine v0.1.0`,
  `oci-runtime v0.5.0`, `itr v0.1.0`, `weg v0.1.0`, `csg v0.1.0`. Each is
  mu-strict from its first commit (AD-12) and releases by immutable annotated
  tag (AD-9). "Public" is proven, not assumed: birth gate 0.5 reads the GitHub
  visibility and anonymously resolves the released tag (no credential helper, no
  terminal prompt) for every repo, because provisioning clones the pin without
  credentials (see `design.md` Risks — the `ags-apps` precedent).
- **`contracts` owns the runtime↔CLI invocation contract** (user decision
  2026-10-19). It gains `cli-invocation-contract` 0.1.0 — `invocation-contract.json`
  plus `cli_invocation_contract.testkit` — and its first tag `v0.1.0`. The
  runtime and all three CLIs pin the same tag. `cli-output` stays
  presentation-only (AD-4).
- **dotfiles-v3 consumes by git tag only.** Every sibling edge becomes
  `{ git = "…/<repo>", tag = "vX.Y.Z" }`; `uv.lock` records the resolved commit.
  No `path =`, no `editable = true`, no submodule, no cross-repo workspace
  (AD-3). One `contracts` tag is shared by the runtime and the three CLIs (AD-4).
- **Provisioning addresses tools by `{name, repo, tag}`.** `dotfiles/provisioning/cli-tools.yaml`
  is the single source of truth; the role shallow-clones `repo@tag` into
  `<install>/cli-tools/<name>/<tag>/`, removes `.git`, records `pinned`, and
  installs from that checkout (PEP 610 records the tag-bearing path, and the
  checkout HEAD equals the remote tag's commit). Asset steps read the same
  checkout. Images are built and verified at the tag-qualified `image_tag`, never
  `latest` (AD-7, AD-10). After the last CLI slice no extracted entry carries
  `source:`; `dotfiles-runtime → src/runtime` remains the only allowed in-repo
  source (OPEN-7).
- **The build-context cutover happens in the `oci-runtime` slice.**
  `resolve_build_context` replaces the monorepo marker
  (`pyproject.toml` + `src/<import_name>`); both container CLIs rewrite their
  Dockerfiles and build verbs in that slice, because deleting `src/shared/`
  breaks every Dockerfile that still `COPY`s it (AD-5, AD-6).
- **Hermetic tests land before the first extraction (S0b).** An autouse
  `HOME`/XDG/`chdir` fixture plus a canary per package, the two known
  host-dependent tests fixed in the tests, and a scrubbed `make hermetic`
  (AD-8).
- **Tests move with their code.** The 195 test modules run in their new repo's
  gates and CI. `dotfiles-v3` runs none of them and asserts the trees are gone
  (AD-14).
- **Destructive-last deletion, one target at a time.** Each slice merges only
  after the pinned replacement is proven by execution; then the in-tree copy
  and every reference it orphaned are deleted in the same slice. After S6,
  `src/cli-tools/` and `src/shared/` do not exist and `deploy-coverage` asserts
  it (AD-11, AD-13, AD-15).

## Capabilities

### New Capabilities

- `cli-repo-boundaries`: one package per repo, repo root = package root, a
  one-way acyclic dependency direction, and `dotfiles-v3` as a pure consumer.
- `cli-pin-consumption`: consumption by immutable git tag only, one `contracts`
  tag per consumer generation, and pins proven by execution rather than by a
  range or a moving branch.
- `cli-provisioning-addressing`: the `{name, repo, tag}` manifest as the single
  source of truth, tag-qualified image tags, role/verify/manifest parity, and
  the positive-shape + retired-tree assertions in `deploy-coverage`.
- `cli-invocation-contract`: the runtime↔CLI invocation contract as versioned
  data plus a conformance kit in `contracts`, executed by every consumer and CLI.
- `cli-repo-birth`: a mu-strict birth checklist, fresh-clone verbs and CI, so a
  new repo is a valid extraction target from its first commit.
- `cli-tree-deletion`: deletion only after proof, the deletion's full reference
  blast radius, and an absence guard that survives the retired tree.

### Modified Capabilities

None. Existing per-package specs (`cli-output`, `oci-*`, `csg-*`, `weg-*`,
`itr-*`, `interface-contract-test`, `container-adapter-env-contract`) move with
their code per AD-15; this change adds the cross-repo contracts that did not
exist before, rather than rewriting those specs in place.

## Non-goals

- **`dotfiles-runtime` stays in `dotfiles-v3`** (OPEN-7). It is not extracted, its
  install path and systemd units are unchanged, and the runtime keeps its
  host role while the contract and CLI split settle.
- **No PyPI and no private index** (OPEN-3). Git tags plus GitHub Release
  artifacts are the only distribution channel; a dependency on a sibling repo is
  always a git source at a tag.
- **No container registry initially** (OPEN-2). Images build locally at provision
  time from the pinned checkout; digest-pinned registry publication is deferred.
- **No history rewrite.** Per-package history is preserved with `git subtree
  split`, not `filter-repo` (OPEN-8).
- **No `itr` container mode.** It has none today and none is planned.
- **No migration of historical artifacts.** `openspec/changes/archive/**` and
  `_bmad-output/` stay as immutable history and are not rewritten (AD-15).
- **No runtime behavior change.** The same argv, env allowlist, artifact names,
  hashes and error mapping remain; this change moves distribution and addressing.

## Impact

- **Runtime (`src/runtime`)**: `pyproject.toml`/`uv.lock` re-point `cli-output`
  and `cli_invocation_contract` at tags; adapter tests assert through the
  contract testkit; the dev-only `src/cli-tools/...` input fallbacks in
  `application/derive.py:158-203` are deleted in the slice that deletes the
  tree. Runtime behavior is unchanged (same argv/env/artifacts).
- **Provisioning (`src/provisioning`)**: `roles/cli_tools`, `roles/assets`,
  `roles/settings` (tag-qualified `image_tag`), `roles/verify` (pin assertions),
  the manifest schema (`yaml_manifest_reader.py`), and their tests. Runtime
  daemon/clipboard install paths are unchanged because `dotfiles-runtime` stays.
- **Gates**: `GATES` stays the same five targets. `deploy-coverage` grows the
  pin-shape, parity and absence assertions; no new gate is added and
  `ci-gates-parity` stays green. The 195 moved suites are gated in their own repos.
- **Deletion**: `src/shared/cli-output`, `src/shared/config-assembler-engine`,
  `src/shared/oci-runtime` and then `src/cli-tools/{icon-templates-renderer,
  wallpaper-effects-generator,color-scheme-generator}` plus the nested
  `src/cli-tools/openspec/`; finally the empty `src/cli-tools/` and `src/shared/`.
- **Docs and specs**: live specs and docs that name the six paths are updated or
  moved; `openspec/changes/archive/**` stays as immutable history (AD-15).
