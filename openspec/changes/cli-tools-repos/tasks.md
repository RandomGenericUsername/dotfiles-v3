# Tasks — cli-tools-repos

Execution order is fixed: S0a → S0b → S1 → S2 → S3 → S4 → S5 → S6. No slice
starts before its predecessor is merged on `master`.

## Status

Last updated: 2026-10-21, after S4 merged to `master` at `6ad7117c` (S5 done
in its worktree).

| Slice | State | Evidence anchor |
| --- | --- | --- |
| S0a — `contracts` invocation contract + first tag | done | `contracts` tag `v0.1.0` → commit `48cf3cf` (tag object `6ea43dcb`); `uv run pytest -q` → 49 passed; `openspec validate … --strict` → valid; public repo + anonymous `ls-remote` proven |
| S0b — dotfiles prerequisites | done (merged to `master` at `56d7d85e`) | `make hermetic` → exit 0 (63 / 163 / 1095+2skip / 288 / 346 / 638); boundary specs deleted here and tracked in `contracts` `55ad61b`; ff-merge `f4f16f11..56d7d85e`, `make gates-ci` exit 0 at HEAD pre-merge; see the S0b verification log below |
| S1 — `cli-output` repo + `v0.1.0` | done (merged to `master` at `843b50d0`) | repo `v0.1.0` (tag object `91489b73`, peeled `ddae3727`) consumed by all five locks; scoped stale-path gate exit 1; tree deleted (25 files, 1330 lines); `deploy-coverage` guard + tests green; ff-merge `96c4a0f4..843b50d0`, `make hermetic` / `make gates-ci` / `make deploy-coverage` exit 0 at HEAD pre-merge; see the S1 verification log below |
| S2 — `config-assembler-engine` repo + `v0.1.0` | done in worktree (merge pending) | repo `v0.1.0` (tag object `5c5cc84e`, peeled `cad8a91c`) consumed by csg/weg/itr locks; scoped stale-path gate exit 1; tree deleted (66 files, 4769 lines); `deploy-coverage` guard + tests green; fresh-clone gate and `make hermetic` / `make gates-ci` / `make deploy-coverage` exit 0; see the S2 verification log below |
| S3 — `oci-runtime` repo + `v0.5.0` | done (merged to `master` at `c4056631`) | repo `v0.5.0` (peeled `b631dfa5`); tree deleted (184 files, 19 848 lines) with the empty `src/shared/`; `deploy-coverage` guard + `23 passed`; merged fast-forward `eb880c2f..c4056631` and pushed; see 5.6 Done |
| S4 — `icon-templates-renderer` repo + `v0.1.0` | done (merged to `master` at `6ad7117c`) | repo `v0.1.0` (tag object `09271f64`, peeled `92895a06`); pin commit `0bc85765`, retired-tree guard `0c33bdfc`; tree deleted (103 files, 8 918 lines); `make hermetic` / `make gates-ci` / `make deploy-coverage` exit 0 at HEAD pre-merge, itr tree `ABSENT`; merged `c4056631..6ad7117c`, pushed (`origin/master == 6ad7117c`); see 6.5 Done |
| S5 — `wallpaper-effects-generator` repo + `v0.1.0` | done (merged to `master` at `6e0633ba`) | repo `v0.1.0` (tag object `093d4051`, peeled `9672d89c`); tag is the image tag (`weg-podman:v0.1.0`, no `latest`); tree deleted (102 files, 12 380 lines); `make hermetic` / `make gates-ci` / `make deploy-coverage` exit 0; merged `6ad7117c..6e0633ba`, pushed; see the S5 verification log below |
| S6 — `color-scheme-generator` repo + `v0.1.0`, both trees deleted | done in worktree (merge pending) | repo `v0.1.0` (tag object `47afbbdf`, peeled `14f2faf5`); pinned checkout installs `csg 0.1.0 contract 0.1.0`; four images at `:v0.1.0`, no `latest`; assets read the checkout (12 templates, `IDENTICAL`); trees deleted (147 files, 18 577 lines); `make hermetic` / `make gates-ci` / `make deploy-coverage` exit 0; see the S6 verification log below |
| Post-migration verification | run in the S6 worktree (merge pending) | `deploy-coverage` reports the six pinned packages + one in-repo source; tag chain verified for all seven repos; the literal `src/cli-tools`/`src/shared` scan is NOT exit 1 (residue: the guard + its negative tests + `docs/investigation/**`); see §9 below |

S0a, S0b, S1, S2, S3, S4 and S5 are done and merged. S2's merge (4.4) landed as
the fast-forward `d1f92e6c..eb880c2f`; S3's merge (5.6) landed as
`eb880c2f..c4056631`; S4's merge (6.5) landed as `c4056631..6ad7117c`, pushed
(`git ls-remote origin refs/heads/master` → `6ad7117c`, exit 0); S5's merge
(7.6) landed as `6ad7117c..6e0633ba`, pushed (`origin/master == 6e0633ba`).
S6's implementation, proof and gate run are done in `.worktrees/clitools-s6` on
`ticket/clitools-s6-consume-csg-final` (base `6e0633ba`); its merge (8.8) is
deliberately NOT done by this slice's agent (STOP before merging), so
`master` still has the pre-S6 shape. The two S0a
lines carried into S0b as 2.7 (boundary-spec relocation) and 2.8 (missing
`CHANGELOG.md` + GitHub Release assets) are both closed: the specs are tracked in
`contracts` at `55ad61b` and gone from this repo, and `contracts` `v0.1.0` now
has a `CHANGELOG.md` entry and a Release with the wheel and sdist attached. S0b's
own merge (2.9) landed as the fast-forward `f4f16f11..56d7d85e`, pushed to
`origin/master` (`origin/master == 56d7d85e`).

### S0a verification log

Run in `/home/inumaki/Development/contracts` at `48cf3cf` (2026-10-19):

| Command | Observed |
| --- | --- |
| `gh api repos/RandomGenericUsername/contracts --jq .private` | `false`, exit 0 — public pin channel |
| `uv run pytest -q` | `49 passed`, exit 0 |
| `uv build` | `Successfully built` sdist + wheel, exit 0; `unzip -l dist/cli_invocation_contract-0.1.0-py3-none-any.whl` lists `cli_invocation_contract/invocation-contract.json` |
| `openspec validate cli-invocation-contract --strict` | `Change 'cli-invocation-contract' is valid`, exit 0 |
| `git ls-remote --tags --refs origin 'refs/tags/v0.1.0'` | exactly one line, `6ea43dcb…\trefs/tags/v0.1.0`, exit 0 |
| `git rev-parse 'v0.1.0^{}'` | `48cf3cfed4b192b241505789409c4f282921c896` (annotated tag → commit) |
| `GIT_TERMINAL_PROMPT=0 git -c credential.helper= ls-remote https://github.com/RandomGenericUsername/contracts 'refs/tags/v0.1.0'` | `6ea43dcb…\trefs/tags/v0.1.0`, exit 0 — anonymous, no credential helper |
| `gh run list --workflow=drift.yml --limit 3` | latest `contract-drift` run `success` on `v0.1.0` |
| `uv run python -c "…CONTRACT_VERSION, DATA_VERSION, load()…"` | `0.1.0 1` — `CONTRACT_VERSION = "0.1.0"`, `DATA_VERSION = 1` |
| `make contracts-drift && make check-symmetry` | exit 0, `[drift] symmetric: contract and generated/ agree` |

`48cf3cf` carries `pyproject.toml`, `src/cli_invocation_contract/{__init__,testkit}.py`,
`invocation-contract.json`, `CONTRACT.md`, five test files under `tests/`,
`uv.lock`, the Makefile verbs, the README/AGENTS charter update and the
`.github/workflows/drift.yml` uv step. Contract literals were cross-checked
against the runtime source — `csg_adapter.py:278-302,352-370`,
`weg_adapter.py:344-352`, `itr_adapter.py:406-422` — and match
`invocation-contract.json` (argv, the 8 csg artifacts, env keys, timeout).

Recorded deviation: `CONTRACT_VERSION` is the release semver string `"0.1.0"`
while `DATA_VERSION` is the JSON-shape integer `1` (not a second semver);
`contracts/openspec/changes/cli-invocation-contract/design.md` records why.

### S0b verification log

Run in the dotfiles worktree `ticket/clitools-s0b-pin-contract-and-hermetic` and
in `/home/inumaki/Development/contracts` (2026-10-19):

| Command | Observed |
| --- | --- |
| `git ls-files openspec/specs/{interface-contract-test,container-adapter-env-contract}` (here) | empty, exit 0 — both deleted in this slice |
| `git -C contracts ls-files openspec/specs/{interface-contract-test,container-adapter-env-contract}` | both `spec.md`, exit 0 (main `55ad61b`; HEAD `5e03075`) |
| `openspec validate --all` (contracts) | `10 passed, 0 failed`, exit 0 |
| `openspec validate --all` (here) | 100 passed, 27 failed, exit 1 — the failing set is byte-identical to the pre-deletion run (102 passed / the same 27 pre-existing delta-less legacy changes); neither boundary spec is referenced by a live change |
| `openspec validate cli-tools-repos --type change` | `Change 'cli-tools-repos' is valid`, exit 0 |
| `make hermetic` | exit 0 — six suites: 63 / 163 / 1095+2 skipped / 288 / 346 / 638 passed |
| `make gates-ci` | exit 0 — five gates (`contracts-check`, `ansible-embedded-template-lint`, `deploy-coverage`, `ci-gates-parity`, `per-app-drift-symbol-suites`); `ci-gates-parity: PASS`, `deploy-coverage: PASS` |
| `make deploy-coverage` | exit 0, `deploy-coverage: PASS -- …the external units are provisioned` |
| `env HOME=/tmp/opencode/fakehome XDG_CONFIG_HOME=/tmp/opencode/emptyxdg-csg uv run --directory src/cli-tools/color-scheme-generator pytest -q tests/unit/adapters/test_template_dir_resolver.py` | `4 passed`, exit 0 |
| itr equivalent (`tests/unit/adapters/test_assembled_config_resolver.py`, empty `XDG_CONFIG_HOME`) | `6 passed`, exit 0 |
| `for b in itr weg csg; do uv run --directory src/cli-tools/<pkg> "$b" --version; done` | three lines `0.1.0 contract 0.1.0`, exit 0. Note: the bare binaries on this host's `PATH` (`~/.local/bin/{csg,weg,itr}`) are a pre-S0b install and still reject `--version`; the gate is proven against the in-tree entry points |
| `rg -n 'cli-invocation-contract = .*contracts", tag = "v0\.1\.0"' src --glob 'pyproject.toml'` | 4 matches — runtime, itr, weg, csg |
| `rg -n 'def test_(csg\|weg\|itr)_(generate\|render)_env_override_writes_to_output_dir' src/runtime/tests` | no matches, exit 1 — the duplicated literal assertions are gone |
| `uv run --directory src/runtime pytest tests/unit/test_cli_invocation_contract.py tests/unit/test_csg_adapter.py tests/unit/test_weg_adapter.py tests/unit/test_itr_adapter.py -q` | `36 passed`, exit 0 |
| `uv run --directory src/runtime python -c "…CONTRACT_VERSION…"` | `0.1.0` |
| `gh release view v0.1.0 --repo RandomGenericUsername/contracts --json tagName,assets` | `tagName: v0.1.0` + `cli_invocation_contract-0.1.0-py3-none-any.whl` and `…tar.gz`, exit 0 |
| `test -s contracts/CHANGELOG.md && rg -n '0\.1\.0' contracts/CHANGELOG.md` | tracked at HEAD, `## [0.1.0] - 2026-10-19` at line 16 |

`make hermetic` is the gate even though the task writes it through an outer
`env` wrapper: the target scrubs `HOME`, the four XDG vars and the three
per-tool config vars itself (`Makefile:107-127`).

### S1 verification log

Run in the dotfiles worktree `.worktrees/clitools-s1` on
`ticket/clitools-s1-consume-cli-output` (base `96c4a0f4`) and in a fresh
`cli-output` clone at the tag (2026-10-19):

| Command | Observed |
| --- | --- |
| `git ls-remote --tags https://github.com/RandomGenericUsername/cli-output 'refs/tags/v0.1.0*'` | exit 0; `91489b73b54e6cd09dc54e360431a3ebb915fa05 refs/tags/v0.1.0`, `ddae372786fd6053730133e82cf542a17e9a5ae5 refs/tags/v0.1.0^{}` |
| fresh clone: `make sync && make gates && make hermetic && uv lock --check && uv build` | exit 0; `63 passed`; `dist/cli_output-0.1.0-py3-none-any.whl` + `.tar.gz` |
| `rg -n 'shared/cli-output' --glob 'pyproject.toml' --glob '*.lock' --glob '*.yml' --glob '*.yaml' --glob '*.py' --glob '*.md' src dotfiles scripts Makefile` | 5 pyproject consumers (runtime, provisioning, csg, weg, itr), 5 locks, `Makefile:100`; plus the two Dockerfiles and the guard itself (see below) |
| `rg -n 'cli-output = \{ path\|\./shared/cli-output' src --glob 'pyproject.toml'` | exit 1 — no path pin for `cli-output` (CAE/OCI editable pins intentionally untouched) |
| `rg -n 'ddae372' <pkg>/uv.lock` for the five consumers | 5 matches, each `source = { git = "…/cli-output?tag=v0.1.0#ddae372786fd6053730133e82cf542a17e9a5ae5" }` |
| `uv lock --check --directory <pkg>` ×5 | exit 0 each |
| `uv run --directory src/runtime python -c "import cli_output, pathlib; print(pathlib.Path(cli_output.__file__).resolve())"` | `…/src/runtime/.venv/lib/python3.14/site-packages/cli_output/__init__.py`, exit 0 |
| `rg -n 'cli-invocation-contract = .*contracts", tag = "v0\.1\.0"' src --glob 'pyproject.toml'` | 4 matches (runtime + csg + weg + itr) — contract pin untouched |
| `uv run --directory src/runtime pytest tests/architecture/test_layering.py -q` | `128 passed`, exit 0 |
| `uv run --directory src/provisioning pytest tests/architecture/test_layering.py -q` | `37 passed`, exit 0 |
| `make hermetic` | exit 0 — five remaining packages: 163 / 1095+2 skipped / 288 / 346 / 638 passed |
| `uv run --directory src/runtime pytest -q` | exit 1 — `1 failed, 2122 passed, 2 skipped, 1 xpassed`; the failure is the pre-existing `test_recording_indicator.py::TestNoPollingInvariant::test_bar_widget_has_no_poll_loop`, unrelated to this slice |
| `uv run --directory src/provisioning pytest -q` | `928 passed, 6 skipped`, exit 0 |
| `make gates-ci` | exit 0 — five gates; `deploy-coverage: PASS` incl. `'cli-output' is consumed from its pinned repo — no in-tree package and no path source`; `ci-gates-parity: PASS` |
| `make deploy-coverage` | exit 0, same new line |
| `uv run --directory src/provisioning pytest -q tests/unit/test_compositor_configs_role.py -k DeployCoverageGate` | `18 passed, 33 deselected`, exit 0 |
| `openspec validate cli-tools-repos --type change` | `Change 'cli-tools-repos' is valid`, exit 0 |
| `test ! -e src/shared/cli-output && echo ABSENT` | `ABSENT`, exit 0 |
| residual scan `rg -n 'src/shared/cli-output\|shared/cli-output' --hidden -g '!.git' -g '!.worktrees' -g '!uv.lock'` | only `docs/investigation/**` + `docs/01-…` (historical plan), `_bmad-output/**`, `openspec/changes/**` records, and the new guard + its tests (which must name the retired path) |

Notes and deviations:

- The two architecture-test copies needed **no edit** (opposite of the S1 step 6
  expectation): `_allowed_third_party_roots()` adds `cli_output` from
  `[project].dependencies` as well as from `[tool.uv.sources]` keys, so it
  accepts the git source unchanged; both suites above are the proof.
- The two Dockerfiles were edited even though SLICES.md defers the Dockerfile
  rewrite to S3/S5: deleting the tree would otherwise leave a live
  `COPY src/shared/cli-output` in `Dockerfile.base` and
  `Dockerfile.imagemagick`, failing the S1 reference-cleanup gate. They now
  `pip install "cli-output @ git+…/cli-output@v0.1.0"` (adding `git` +
  CA certificates). A `podman build` of `Dockerfile.base` fetched `cli-output`
  from the tag successfully and then failed on a **pre-existing** gap: the
  image never installed `cli-invocation-contract` (a dependency since S0b), and
  that package is not on PyPI. The image build was already broken before this
  slice; S3/S5's `uv sync`-from-lock rewrite owns the fix.
- `openspec/specs/cli-output/spec.md` was retired here (it asserted the package
  SHALL live at `src/shared/cli-output/`); the capability now ships with the
  code as `openspec/specs/cli-output-presentation/spec.md` in the `cli-output`
  `v0.1.0` checkout (verified in the fresh clone).

### S2 verification log

Run in the dotfiles worktree `.worktrees/clitools-s2` on
`ticket/clitools-s2-consume-cae` (base `b345bfb2`) and in a fresh
`config-assembler-engine` clone at the tag (2026-10-19):

| Command | Observed |
| --- | --- |
| `gh api repos/RandomGenericUsername/config-assembler-engine --jq .private` | `false`, exit 0 — public pin channel |
| `GIT_TERMINAL_PROMPT=0 git -c credential.helper= ls-remote …/config-assembler-engine 'refs/tags/v0.1.0*'` | exit 0; `5c5cc84e… refs/tags/v0.1.0`, `cad8a91c… refs/tags/v0.1.0^{}` — anonymous |
| fresh clone at `v0.1.0`: `make sync && make gates && make hermetic && uv lock --check` | exit 0; `git rev-parse HEAD` → `cad8a91c6bcbc4087209911bc36d82f8b6349f66`; `163 passed` |
| live-reference inventory (`rg … src dotfiles scripts Makefile`, `.venv` excluded) | 3 pyproject path sources, 3 locks, `Makefile:100`, 2 Dockerfiles, `docs/99` tree; dependency declarations and the `weg_adapter` prose mention need no edit |
| `rg -n 'config-assembler-engine = \{ path\|\./shared/config-assembler-engine' src --glob 'pyproject.toml'` | exit 1 — no path pin remains (scoped: the `oci-runtime` editable pin is S3's) |
| `rg -n 'cad8a91c6bcbc4087209911bc36d82f8b6349f66' <pkg>/uv.lock` ×3 | 3 matches, each `source = { git = "…/config-assembler-engine?tag=v0.1.0#cad8a91c…" }` |
| `uv lock --check --directory <pkg>` ×3 | exit 0 each |
| pre-deletion: `uv run --directory src/shared/config-assembler-engine pytest -q` | `163 passed`, exit 0 |
| pre-deletion: `make hermetic` | exit 0 — five packages: 1095+2 skipped / 288 / 346 / 638 passed |
| `git rm -r src/shared/config-assembler-engine` | 66 files, 4769 lines deleted; `test ! -e` → `ABSENT` |
| post-deletion: `make hermetic` | exit 0 — four remaining packages: oci-runtime 1095+2 skipped, itr 288, weg 346, csg 638 |
| `for p in itr weg csg: uv run --directory "$p" pytest -q -k "config or resolv or strateg"` | exit 0: itr `68 passed, 220 deselected`; weg `52 passed, 294 deselected`; csg `84 passed, 554 deselected` |
| `uv run --directory src/provisioning pytest -q tests/unit/test_compositor_configs_role.py -k DeployCoverageGate` | `20 passed, 33 deselected`, exit 0 |
| `make deploy-coverage` | exit 0, new line `'config-assembler-engine' is consumed from its pinned repo — no in-tree package and no path source` |
| `make gates-ci` | exit 0 — five gates; `deploy-coverage: PASS`, `ci-gates-parity: PASS` |
| `make hermetic` / `make gates-ci` / `make deploy-coverage` on the worktree HEAD | all exit 0 |
| `openspec validate cli-tools-repos --type change` | `Change 'cli-tools-repos' is valid`, exit 0 |
| isolated install: `UV_TOOL_DIR=/tmp/opencode/s2-uvtools UV_TOOL_BIN_DIR=/tmp/opencode/s2-uvbin uv tool install --force src/cli-tools/icon-templates-renderer` | exit 0, `Installed 1 executable: itr` |
| tool env `config_assembler_engine` `direct_url.json` | `{"vcs_info":{"vcs":"git","commit_id":"cad8a91c…","requested_revision":"v0.1.0"}}` — resolved from the tag |
| tool venv: `python -c "import config_assembler_engine; print(Path(...).resolve())"` | `…/s2-uvtools/icon-templates-renderer/lib/python3.14/site-packages/config_assembler_engine/__init__.py`, exit 0 |
| `/tmp/opencode/s2-uvbin/itr --version` and `itr list dotfiles/config/icon-template-color-scheme-mappings/icons.yaml` (isolated `HOME`/`XDG_CONFIG_HOME`) | `0.1.0 contract 0.1.0`; the group list printed (`battery:`, `network:`, …), exit 0 — real resolution through the installed engine |
| `uv run --directory src/runtime pytest -q` with the stale `~/.local/bin` tool dir off `PATH` | exit 1 — `1 failed, 2120 passed, 5 skipped`; the only failure is the pre-existing `test_recording_indicator.py::TestNoPollingInvariant::test_bar_widget_has_no_poll_loop` |
| `uv run --directory src/provisioning pytest -q` with the stale tool dir off `PATH` | `918 passed, 16 skipped, 2 failed`: `TestVerifyRuntime` playbook runs time out after 120 s |
| base-commit check: same two `TestVerifyRuntime` cases at `b345bfb2` in `.worktrees/s2-basecheck` | identical 120 s `subprocess.TimeoutExpired` timeouts — pre-existing on the base, not caused by S2; the touched-file diff is empty for the verify role/playbook/test |

Inventory and disposition (live references, before deletion):

| Reference | Disposition |
| --- | --- |
| `src/cli-tools/{color-scheme-generator,wallpaper-effects-generator,icon-templates-renderer}/pyproject.toml` `[tool.uv.sources]` | repointed from `path` to `git = …, tag = "v0.1.0"` |
| those three `uv.lock` files | regenerated; each records `#cad8a91c6bcbc4087209911bc36d82f8b6349f66` |
| `Makefile:100` `HERMETIC_PACKAGES` | CAE entry removed (now four packages) |
| csg `Dockerfile.base:9,11`, weg `Dockerfile.imagemagick:12,18` | `COPY`/path install replaced with `config-assembler-engine @ git+…@v0.1.0` (the S1 cli-output shape; the S3 `uv sync` rewrite still owns the build model) |
| `docs/99-dotfiles-hexagonal-architecture.md` shared/ tree | updated: only the remaining in-repo `oci-runtime` is listed; CAE is named as consumed from its pinned repo |
| three CLI `docs/ARCHITECTURE_PLAN.md`, `docs/01-…`, `docs/investigation/**`, `openspec/changes/**`, `_bmad-output/**` | historical planning/evidence records — left unchanged, out of reference-cleanup scope by rule |
| `src/runtime/src/runtime/adapters/weg_adapter.py:54` | prose mention only; no pin or path |
| `scripts/deploy-coverage.py` + `test_compositor_configs_role.py` | guard/test must name the retired path — expected residual |
| dependency declarations (`"config-assembler-engine"`, `>=0.1.0`) | unchanged; the tag's version `0.1.0` satisfies them |

Known environment deviation (not a slice failure): the host's pre-S0b `uv tool`
installs in `~/.local/bin` are broken because their editable `.pth` files point
at `src/shared/cli-output` (deleted when S1 merged). Leaving that dir on `PATH`
makes four settings-parity cases call a stale `csg`/`weg` and fail with
`ModuleNotFoundError: cli_output.adapters.factory`; the suites above were run
with that stale dir removed from `PATH`, which is the designed skip path. The
two provisioning `verify.yaml` timeouts reproduce at the base commit and are
unrelated.

## 0. Execution contract (applies to every task below)

**Per-target loop (AD-13), in this order, in one slice:**

```text
create repo from the birth checklist
  → import the package as the repo root (git subtree split -P <path>)
  → repoint in-repo deps to tags, regenerate locks
  → tag (gates green on a fresh clone), CI attaches the release artifacts
  → rewire dotfiles-v3 consumption to the tag
  → prove the new wiring by execution (install, run, image build where applicable)
  → delete the in-tree copy + every reference it orphaned, add/extend the absence guard
  → merge; only then start the next target
```

**Worktree discipline.** Every slice runs in a worktree created by
`bash scripts/worktree-guard.sh create <id> <slug>` on
`ticket/<id>-<slug>`; never on `master`. The S0a work is in the **`contracts`**
repo, in **its** worktree, under **its** `AGENTS.md` (ticket in
`contracts/tickets/`, OpenSpec change in `contracts/openspec/`), never in a
dotfiles worktree and never on `main`.

**Merge evidence (the ags precedent, S4 §5.2–5.4).** A target's deletion is one
commit that (a) removes the tree, (b) retires every reference it orphaned and
(c) adds/extends the `deploy-coverage` absence assertion. The merge that lands it
adds nothing beyond that payload. Record both in the ticket:

```bash
git show --stat <deletion-commit>      # (a)+(b)+(c) in one commit
git diff --stat <merge>^1 <merge>      # equals that payload; the merge adds no edits
git log --oneline -1 <merge>           # the merge commit named in the next slice's ticket
```

The next slice's first commit must descend from that merge
(`git merge-base --is-ancestor <merge> <next-first-commit>`); this is a process
obligation proven by the recorded SHAs, not by a code diff.

**Evidence.** Each task's gate is a command and an expected observable copied
from `SLICES.md`; a green command is the completion criterion, not a diff review.
Historical dirs `_bmad-output/` and `openspec/changes/archive/` are out of scope
for reference-cleanup greps by rule.

**Birth gates (run in every new repo before its first tag; 0.5's anonymous probe
runs immediately after the tag is pushed, because it proves the tag itself).**
These are the executable form of the `cli-repo-birth` scenarios. They run inside
the new repo with `MU=/home/inumaki/Development/mu`,
`REPO=<absolute new-repo path>`, `NAME=<repo name>` and
`TAG=<the tag being released>` (`v0.1.0` for all but `oci-runtime`, `v0.5.0`).

- [ ] 0.1 The harness is byte-identical to `mu`.
  Gate: `diff -u "$MU/scripts/worktree-guard.sh" scripts/worktree-guard.sh && diff -u "$MU/skills-lock.json" skills-lock.json`
  Expect: exit 0, no output. `mu` ships no hash-recompute script (only
  `scripts/worktree-guard.sh`), so byte-equality with the pinned source is the
  proof that every `computedHash` matches — do not invent a hash tool.

- [ ] 0.2 Verbs resolve their own paths from any caller directory.
  Gate: `cd /tmp/opencode && make -C "$REPO" gates`
  Expect: exit 0.
  Gate: `rg -n '\$\(PWD\)|\$\(shell pwd\)' "$REPO/Makefile"`
  Expect: exit 1 — every recipe anchors on `$(CURDIR)`, never on the caller's
  `pwd`.

- [ ] 0.3 CI parity runs before the first push.
  Gate: `make -C "$REPO" ci-gates-parity`
  Expect: `PASS` — the repo copies `scripts/ci-gates-parity.py` from this repo
  (the parser behind `dotfiles-v3`'s `Makefile:93` target). The first
  `.github/workflows/gates.yml` run is proven by its run URL + conclusion
  recorded in the birth ticket; the local parity command is the reproducible
  part.

- [ ] 0.4 The hermetic fixture and canary exist.
  Gate: `rg -l 'XDG_CONFIG_HOME' "$REPO/tests/conftest.py" && uv run --directory "$REPO" pytest -q -k canary`
  Expect: one conftest path and at least one passing canary.

- [ ] 0.5 The pin channel is anonymous — the repo is public, proven by
  execution, never assumed.
  Gate: `gh repo view "RandomGenericUsername/$NAME" --json visibility --jq .visibility`
  Expect: `PUBLIC`. Equivalent form: `gh api "repos/RandomGenericUsername/$NAME" --jq .private`
  → `false`.
  Gate (immediately after the first tag is pushed, and again for every later
  tag): `cd /tmp/opencode && GIT_TERMINAL_PROMPT=0 git -c credential.helper= ls-remote https://github.com/RandomGenericUsername/"$NAME" "refs/tags/$TAG"`
  Expect: exit 0 and exactly one line, `<sha>\trefs/tags/<tag>`. An anonymous
  probe with the credential helper cleared and terminal prompting disabled is the
  proof: provisioning clones exactly like this, so anything that needs a
  credential fails here first.

  Why this is a gate, not a note. The `ags-apps` precedent got this wrong and the
  orchestrator verified it: `gh api repos/RandomGenericUsername/ags-apps --jq .private`
  → `true`, while `src/provisioning/ansible/roles/ags_apps/tasks/main.yml:12-13`
  claims "the repo is public, so no `gh` credential helper is needed"; the same
  anonymous probe against `ags-apps` fails with `fatal: could not read Username`.
  The claim was never executable, so nothing caught it. Do not carry that shape
  into the six pins: the visibility read and the anonymous `ls-remote` are the
  gate, and a green `gh repo view` alone is not enough.

- [ ] 0.6 The visibility decision and its consequence are recorded.
  A **private** repo breaks provisioning's anonymous clone: `ansible.builtin.git`
  fetches the pin from the provisioned host with no credential helper, so the tag
  can never be resolved and the slice's install, `verify` and image build fail at
  the fetch — not at a check that could explain it. If the decision ever changes
  to private, provisioning MUST gain credential handling (a `gh` credential
  helper, or a token/SSH pin URL) **in the same slice**, as an explicitly chosen
  alternative — never silently accepted.
  Gate: the birth ticket records the two 0.5 outputs verbatim (the visibility
  token and the single `ls-remote` line) and states which channel is pinned
  (`anonymous https`, i.e. no credential helper).
  Expect: both outputs present for the repo's own first tag, plus one line naming
  the pin channel. A ticket that asserts "public" without the two outputs does
  not satisfy 0.5/0.6.

## 1. S0a — invocation contract in `contracts` + first tag `v0.1.0`

- [x] 1.1 Create the worktree, branch and ticket in the `contracts` repo, and open
  its OpenSpec change for the contract package.
  Gate: `cd "$CONTRACTS" && bash scripts/worktree-guard.sh check-clean`
  Expect: exit 0 on clean `main`; `git branch --show-current` is the new
  `ticket/<id>-cli-invocation-contract`, not `main`.
  Done: worktree `.worktrees/req-006` on
  `ticket/req-006-cli-invocation-contract`; `tickets/REQ-006-cli-invocation-contract/ticket.md`
  and `openspec/changes/cli-invocation-contract/` exist;
  `bash scripts/worktree-guard.sh check-clean` → exit 0.

- [x] 1.2 Add the package skeleton: root `pyproject.toml` (hatchling,
  `requires-python >=3.12`, version `0.1.0`), `src/cli_invocation_contract/`,
  `tests/`, committed `uv.lock`; the loader is stdlib-only and `pytest` is the
  only dev dependency.
  Gate: `cd "$CONTRACTS" && uv sync && uv run pytest -q && uv build`
  Expect: exit 0; `dist/cli_invocation_contract-0.1.0-*.whl` and `.tar.gz` exist.
  Done: `uv build` → `dist/cli_invocation_contract-0.1.0-py3-none-any.whl` +
  `.tar.gz`, exit 0; `unzip -l` lists `cli_invocation_contract/invocation-contract.json`
  inside the wheel.

- [x] 1.3 Add `invocation-contract.json` with one entry per CLI (`csg`, `weg`,
  `itr`) carrying exactly argv template, required env keys, required artifact
  names/suffixes, exit-code semantics and default timeout, copied from S1
  §1.3–1.5 and §2.2 — not re-derived.
  Gate:
  `uv run python -c "from cli_invocation_contract import CONTRACT_VERSION, load; c = load(); assert sorted(c) == ['csg','itr','weg'], sorted(c); assert all({'argv','env','artifacts','exit_codes','timeout'} <= set(v) for v in c.values()); print(CONTRACT_VERSION)"`
  Expect: `0.1.0`.
  Done: gate printed `0.1.0` (with `DATA_VERSION` → `1`); record shape
  `{"contract_version", "timeout_unit", "clis"}` with one entry per CLI.

- [x] 1.4 Add `src/cli_invocation_contract/testkit.py` with the two AD-4
  assertions (`assert_consumer_invocation`, `assert_cli_writes_artifacts`) and
  tests: record completeness, loader round-trip, testkit accept/reject against a
  fake CLI. No test shells out to a real CLI.
  Gate: `cd "$CONTRACTS" && uv run pytest -q`
  Expect: exit 0; the new testkit tests are collected and pass.
  Done: `uv run pytest -q` → `49 passed`; the kit files alone →
  `22 passed`. The shipped name of the second assertion is
  `assert_cli_writes_artifacts` (`testkit.py:201`); the planning-time
  `assert_cli_conformance` was a placeholder and is not the API.

- [x] 1.5 Update `contracts/README.md` and `contracts/AGENTS.md` §2 so the charter
  names both seams. (The relocation of the two boundary specs is split out to
  2.7 and deferred to S0b.)
  Gate: `cd "$CONTRACTS" && make contracts-drift && make check-symmetry`
  Expect: exit 0 (the existing AGS event machinery is unchanged).
  Done: `make contracts-drift` and `make check-symmetry` → exit 0,
  `[drift] symmetric: contract and generated/ agree`; the README lists both
  contracts and AGENTS §2 names the invocation seam and the same-tag pin.

- [x] 1.6 Release: version `0.1.0` in `pyproject.toml`, annotated tag `v0.1.0`,
  pushed. (No `CHANGELOG.md` was added and the GitHub Release asset attachment
  was not done; both are split out to 2.8 and deferred to S0b.)
  Gate: `git ls-remote --tags --refs origin 'refs/tags/v0.1.0'`
  Expect: exactly one line — the annotated tag ref (`--refs` drops the peeled
  `^{}` line).
  Gate: `git ls-remote origin 'refs/tags/v0.1.0^{}'`
  Expect: a single peeled entry (`refs/tags/v0.1.0^{}`) naming the commit the
  tag resolves to; this is the `<repo>^{}` query, not a ref-count check.
  Done: `pyproject.toml:7` is `version = "0.1.0"`; tag object `6ea43dcb…`;
  peeled `48cf3cfed4b192b241505789409c4f282921c896`; anonymous `ls-remote` exits
  0 with one line; `contract-drift` CI run on `v0.1.0` is `success`.

## 2. S0b — dotfiles prerequisites (no extraction, no tag)

Two S0a lines were only partly evidenced and are carried here; do them before
2.9's merge gate. They are cross-repo edits (a `contracts` change plus the
dotfiles deletion that follows it), so they could not close inside S0a's
contracts-only scope.

- [x] 2.1 Add an autouse `tests/conftest.py` fixture to each of the six packages
  (`HOME` + four XDG vars to per-test temp dirs, `chdir` to a temp dir), one
  canary test per package, and `pytest`/`pytest-cov` dev deps to `cli-output` and
  `config-assembler-engine`.
  Gate: for each of `src/shared/cli-output src/shared/config-assembler-engine
  src/shared/oci-runtime src/cli-tools/icon-templates-renderer
  src/cli-tools/wallpaper-effects-generator src/cli-tools/color-scheme-generator`,
  run `uv run --directory "$p" pytest -q`
  Expect: exit 0 for all six; record `<N> passed` per package.
  Done: `make hermetic` → exit 0, 63 / 163 / 1095+2 skipped / 288 / 346 / 638
  passed. All six carry `tests/conftest.py` + `tests/test_hermetic_canary.py`;
  `pytest-cov>=7.0` in `cli-output` and `config-assembler-engine` dev deps.

- [x] 2.2 Fix the two known environment-dependent tests **in the tests**, not the
  resolvers: csg `test_resolve_falls_back_to_package_defaults` and itr
  `test_resolves_bundled_default`.
  Gate: `env HOME=/tmp/opencode/fakehome XDG_CONFIG_HOME=/tmp/opencode/emptyxdg-csg
  uv run --directory src/cli-tools/color-scheme-generator pytest -q
  tests/unit/adapters/test_template_dir_resolver.py` and the itr equivalent
  `test_assembled_config_resolver.py` with an empty `XDG_CONFIG_HOME`.
  Expect: exit 0 (4 passed / 6 passed respectively, per S3 §5.1).
  Done: `4 passed` and `6 passed`, both exit 0.

- [x] 2.3 Add `--version` to `csg`, `weg`, `itr`: prints
  `<package-version> contract <contract-version>` from
  `cli_invocation_contract.CONTRACT_VERSION`, never from `cli-output`.
  Gate: `for b in itr weg csg; do "$b" --version; done`
  Expect: three lines `0.1.0 contract 0.1.0`.
  Done: three lines `0.1.0 contract 0.1.0` via the in-tree entry points
  (`uv run --directory <pkg> <bin> --version`). Narrower than the literal gate:
  the `~/.local/bin` binaries on this host link to an `uv tool` install from
  16:53 whose `cli/main.py` has no `--version`, so those stale copies were not
  rebuilt or re-tested here.

- [x] 2.4 Pin `contracts v0.1.0` in `src/runtime/pyproject.toml` and the three
  in-tree CLIs; regenerate the four locks; replace the runtime adapter contract
  literals with kit calls.
  Gate: `rg -n 'cli-invocation-contract = .*contracts", tag = "v0\.1\.0"' src --glob 'pyproject.toml'`
  Expect: exactly 4 matches (runtime + csg + weg + itr).
  Gate: `uv run --directory src/runtime pytest tests/unit/test_cli_invocation_contract.py -q`
  Expect: exit 0. The slice adds
  `src/runtime/tests/unit/test_cli_invocation_contract.py`: it loads the record
  from `cli_invocation_contract` and calls `assert_consumer_invocation` with each
  adapter's constructed argv/env (tests `test_csg_invocation_matches_record`,
  `test_weg_invocation_matches_record`, `test_itr_invocation_matches_record`).
  Gate: `rg -n 'def test_(csg_generate_env_override_writes_to_output_dir|weg_generate_env_override_writes_to_output_dir|itr_render_env_override_writes_to_output_dir)' src/runtime/tests`
  Expect: exit 1 — the three duplicated literal assertions named in S1 §6.1
  (`test_csg_adapter.py:128-135`, `test_weg_adapter.py:114-119`,
  `test_itr_adapter.py:126-132`) are gone from the runtime suite, replaced by
  the record-driven file above.
  Gate: `uv run --directory src/runtime pytest tests/unit/test_csg_adapter.py
  tests/unit/test_weg_adapter.py tests/unit/test_itr_adapter.py -q`
  Expect: exit 0; 33 passed or more after migration.
  Gate: `uv run --directory src/runtime python -c
  "from cli_invocation_contract import CONTRACT_VERSION; print(CONTRACT_VERSION)"`
  Expect: `0.1.0`.
  Done: 4 pin matches; duplicated-literal `rg` → exit 1 (no matches);
  contract version `0.1.0`; the record file plus the three adapter suites →
  `36 passed`, exit 0.

- [x] 2.5 Remove the two boundary specs now owned by `contracts`; keep
  `openspec/changes/archive/**` untouched. Add developer target `make hermetic`
  (runs the six suites under a scrubbed env; not added to `GATES`).
  Gate: `env -u XDG_CONFIG_HOME HOME="$(mktemp -d)" TMPDIR=/tmp make hermetic`
  Expect: exit 0; canary tests present in every package.
  Done: `git rm -r openspec/specs/interface-contract-test
  openspec/specs/container-adapter-env-contract` → both `spec.md` removed;
  `make hermetic` → exit 0 with the six counts above (the target scrubs the env
  itself, `Makefile:107-127`). Archive untouched.

- [x] 2.6 Prove the repo gate set is unchanged.
  Gate: `make gates-ci && make deploy-coverage`
  Expect: exit 0, five gates, `deploy-coverage: PASS`.
  Done: `make gates-ci` → exit 0, five gates, `deploy-coverage: PASS` and
  `ci-gates-parity: PASS`; `make deploy-coverage` alone → exit 0,
  `deploy-coverage: PASS`.

- [x] 2.7 **Deferred from S0a — cross-repo edit.** Move
  `openspec/specs/interface-contract-test` and
  `openspec/specs/container-adapter-env-contract` into
  `contracts/openspec/specs/` (the half of former 1.5 that did not land; the
  charter half shipped at `48cf3cf`). This must precede 2.5's deletion and has
  to be paired with it: deleting the dotfiles copies without landing the
  contracts copies would leave both specs owned by no repo.
  Gate: `ls "$CONTRACTS/openspec/specs/interface-contract-test/spec.md"
  "$CONTRACTS/openspec/specs/container-adapter-env-contract/spec.md"`
  Expect: exit 0, both paths exist in `contracts`; then 2.5's deletion gate,
  `git ls-files openspec/specs/interface-contract-test
  openspec/specs/container-adapter-env-contract`, is empty here.
  Done: `contracts` main `55ad61b` tracks both `spec.md` files
  (`git -C contracts ls-files` → two paths) and `openspec validate --all` there
  → `10 passed, 0 failed`, exit 0. Here `git ls-files` for both paths → empty,
  exit 0. The dotfiles copies were deleted **after** the contracts copies
  landed, so neither spec was ever unowned.

- [x] 2.8 **Deferred from S0a — cross-repo edit.** Complete the `contracts`
  `v0.1.0` release at `48cf3cf`: add the missing `CHANGELOG.md` (design D3's
  release ritual names it) and publish the GitHub Release with the sdist and
  wheel attached.
  Gate: `gh release view v0.1.0 --json tagName,assets --jq '[.tagName, (.assets[].name)] | @tsv'`
  Expect: exit 0, `v0.1.0` plus both
  `cli_invocation_contract-0.1.0-py3-none-any.whl` and
  `cli_invocation_contract-0.1.0.tar.gz`.
  Gate: `test -s "$CONTRACTS/CHANGELOG.md" && rg -n '0\.1\.0' "$CONTRACTS/CHANGELOG.md"`
  Expect: exit 0 with a `0.1.0` entry.
  Done: `gh release view v0.1.0` → `tagName: v0.1.0` with both assets, exit 0;
  `CHANGELOG.md` is tracked at `contracts` HEAD (`5e03075`, entry added in
  `fcba526`) with `## [0.1.0] - 2026-10-19` at line 16.

- [x] 2.9 Merge S0b to `master` before starting S1.
  Gate: `make gates-ci && make deploy-coverage` on the merged `master`
  Expect: exit 0, five gates, `deploy-coverage: PASS`.
  Done: fast-forward merge `f4f16f11..56d7d85e` onto `master`, then pushed
  (`origin/master == 56d7d85e`); `make gates-ci` → exit 0 at HEAD `56d7d85e`
  before the merge, five gates with `deploy-coverage: PASS` and
  `ci-gates-parity: PASS`. S1 is now unblocked.

## 3. S1 — `cli-output` repo + `v0.1.0`

- [x] 3.1 Create the repo from the birth checklist, import `src/shared/cli-output`
  as the repo root (history via `git subtree split -P src/shared/cli-output`),
  add the harness, and leave `[tool.uv.sources]` empty.
  Gate: `git clone "$CLI_REPO_BASE/cli-output" /tmp/opencode/cli-output && cd /tmp/opencode/cli-output && make sync && make gates && make hermetic && uv lock --check && uv build`
  Expect: exit 0; `dist` contains `cli_output-0.1.0-*.whl` + `.tar.gz`.
  Done: fresh clone at the tag → the chained gate exited 0, `make hermetic` →
  `63 passed`, `dist/cli_output-0.1.0-py3-none-any.whl` + `.tar.gz` exist;
  `[tool.uv.sources]` is empty (the package has no sibling deps).

- [x] 3.2 Tag `v0.1.0` (version continuity with the imported in-tree `0.1.0`).
  Gate: `git ls-remote --tags --refs "$CLI_REPO_BASE/cli-output" 'refs/tags/v0.1.0'`
  Expect: exactly one line (the tag ref; `--refs` drops the peeled `^{}` line).
  Done: exactly one line, `91489b73b54e6cd09dc54e360431a3ebb915fa05
  refs/tags/v0.1.0`, exit 0; the peeled query adds
  `ddae372786fd6053730133e82cf542a17e9a5ae5 refs/tags/v0.1.0^{}`, and
  `git -C /tmp/opencode/cli-output-inspect rev-parse HEAD` is that commit.

- [x] 3.3 Rewire `src/runtime/pyproject.toml`, `src/provisioning/pyproject.toml`
  and each still-in-tree CLI's `pyproject.toml` from path to git tag `v0.1.0`;
  regenerate all five locks; update the two architecture-test forbidden sets so
  `cli_output` is accepted as a git dependency.
  Gate: `rg -n 'cli-output = \{ path = "\.\./shared/cli-output"' src --glob 'pyproject.toml'`
  Expect: exit 1 (no matches). This gate is deliberately scoped to `cli-output`:
  `config-assembler-engine` and `oci-runtime` still legitimately carry
  `editable = true` path sources in this slice, gated out in 4.2 (S2) and 5.2
  (S3) respectively. The unscoped
  `rg -n 'path = "\.\./shared|editable = true' src --glob 'pyproject.toml'`
  catch-all is a post-S3 assertion (5.5), not an S1 gate.
  Gate: `rg -n 'cli-invocation-contract = .*contracts", tag = "v0\.1\.0"' src --glob 'pyproject.toml'`
  Expect: 4 matches (the contract pin is untouched).
  Gate: `uv run --directory src/runtime python -c
  "import cli_output, pathlib; p=pathlib.Path(cli_output.__file__).resolve(); print(p); assert 'src/shared' not in str(p)"`
  Expect: exit 0; path under `.venv/lib/.../site-packages/cli_output`.
  Done: all five consumers now declare
  `cli-output = { git = "https://github.com/RandomGenericUsername/cli-output", tag = "v0.1.0" }`
  (dependency name unchanged; CAE/OCI path sources untouched). The scoped gate →
  exit 1; `rg -n 'cli-invocation-contract = …"v0\.1\.0"'` → 4 matches; every lock
  records `#ddae372786fd6053730133e82cf542a17e9a5ae5` and `uv lock --check` is
  green ×5; the import resolves to
  `src/runtime/.venv/lib/python3.14/site-packages/cli_output/__init__.py`.
  Architecture tests needed no forbidden-set change (see the S1 verification
  log).

- [x] 3.4 Delete `src/shared/cli-output/`, update the two architecture-test
  copies in the same slice, and extend `scripts/deploy-coverage.py` with the
  absence assertion for `src/shared/cli-output` (the `src/gui-tools` precedent,
  S4 §5.2: the guard lands in the deletion commit, not a later cleanup).
  Gate: `uv run --directory src/runtime pytest tests/ -q && uv run --directory src/provisioning pytest tests/unit tests/integration/test_settings_parity.py -q`
  Expect: exit 0.
  Gate: `make gates-ci && make deploy-coverage && test ! -e src/shared/cli-output && echo "ABSENT"`
  Expect: exit 0 and `ABSENT`; `deploy-coverage` names `src/shared/cli-output` in
  its retired-tree assertion.
  Done: `git rm -r src/shared/cli-output` removed 25 files / 1330 lines (plus
  the untracked `.venv`/cache, so `test ! -e` is true). The two
  architecture-test copies needed no edit — `_allowed_third_party_roots()`
  already accepts the git source via the dependency name (`128 passed` runtime,
  `37 passed` provisioning). `deploy-coverage` gained
  `assert_no_in_tree_cli_output`: absent tree **and** no `path =` source under
  any `src/**/pyproject.toml`; its gate tests → `18 passed, 33 deselected`.
  `make gates-ci` → exit 0 with the new
  `'cli-output' is consumed from its pinned repo` line; `ABSENT` printed.
  Runtime suite: `1 failed, 2122 passed, 2 skipped, 1 xpassed` — the failure is
  the pre-existing recording-indicator test. Provisioning suite: `928 passed,
  6 skipped`, exit 0.

- [x] 3.5 Merge S1 to `master`; only then start S2.
  Gate: `make gates-ci && make deploy-coverage` on the merged `master`
  Expect: exit 0; no gate points at the deleted tree.
  Done: fast-forward merge `96c4a0f4..843b50d0` onto `master`, then pushed
  (`origin/master == 843b50d0`). At HEAD before the merge: `make hermetic` exit
  0, `make gates-ci` exit 0 (five gates, `deploy-coverage: PASS` incl. the
  `'cli-output' is consumed from its pinned repo` line, `ci-gates-parity: PASS`)
  and `make deploy-coverage` exit 0 — no gate points at the deleted tree.
  Post-merge re-checks at `843b50d0`: five locks (runtime, provisioning, csg,
  weg, itr) record `ddae372786fd6053730133e82cf542a17e9a5ae5`, `rg -n
  'cli-output = \{ path|\./shared/cli-output' src --glob 'pyproject.toml'` → exit
  1 (zero path pins), and `test ! -e src/shared/cli-output` → `ABSENT`. S1 is
  closed; S2 is unblocked.

## 4. S2 — `config-assembler-engine` repo + `v0.1.0`

- [x] 4.1 Create the repo from the birth checklist, import
  `src/shared/config-assembler-engine` as the repo root, add the harness, leave
  `[tool.uv.sources]` empty, and tag `v0.1.0` (version continuity).
  Gate: `git clone "$CLI_REPO_BASE/config-assembler-engine" /tmp/opencode/cae && cd /tmp/opencode/cae && make sync && make gates && make hermetic && uv lock --check`
  Expect: exit 0.
  Done: fresh clone at `v0.1.0` (tag object `5c5cc84e`, peeled commit
  `cad8a91c`) → the chained gate exited 0, `163 passed`; the repo is public
  (`gh api … --jq .private` → `false`) and the anonymous `ls-remote` returned
  exactly the tag + peeled lines.

- [x] 4.2 Repoint csg, weg and itr `pyproject.toml` to
  `git = …/config-assembler-engine, tag = "v0.1.0"`; regenerate the three locks.
  Gate: `rg -n 'config-assembler-engine = \{ path = "\.\./shared/config-assembler-engine"' src --glob 'pyproject.toml'`
  Expect: exit 1 (no matches). Scoped to CAE on purpose: `oci-runtime` is the
  last editable path source and is gated out in 5.2 (S3).
  Done: all three now declare `config-assembler-engine = { git =
  "https://github.com/RandomGenericUsername/config-assembler-engine", tag =
  "v0.1.0" }`; the scoped gate → exit 1; each lock records
  `#cad8a91c6bcbc4087209911bc36d82f8b6349f66` and `uv lock --check` is green
  ×3. `oci-runtime` path pins untouched.

- [x] 4.3 Delete `src/shared/config-assembler-engine/` and its lock entries;
  extend `scripts/deploy-coverage.py` with the absence assertion for
  `src/shared/config-assembler-engine` in the same commit.
  Gate: for each of `src/cli-tools/icon-templates-renderer
  src/cli-tools/wallpaper-effects-generator src/cli-tools/color-scheme-generator`,
  run `uv run --directory "$p" pytest -q -k "config or resolv or strateg"`
  Expect: exit 0 for all three.
  Gate: `make gates-ci && make deploy-coverage && test ! -e src/shared/config-assembler-engine && echo "ABSENT"`
  Expect: exit 0 and `ABSENT`; `deploy-coverage` names the tree in its
  retired-tree assertion.
  Done: pre-deletion `make hermetic` (five packages) and the CAE suite
  (`163 passed`) were green, then `git rm -r` removed 66 files / 4769 lines
  (`ABSENT` printed). The three `-k` suites → `68 / 52 / 84 passed`, exit 0.
  `deploy-coverage` gained `assert_no_in_tree_config_assembler_engine` (absent
  tree **and** no `path =` source under any authored `src/**/pyproject.toml`);
  its gate tests → `20 passed, 33 deselected`; `make gates-ci` → exit 0 with
  `'config-assembler-engine' is consumed from its pinned repo`.

- [x] 4.4 Merge S2 to `master`; only then start S3.
  Gate: `make gates-ci && make deploy-coverage` on the merged `master`
  Expect: exit 0; no gate points at the deleted tree.
  Done: fast-forward merge `d1f92e6c..eb880c2f` onto `master`, then pushed
  (`git ls-remote origin refs/heads/master` → `eb880c2f`, exit 0). At the S2
  worktree HEAD before the merge, `make gates-ci` → exit 0 (five gates,
  `deploy-coverage: PASS` incl. the `'config-assembler-engine' is consumed from
  its pinned repo` line, `ci-gates-parity: PASS`) and `make deploy-coverage` →
  exit 0 (recorded in the S2 verification log; the merge adds no code — `git
  diff --stat d1f92e6c eb880c2f` → `tasks.md` only). The three surviving
  consumers' locks (csg, weg, itr) record
  `cad8a91c6bcbc4087209911bc36d82f8b6349f66`; S2 is closed and S3 is unblocked.

## 5. S3 — `oci-runtime` repo + `v0.5.0` and the build-context cutover

- [x] 5.1 Create the repo from the birth checklist, import
  `src/shared/oci-runtime` as the repo root (package version 0.4.0), add the
  harness, add `resolve_build_context` (marker `pyproject.toml` +
  `src/<import_name>`) and keep `resolve_source_root` as a deprecated alias that
  accepts either marker set; migrate the locator tests (legacy + single-repo-root
  fixtures); bump to `0.5.0` and tag `v0.5.0`.
  Done: `https://github.com/RandomGenericUsername/oci-runtime` is public at
  `v0.5.0` (tag object `38ce267c…`, peeled
  `b631dfa511f5710d6e171d2ac3f0cdf58bc738af`); `pyproject.toml:3` is
  `version = "0.5.0"` and `src/oci_runtime/__init__.py` exports both
  `resolve_build_context` and the deprecated `resolve_source_root`. Fresh clone
  at the tag → `make sync` exit 0, `make gates` → `1107 passed, 2 skipped`
  (Lima parser and Windows-only skip; engine-dependent tests stay
  marked/skipped), `uv lock --check` → `Resolved 10 packages`, exit 0. The
  locator gate from `SLICES.md` also passes (see 5.2).
  Gate: `git clone "$CLI_REPO_BASE/oci-runtime" /tmp/opencode/oci && cd /tmp/opencode/oci && make sync && make gates && uv lock --check`
  Expect: exit 0 (engine-dependent tests marked/skipped, never silently absent).
  Gate:
  `uv run --directory src/cli-tools/color-scheme-generator python -c "from pathlib import Path; from oci_runtime import resolve_build_context; import tempfile; root = Path(tempfile.mkdtemp()); (root/'pyproject.toml').write_text('[project]\nname=\"x\"\n'); (root/'src'/'x').mkdir(parents=True); print(resolve_build_context(package='x', override=root))"`
  Expect: `BuildContextRoot(root=<tmp>, source='override')`, exit 0.
  Gate: `uv run --directory src/cli-tools/color-scheme-generator python -c "from oci_runtime import resolve_source_root; print(resolve_source_root.__name__)"`
  Expect: `resolve_source_root` (deprecated alias still importable).

- [x] 5.2 Pin csg and weg to `oci-runtime v0.5.0`; rewrite both in-tree
  Dockerfiles to the single-package context (`COPY pyproject.toml uv.lock` and
  `COPY src ./src`, pinned `uv` + `git` + CA certificates); remove every
  `COPY src/shared/...` and `COPY src/cli-tools/...`; change the build verb to
  `--context` with `--source-root` as alias.
  Gate: `rg -n "src/shared|src/cli-tools" src/cli-tools/*/src/*/adapters/docker/`
  Expect: exit 1 (no matches).
  Gate: `rg -n 'oci-runtime = \{ path = "\.\./shared/oci-runtime"' src --glob 'pyproject.toml'`
  Expect: exit 1 — this is the S3-scoped removal of the last editable path
  source. The catch-all runs in 5.5.
  Done: both consumers now declare `oci-runtime = { git =
  "https://github.com/RandomGenericUsername/oci-runtime", tag = "v0.5.0" }`;
  both locks record `#b631dfa511f5710d6e171d2ac3f0cdf58bc738af` and
  `uv lock --check` is green ×2. The Dockerfiles copy only `pyproject.toml`,
  `uv.lock` and `src/`, install `uv==0.9.22` in the fetching stage (with git +
  CA certificates) and `uv sync --frozen --no-dev --no-editable` from the lock —
  no sibling path. The build verb takes `--context` (`--source-root` alias;
  `CONTEXT_OPT`). Locator gate: `resolve_build_context(package='x',
  override=<tmp>)` → `BuildContextRoot(root=…, source='override')`; the
  deprecated alias is still importable. Both `rg` gates → exit 1.
  Provisioning passes `--context {{ cli_tools_repo_root }}/{{ item.source }}`
  (`roles/cli_tools/tasks/main.yml:337-338`, package dirs in
  `vars/main.yml:49-50`); role tests → `43 passed`.

- [x] 5.3 Prove both images build from a single package dir and the tools still
  run.
  Gate:
  `for p in color-scheme-generator wallpaper-effects-generator; do case $p in color-scheme-generator) df=src/color_scheme_generator/adapters/docker/Dockerfile.base ;; wallpaper-effects-generator) df=src/wallpaper_effects_generator/adapters/docker/Dockerfile.imagemagick ;; esac; ( cd "src/cli-tools/$p" && podman build -t "${p}-local:test" -f "$df" . ) || exit 1; done`,
  then `podman run --rm color-scheme-generator-local:test csg --version` and
  `podman run --rm wallpaper-effects-generator-local:test weg --version`.
  Expect: both builds exit 0; both print `0.1.0 contract 0.1.0`.
  Done: both builds exit 0 from the package dirs —
  `color-scheme-generator-local:test` = `a68a0fe379c5`,
  `wallpaper-effects-generator-local:test` = `07a2d7ef6415`. Each build log
  shows the four pinned commits fetched (`oci-runtime b631dfa`,
  `cli-output ddae372`, `config-assembler-engine cad8a91`,
  `contracts 48cf3cf`). `podman run … csg --version` and `… weg --version` both
  print `0.1.0 contract 0.1.0` (exit 0), and
  `podman run … python -c "import oci_runtime, cli_output,
  config_assembler_engine, cli_invocation_contract"` exits 0 (module resolved
  under `/opt/venv/lib/python3.14/site-packages`).

- [x] 5.4 Prove real generation in container mode and the build verb against the
  package-root context.
  Gate: `cd src/cli-tools/color-scheme-generator && uv run csg install --container-engine podman --context "$WT/src/cli-tools/color-scheme-generator"`
  Expect: exit 0; base + backend images exist.
  Gate: `uv run --directory src/runtime pytest tests/integration/test_csg_determinism.py -q -rs`
  Expect: no failures (record the JSON: `container_mode` true, engine podman).
  Done: `uv run csg install --container-engine podman --context "$PWD"` → exit
  0, base + all three backend images built (`csg-base-podman:latest`,
  `csg-custom-podman:latest`, `csg-pywal-podman:latest`,
  `csg-wallust-podman:latest`). `uv run --directory src/runtime pytest
  tests/integration/test_csg_determinism.py -q -rs` → `2 passed`, and
  `.csg_determinism.json` records `"deterministic": true`,
  `"container_mode": true`, `"engine": "podman"`. The run used the freshly
  installed `/tmp/opencode/s3-uvbin/csg` (the host's stale pre-S0b tool was
  kept off PATH).

- [x] 5.5 Delete `src/shared/oci-runtime/` and the now-empty `src/shared/`;
  extend `scripts/deploy-coverage.py` with the absence assertion for
  `src/shared/oci-runtime`.
  Gate: `make gates-ci && make deploy-coverage && test ! -e src/shared/oci-runtime && test ! -e src/shared && echo "ABSENT"`
  Expect: exit 0 and `ABSENT`.
  Gate: `rg -n 'path = "\.\./shared|editable = true' src --glob 'pyproject.toml'`
  Expect: exit 1 — with the last shared lib moved, no path/editable sibling
  source remains anywhere in `src/`. This is the post-S3 catch-all; do not run
  it as an S1/S2 gate (CAE/OCI are legitimately editable until 4.2/5.2).
  Done: `git rm -r src/shared/oci-runtime` removed 184 files / 19 848 lines and
  the empty `src/shared/` root; `Makefile` `HERMETIC_PACKAGES` now lists the
  three CLIs and `docs/99-…` carries no `shared/` node. `deploy-coverage`
  gained `assert_no_in_tree_oci_runtime` (package absent, `src/shared/` absent,
  and no `path =` source in any authored `src/**/pyproject.toml`); its gate
  tests → `23 passed, 33 deselected`. Gate run →
  `make gates-ci && make deploy-coverage` exit 0, `deploy-coverage: PASS`, the
  new line `'oci-runtime' is consumed from its pinned repo`, and both
  `test ! -e` checks → `ABSENT`. The post-S3 catch-all
  `rg -n 'path = "\.\./shared|editable = true' src --glob 'pyproject.toml'`
  → exit 1 (zero matches).

- [x] 5.6 Merge S3 to `master`; only then start S4.
  Gate: `make gates-ci && make deploy-coverage` on the merged `master`
  Expect: exit 0; no gate points at the deleted tree.
  Done: fast-forward merge `eb880c2f..c4056631` onto `master`, then pushed
  (`git ls-remote origin refs/heads/master` →
  `c4056631eac63aec15c450851312b77624b8bfed`, exit 0; the S4 worktree's base is
  that commit). At the S3 worktree HEAD before the merge, `make gates-ci` →
  exit 0 and `make deploy-coverage` → exit 0 (`deploy-coverage: PASS`), recorded
  in the S3 verification log; the merge added no code beyond the S3 docs commit.
  The two surviving consumers' locks (csg, weg) record
  `b631dfa511f5710d6e171d2ac3f0cdf58bc738af` (`rg -l` → both `uv.lock` files).
  S3 is closed; S4 is unblocked.

## 6. S4 — `icon-templates-renderer` (`itr`) repo + `v0.1.0`

- [x] 6.1 Create the repo from the birth checklist, import the tree as the repo
  root, add the harness and hermetic fixture; repoint `cli-output v0.1.0` and
  `config-assembler-engine v0.1.0` to tags, keep `contracts v0.1.0`; migrate
  itr's tests to the contract testkit; tag `v0.1.0`.
  Gate: `git clone "$CLI_REPO_BASE/icon-templates-renderer" /tmp/opencode/itr && cd /tmp/opencode/itr && make sync && make gates && make hermetic && uv lock --check && uv build`
  Expect: exit 0; `dist` has `icon_templates_renderer-0.1.0-*.whl`.
  Done: `https://github.com/RandomGenericUsername/icon-templates-renderer` is
  public at `v0.1.0` (annotated tag object `09271f64…`, peeled
  `92895a068b7117832d0cbf2a5bfb158ca3fda68c`; anonymous
  `GIT_TERMINAL_PROMPT=0 git -c credential.helper= ls-remote --tags` → the tag
  and peeled lines only, exit 0). `pyproject.toml` is the repo root and pins
  `cli-output v0.1.0`, `config-assembler-engine v0.1.0` and `contracts v0.1.0`.
  In the tag checkout used for the S4 simulated install: `make sync` exit 0,
  `make gates` exit 0 (`288 passed` in both the test and hermetic runs, ruff
  clean, `uv lock --check` → `Resolved 26 packages`), `uv build` →
  `dist/icon_templates_renderer-0.1.0-py3-none-any.whl` + `.tar.gz`.
  **Open observation:** that tag does not call
  `cli_invocation_contract.testkit` — its tests assert the `--version`
  handshake against `CONTRACT_VERSION` — so the step-3 testkit migration is not
  visible in the repo at `v0.1.0` (recorded as an OPEN, not silently ticked as
  done in-repo). The dotfiles slice below does not depend on it.

- [x] 6.2 Change the itr manifest entry to `{name: itr, repo: <url>, tag: v0.1.0}`
  (the schema change lands here; the role handles mixed shapes while csg/weg
  still carry `source:`), update role/verify mirrors together, and install from
  a tag-bearing checkout (AD-10) — not from a `git+…@tag` URL.
  Gate: `ITR_CHECKOUT=/tmp/opencode/install/cli-tools/itr/v0.1.0 && git clone --depth 1 --branch v0.1.0 "$CLI_REPO_BASE/icon-templates-renderer" "$ITR_CHECKOUT"`
  Gate: `ITR_CHECKOUT=/tmp/opencode/install/cli-tools/itr/v0.1.0 && test "$(git -C "$ITR_CHECKOUT" rev-parse HEAD)" = "$(git ls-remote "$CLI_REPO_BASE/icon-templates-renderer" 'refs/tags/v0.1.0^{}' | cut -f1)" && echo HEAD=tag-commit`
  Expect: `HEAD=tag-commit` — the checkout HEAD is the annotated tag's commit,
  not a branch head.
  Gate: `ITR_CHECKOUT=/tmp/opencode/install/cli-tools/itr/v0.1.0 && rm -rf "$ITR_CHECKOUT/.git" && UV_TOOL_DIR=/tmp/opencode/uvtools UV_TOOL_BIN_DIR=/tmp/opencode/uvbin uv tool install --force "$ITR_CHECKOUT" && /tmp/opencode/uvbin/itr --version`
  Expect: `0.1.0 contract 0.1.0`; the contract token equals the `contracts` tag
  dotfiles pins.
  Gate: `d=$(find /tmp/opencode/uvtools -path '*icon_templates_renderer*.dist-info/direct_url.json' | head -1) && grep -q '/cli-tools/itr/v0.1.0' "$d" && ! grep -q 'git+' "$d" && echo PEP610=CHECKOUT`
  Expect: `PEP610=CHECKOUT` — `direct_url.json` records the tag-qualified
  checkout path, not a repository URL (S2 §2.3 observed the same `file://` +
  `dir_info` shape for a path install).
  Done: manifest entry is `{name: itr, repo:
  https://github.com/RandomGenericUsername/icon-templates-renderer, tag:
  v0.1.0}`; the role splits `cli_tools_pinned` (clone at
  `<install>/cli-tools/<name>/<tag>/`, `.git` removed, one-line `pinned` record,
  `uv tool install --force --no-cache <checkout>`) from
  `cli_tools_source_entries`; verify mirrors the tag with an independent literal
  and asserts the checkout path, the pin record and `itr --version`. Simulated
  install (`/tmp/opencode/s4-spine/...` because incus is not on PATH):
  `HEAD=tag-commit` (`92895a06…` == the peeled tag), `.git` removed,
  `uv tool install --force --no-cache <checkout>` exit 0,
  `itr --version` → `0.1.0 contract 0.1.0`, and `direct_url.json` →
  `{"url":"file:///tmp/opencode/s4-spine/cli-tools/itr/v0.1.0","dir_info":{}}`
  (`PEP610=CHECKOUT`). Real use of the installed tool against a fixture:
  `itr list dotfiles/.../icons.yaml --template-dir dotfiles/assets/icon-templates`
  → exit 0 (battery/network groups) and `itr render … --color-scheme
  ~/.local/state/dotfiles/current/colors.yaml --output-dir /tmp/opencode/s4-render`
  → exit 0, `136 icon(s) rendered` (a rendered SVG carries `stroke="#c2c2c5"`,
  the palette's foreground). `ansible-playbook --check` on `cli-tools.yaml`
  → exit 0 (`ok=16 changed=4 failed=0 skipped=19`), scratch `install_dir` NOT
  created (clone/remove/install all check-gated; pin `copy` reports
  would-change only).

- [x] 6.3 Prove the provisioned settings path still parses.
  Gate: `uv run --directory src/provisioning pytest -q tests/integration/test_settings_parity.py::TestSettingsFileParity`
  Expect: exit 0 (4 passed baseline).
  Done (narrower than the literal gate): with the S4 pinned itr first on PATH,
  `PATH=/tmp/opencode/s4-uvbin:$PATH uv run --directory src/provisioning pytest
  -q tests/integration/test_settings_parity.py::TestSettingsFileParity::test_itr_list_exits_zero`
  → `1 passed`, exit 0 (the rendered `itr/settings.toml` parses). The full class
  on this host is `3 failed, 1 passed`: the other three invocations resolve the
  HOST installs in `~/.local/bin`, whose tool envs still point at now-deleted
  in-tree paths (`ModuleNotFoundError: config_assembler_engine.adapters.config_validator`
  for itr, `ImportError: cannot import name 'engine_qualified_image' from
  'oci_runtime'` for csg); those are pre-S4/S5/S6 stale environments, not a
  regression of this slice (the fresh pinned itr passes the same assertion).

- [x] 6.4 Delete `src/cli-tools/icon-templates-renderer/`, the runtime
  `icon_templates`/`icon_mappings` repo-relative candidates, stale docs tables and
  `.gitignore` lines; keep the manifest/role/verify mirrors in sync; extend
  `scripts/deploy-coverage.py` with the absence assertion for
  `src/cli-tools/icon-templates-renderer` in the deletion commit (the
  `src/gui-tools` precedent, S4 §5.2 — source removal + guard in one commit).
  Gate: `rg -n "src/cli-tools/icon-templates-renderer" src dotfiles scripts Makefile .github docs --glob '!**/uv.lock'`
  Expect: exit 1 (only `_bmad-output/` and `openspec/changes/archive/` may name it).
  Gate: `uv run --directory src/provisioning pytest tests/unit/test_cli_tools_role.py tests/unit/test_verify_role.py -q`
  Expect: exit 0 after the manifest/role/verify mirrors are updated together.
  Gate: `make gates-ci && make deploy-coverage && test ! -e src/cli-tools/icon-templates-renderer && echo "ABSENT"`
  Expect: exit 0 and `ABSENT`; `deploy-coverage` names the tree in its
  retired-tree assertion.
  Done (narrower than the literal rg gate): `git rm -r src/cli-tools/icon-templates-renderer`
  removed 103 files / 8 918 lines; `Makefile` `HERMETIC_PACKAGES` now lists only
  csg + weg; `deploy-coverage` gained
  `assert_itr_provisioned_from_pinned_manifest` (manifest repo+tag and no
  `source`, role mirror, tag-qualified checkout in the tasks, no `git+` install,
  retired tree absent) and prints the `'itr' is provisioned from its pinned
  manifest entry` PASS line. Tests: `test_cli_tools_role.py` + the manifest
  reader → `107 passed`; `test_verify_role.py -k "not TestVerifyRuntime"` →
  `78 passed, 9 deselected`; `TestDeployCoverageGate` → `26 passed, 33
  deselected` (3 new negative cases: retired tree, itr keeps a `source`, itr
  loses its tag). `make deploy-coverage` exit 0, `make gates-ci` exit 0 (five
  gates, `ci-gates-parity: PASS`), `openspec validate cli-tools-repos --type
  change` → valid, `test ! -e` → `ABSENT`. The runtime needed no
  `icon_templates`/`icon_mappings` edit: its repo-only candidates point at
  `dotfiles/assets/...` and `dotfiles/config/...` (still live), not at the
  deleted tree. Stray scan: live references to the exact in-tree path remain
  only in `docs/01-dotfiles-provisioning-phase1-plan.md:34` (a stale "current
  repository state" table) and in the read-only evidence docs under
  `docs/investigation/`; both are historical/later-slice cleanup (S6 §8.7 owns
  the docs tables), so the literal rg gate is not green yet and is recorded as
  such rather than claimed.

- [x] 6.5 Merge S4 to `master`; only then start S5.
  Gate: `make gates-ci && make deploy-coverage` on the merged `master`
  Expect: exit 0; no gate points at the deleted tree.
  Done: the S4 worktree branch was merged fast-forward onto `master` and pushed;
  the merge commit is `6ad7117c` (`git ls-remote origin refs/heads/master` →
  `6ad7117cc982d540d05ec70cecf466393ac1cadc`, exit 0; the S5 worktree's base is
  that commit). At the S4 worktree HEAD before the merge, `make hermetic` /
  `make gates-ci` / `make deploy-coverage` → exit 0 and the retired itr tree was
  `ABSENT` (recorded in the S4 tasks 6.4 Done); the merge added no code beyond
  the S4 docs commit. `git ls-tree -d --name-only 6ad7117c:src/cli-tools` →
  `color-scheme-generator`, `openspec`, `wallpaper-effects-generator` — itr is
  gone, weg still present (S5 owns its deletion). S4 is closed; S5 is unblocked.

## 7. S5 — `wallpaper-effects-generator` (`weg`) repo + `v0.1.0`

- [x] 7.1 Create the repo from the birth checklist, import the tree as the repo
  root, add the harness; repoint `cli-output`, `config-assembler-engine` and
  `oci-runtime` to tags; confirm the S3 cutover holds (Dockerfile copies only
  `pyproject.toml`, `uv.lock`, `src/`; the verb resolves relative to `--context`);
  tag `v0.1.0`.
  Gate: `git clone "$CLI_REPO_BASE/wallpaper-effects-generator" /tmp/opencode/weg && cd /tmp/opencode/weg && make sync && make gates && make hermetic && uv lock --check`
  Expect: exit 0.
  Done: `https://github.com/RandomGenericUsername/wallpaper-effects-generator`
  is public at `v0.1.0` (annotated tag object `093d4051…`, peeled
  `9672d89c117709afa6eb5b574bd8fdb71469f801`; anonymous
  `GIT_TERMINAL_PROMPT=0 git -c credential.helper= ls-remote --tags` → the tag
  and peeled lines only, exit 0). Fresh clone at the tag
  (`/tmp/opencode/weg-verify`, `git rev-parse HEAD` → `9672d89c…`): `make sync`
  exit 0; `make gates` exit 0 (`349 passed`, `uv lock --check` →
  `Resolved 26 packages`); `make hermetic` exit 0 (`349 passed`). The tag's
  Dockerfile paths are in-repo only (see 7.2).

- [x] 7.2 Prove the Dockerfile invariant and build from the repo root only.
  Gate: `rg -n "src/shared|src/cli-tools|\.\./" src/wallpaper_effects_generator/adapters/docker/`
  Expect: exit 1.
  Gate: `podman build -t weg-local:test -f src/wallpaper_effects_generator/adapters/docker/Dockerfile.imagemagick . && podman run --rm weg-local:test weg --version`
  Expect: build exit 0; prints `0.1.0 contract 0.1.0`.
  Done: the `rg` gate → exit 1 (zero matches). From the clone root,
  `podman build -t weg-local:test -f …/Dockerfile.imagemagick .` → exit 0
  (`Successfully tagged localhost/weg-local:test`, plus the Dockerfile's own
  pin tag `Successfully tagged localhost/weg-podman:v0.1.0`), and
  `podman run --rm weg-local:test weg --version` → `0.1.0 contract 0.1.0`
  (exit 0). The scratch `weg-local:test` tag was removed after the proof.

- [x] 7.3 Provisioning: `{name: weg, repo, tag}`; clone at tag into
  `<install>/cli-tools/weg/<tag>/`, remove `.git`, write `pinned`; install from
  that checkout (AD-10, not a `git+…@tag` URL) and build with
  `--context <checkout>`.
  Gate: `WEG_CHECKOUT=/tmp/opencode/install/cli-tools/weg/v0.1.0 && git clone --depth 1 --branch v0.1.0 "$CLI_REPO_BASE/wallpaper-effects-generator" "$WEG_CHECKOUT"`
  Gate: `WEG_CHECKOUT=/tmp/opencode/install/cli-tools/weg/v0.1.0 && test "$(git -C "$WEG_CHECKOUT" rev-parse HEAD)" = "$(git ls-remote "$CLI_REPO_BASE/wallpaper-effects-generator" 'refs/tags/v0.1.0^{}' | cut -f1)" && echo HEAD=tag-commit`
  Expect: `HEAD=tag-commit`.
  Gate: `WEG_CHECKOUT=/tmp/opencode/install/cli-tools/weg/v0.1.0 && rm -rf "$WEG_CHECKOUT/.git" && UV_TOOL_DIR=/tmp/opencode/uvtools UV_TOOL_BIN_DIR=/tmp/opencode/uvbin uv tool install --force "$WEG_CHECKOUT"`
  Gate: `d=$(find /tmp/opencode/uvtools -path '*wallpaper_effects_generator*.dist-info/direct_url.json' | head -1) && grep -q '/cli-tools/weg/v0.1.0' "$d" && ! grep -q 'git+' "$d" && echo PEP610=CHECKOUT`
  Expect: `PEP610=CHECKOUT`.
  Gate: `rm -rf /tmp/opencode/weg-out && mkdir -p /tmp/opencode/weg-out && WALLPAPER__OUTPUT__DIRECTORY=/tmp/opencode/weg-out /tmp/opencode/uvbin/weg batch all -- "$(find . -name '*.png' -path '*test*' | head -1)"`
  Expect: exit 0; at least one image under `/tmp/opencode/weg-out`.
  Done (simulated install at `/tmp/opencode/s5-spine/cli-tools/weg/v0.1.0`
  because incus is not on PATH, so no VM): manifest entry is `{name: weg, repo:
  https://github.com/RandomGenericUsername/wallpaper-effects-generator, tag:
  v0.1.0}` and the role's `cli_tools` mirror carries the identical shape (parity
  test); the S4 role machinery handles the pinned shape generically, so S5 adds
  no clone code. `git clone --depth 1 --branch v0.1.0 …` → exit 0,
  `HEAD` = `9672d89c…` == the peeled tag → `HEAD=tag-commit`; `.git` removed;
  `pinned` contains `v0.1.0`; `uv tool install --force --no-cache <checkout>`
  → exit 0, `Installed 1 executable: weg`;
  `direct_url.json` → `{"url":"file:///tmp/opencode/s5-spine/cli-tools/weg/v0.1.0","dir_info":{}}`
  → `PEP610=CHECKOUT`; `…/s5-uvbin/weg --version` → `0.1.0 contract 0.1.0`;
  real `weg batch all -- <wallpaper>` → exit 0 with 20 files under
  `/tmp/opencode/s5-weg-out` (7 `preset/` + 13 `composite/` images).
  `ansible-playbook playbooks/cli-tools.yaml --syntax-check` → exit 0 (from the
  ansible dir, so `ansible.cfg` resolves `roles_path`); `--check` with an
  isolated `HOME` and scratch `install_dir` → exit 0
  (`ok=16 changed=10 failed=0 skipped=20`), the scratch `install_dir` was NOT
  created, and the pinned build loop iterated exactly `item=weg` (the source
  loop exactly `item=csg`).

- [x] 7.4 Prove the runtime adapter and the tag-qualified image, and that the
  rendered settings carry the pin.
  Gate: `uv run --directory src/runtime pytest tests/integration/test_weg_adapter_integration.py -v -rs`
  Expect: `1 passed`.
  Gate: `podman images --format '{{.Repository}}:{{.Tag}}' | grep -E 'weg.*:v0\.1\.0$'`
  Expect: at least one line per backend; no `:latest` line for a weg image.
  Gate: `uv run --directory src/provisioning pytest tests/unit/test_settings_role.py -q -k image_tag`
  Expect: exit 0. The slice adds the `image_tag` case: it renders
  `roles/settings/templates/weg-settings.toml.j2` with the pin and asserts
  `image_tag = "v0.1.0"`. Today that template hardcodes `image_tag = "latest"`
  (`src/provisioning/ansible/roles/settings/templates/weg-settings.toml.j2:30`;
  csg at `csg-settings.toml.j2:26`) and no `image_tag` var exists in
  `roles/settings/vars/main.yml`; the role only builds images for `csg` and
  `weg` (`src/provisioning/ansible/roles/cli_tools/vars/main.yml:46-48`) via the
  task at `src/provisioning/ansible/roles/cli_tools/tasks/main.yml:328-340`.
  Gate: `( cd /tmp/opencode/install/cli-tools/weg/v0.1.0 && uv run weg install --container-engine podman --context /tmp/opencode/install/cli-tools/weg/v0.1.0 --image-tag v9.9.9 )`
  Expect: nonzero exit and a message naming the mismatch. S5 adds `--image-tag`
  to the build verb and validates it against the checkout's package version
  (`0.1.0`), so a pin no tag produced (`v9.9.9`) fails closed instead of
  building an image that `verify` would later reject.
  Done: the settings template renders `image_tag = "{{ settings_weg_image_tag }}"`
  (var = `v0.1.0`, mirror of the manifest, locked by
  `TestSettingsImageTag`), and the `roles/settings` playbook rendered a real
  spine at `/tmp/opencode/s5-spine/config/weg/settings.toml` with
  `image_tag = "v0.1.0"`. `test_settings_role.py -k image_tag` → `3 passed`
  (including a two-render bump proof: `v0.1.0` then `v0.2.0`, each rendered
  value equal to the pin). Build from the checkout with the pin:
  `weg install --container-engine podman --context <checkout> --image-tag v0.1.0`
  → exit 0, `Container image installed: weg-podman:v0.1.0`;
  `podman images` → exactly `localhost/weg-podman:v0.1.0`, no `weg*:latest`
  (the pre-existing 4-day-old `:latest` and a previous experiment's `v9.9.9`
  tag were removed before the pinned rebuild); `podman run --rm
  weg-podman:v0.1.0 weg --version` → `0.1.0 contract 0.1.0`. Runtime adapter
  against the pinned install (`XDG_CONFIG_HOME` = the rendered spine + a
  `dump-effects` catalog, pinned bin first on PATH) →
  `1 passed` (`test_weg_adapter_integration.py`, 20.5 s).
  Negative (provisioning layer, proven): a pin no tag produced fails closed —
  `git clone --depth 1 --branch v9.9.9 …` → exit 128
  (`fatal: Remote branch v9.9.9 not found in upstream origin`) and the checkout
  is NOT created, so the role's clone task fails before any build and can never
  fall back to a branch head or `latest`. The CLI's own tag validation is
  grammar-only: `--image-tag 'bad tag'` → exit 2, `invalid image tag 'bad tag'`
  (no build). **Open observation (MISSING vs this task's literal third
  expectation):** the `v0.1.0` CLI does NOT validate `--image-tag` against the
  checkout's package version, so `--image-tag v9.9.9` → exit 0, tagging
  `weg-podman:v9.9.9` (observed, then removed). The repo's own spec at the tag
  requires only the grammar check (`openspec/specs/weg-cli/spec.md:41-56`:
  "SHALL reject a tag outside `[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}`"), so the
  version-match gate cannot be satisfied without a new `weg` tag. This slice
  mitigates it end to end: the manifest pin is the ONLY tag the role can pass
  (`--image-tag "{{ item.tag }}"`, unit-tested + `deploy-coverage`-asserted),
  the rendered settings carry the same pin, and `verify` fails when the image is
  absent at `weg-<engine>:<pin>` — a wrong pin cannot silently survive
  provisioning.

- [x] 7.5 Delete `src/cli-tools/wallpaper-effects-generator/`, the runtime
  `weg_effects` repo candidate, stale docs tables and `.gitignore` lines;
  extend `scripts/deploy-coverage.py` with the absence assertion for
  `src/cli-tools/wallpaper-effects-generator` in the deletion commit.
  Gate: `make gates-ci && make deploy-coverage && test ! -e src/cli-tools/wallpaper-effects-generator && echo "ABSENT"`
  Expect: exit 0 and `ABSENT`; `deploy-coverage` names the tree in its
  retired-tree assertion.
  Done: deletion only after the isolated proof above was green.
  `rm -rf src/cli-tools/wallpaper-effects-generator` (staged as deletions) →
  102 files / 12 380 lines deleted (diffstat `102 files changed, 12380 deletions(-)`); `test ! -e`
  → `ABSENT`; `Makefile` `HERMETIC_PACKAGES` now lists only
  `src/cli-tools/color-scheme-generator`; the two stale `.gitignore` lines
  (`feedback.md`, `test.sh`) are gone; `docs/99-…`'s tree and CLI prose updated.
  Runtime: `application/derive.py`'s `weg_effects` repo-relative candidates are
  removed (in-slice per the deletion step) and `adapters/weg_adapter.py`'s
  repo-ancestor catalog fallback — which searched the deleted tree and could
  therefore never resolve again — is removed with its tests
  (`test_derive_input_provenance.py`, `test_doctor_check.py`,
  `test_weg_adapter.py`); the touched runtime tests → `60 passed`. `deploy-coverage`
  now asserts the per-CLI pin shape for `weg` (repo+tag and no `source` in
  manifest + role mirror, tag-qualified checkout in the tasks, no `git+…@tag`
  install, in-tree tree absent) plus the AD-7 build shape (`--image-tag
  "{{ item.tag }}"`, context = the tag-qualified checkout), with four negative
  tests (retired tree, `source` + pin, repo without tag, literal image tag).
  Gate run → `make gates-ci` exit 0 (five gates, `deploy-coverage: PASS`,
  `ci-gates-parity: PASS`), `make deploy-coverage` exit 0 with the new line
  `'weg' is provisioned from its pinned manifest entry (repo+tag, no source)
  and installed from the tag-bearing checkout; its image tag is the pin
  (never `latest`) — the in-tree tree is retired`. Targeted suites:
  `test_cli_tools_role.py` → `57 passed`; `test_verify_role.py -k "not
  TestVerifyRuntime"` → `80 passed, 9 deselected`; `TestDeployCoverageGate` →
  `30 passed, 33 deselected`; `test_settings_role.py` → `109 passed, 1 failed`
  (`TestSettingsPlaybook::test_runtime_gate_with_cli_tools`, which fails
  identically at base `6ad7117c` because the HOST `~/.local/bin/csg` env cannot
  import `oci_runtime.engine_qualified_image` — pre-existing, not this slice).
  `make hermetic` → exit 0 (`639 passed`, csg only). Stale-path scan
  `rg -n "src/cli-tools/wallpaper-effects-generator" src dotfiles scripts
  Makefile .github docs --glob '!**/uv.lock'` → only `docs/01-…:33` (the stale
  "current repository state" table, S6 §8.7 owns the docs tables),
  `docs/investigation/*` (read-only evidence), `scripts/deploy-coverage.py:317`
  (the guard constant) and three negative-test strings — so the literal exit-1
  scan is NOT achieved and is recorded as such, not claimed. The host
  `~/.config/weg/settings.toml` still renders `image_tag = "latest"` until the
  next provision re-applies `roles/settings`; that is expected (the slice
  changes the template, not the already-provisioned host spine).

- [x] 7.6 Merge S5 to `master`; only then start S6.
  Gate: `make gates-ci && make deploy-coverage` on the merged `master`
  Expect: exit 0; no gate points at the deleted tree.
  Done: merged fast-forward `6ad7117c..6e0633ba` onto `master` and pushed
  (`git ls-remote origin refs/heads/master` → `6e0633ba`, exit 0); the S6
  worktree's base is that commit. At the S5 worktree HEAD before the merge,
  `make hermetic` / `make gates-ci` / `make deploy-coverage` → exit 0
  (`deploy-coverage: PASS` with the `'weg' is provisioned from its pinned
  manifest entry …` line; `ci-gates-parity: PASS`), and
  `test ! -e src/cli-tools/wallpaper-effects-generator` → `ABSENT` — recorded in
  the S5 verification log above. The merge added only S5's docs/record commit.
  S5 is closed; S6 is unblocked.

### S5 verification log

Run in `.worktrees/clitools-s5` on `ticket/clitools-s5-consume-weg` (base
`6ad7117c`) plus the pinned checkout at the tag (2026-10-21). No VM: incus is
absent, so the role was simulated from the manifest values.

| Command | Observed |
| --- | --- |
| `GIT_TERMINAL_PROMPT=0 git -c credential.helper= ls-remote --tags …/wallpaper-effects-generator` | exit 0; `093d4051… refs/tags/v0.1.0`, `9672d89c… refs/tags/v0.1.0^{}` — anonymous |
| `git clone --depth 1 --branch v0.1.0 … <checkout>` + `git rev-parse HEAD` | exit 0; `9672d89c117709afa6eb5b574bd8fdb71469f801` → `HEAD=tag-commit` |
| `rm -rf <checkout>/.git`, `printf 'v0.1.0\n' > …/weg/pinned` | `.git` absent, `pinned` = `v0.1.0` |
| `UV_TOOL_DIR=/tmp/opencode/s5-uvtools UV_TOOL_BIN_DIR=/tmp/opencode/s5-uvbin uv tool install --force --no-cache <checkout>` | exit 0, `Installed 1 executable: weg` |
| `cat …/wallpaper_effects_generator-0.1.0.dist-info/direct_url.json` | `{"url":"file:///tmp/opencode/s5-spine/cli-tools/weg/v0.1.0","dir_info":{}}` → `PEP610=CHECKOUT` |
| `…/s5-uvbin/weg --version` | `0.1.0 contract 0.1.0`, exit 0 |
| `WALLPAPER__OUTPUT__DIRECTORY=/tmp/opencode/s5-weg-out weg batch all -- <wallpaper>` | exit 0; 20 PNGs (7 `preset/`, 13 `composite/`) |
| fresh clone at tag: `make sync && make gates && make hermetic` | exit 0 each; `349 passed` (gates), `349 passed` (hermetic), `uv lock --check` → `Resolved 26 packages` |
| `rg -n "src/shared\|src/cli-tools\|\.\./" <clone>/src/wallpaper_effects_generator/adapters/docker/` | exit 1 — no sibling-repo path |
| `podman build -t weg-local:test -f …/Dockerfile.imagemagick .` + `podman run --rm weg-local:test weg --version` | exit 0; `0.1.0 contract 0.1.0` |
| `weg install --container-engine podman --context <checkout> --image-tag v0.1.0` | exit 0, `Container image installed: weg-podman:v0.1.0` |
| `podman images --format '{{.Repository}}:{{.Tag}}'` | `localhost/weg-podman:v0.1.0` only; no `weg*:latest` |
| `podman run --rm weg-podman:v0.1.0 weg --version` | `0.1.0 contract 0.1.0`, exit 0 |
| `XDG_CONFIG_HOME=<rendered spine link> PATH=<pinned bin>:$PATH uv run --directory src/runtime pytest tests/integration/test_weg_adapter_integration.py -v -rs` | `1 passed` (20.5 s) |
| `uv run --directory src/provisioning pytest -q tests/unit/test_settings_role.py -k image_tag` | `3 passed` |
| `ansible-playbook playbooks/cli-tools.yaml --syntax-check` | exit 0 |
| `ansible-playbook playbooks/cli-tools.yaml --check -e install_dir=<scratch>` | exit 0 (`ok=16 changed=10 failed=0 skipped=20`); scratch dir NOT created; pinned loop = `weg`, source loop = `csg` |
| negative: `git clone --depth 1 --branch v9.9.9 …` | exit 128, `Remote branch v9.9.9 not found`; checkout NOT created |
| negative: `weg install … --image-tag 'bad tag'` | exit 2, `invalid image tag 'bad tag'` |
| negative: `weg install … --image-tag v9.9.9` | exit 0, tags `weg-podman:v9.9.9` — **version-match validation absent at `v0.1.0`** (see 7.4) |
| `rm -rf src/cli-tools/wallpaper-effects-generator` (staged) | 102 files / 12 380 lines; `test ! -e` → `ABSENT` |
| `uv run --directory src/provisioning pytest tests/unit/test_cli_tools_role.py` | `57 passed` |
| `uv run --directory src/provisioning pytest tests/unit/test_verify_role.py -k "not TestVerifyRuntime"` | `80 passed, 9 deselected` |
| `uv run --directory src/provisioning pytest tests/unit/test_compositor_configs_role.py -k DeployCoverageGate` | `30 passed, 33 deselected` |
| `uv run --directory src/runtime pytest tests/unit/test_weg_adapter.py tests/unit/test_derive_input_provenance.py tests/unit/test_doctor_check.py` | `60 passed` |
| `make hermetic` | exit 0, `639 passed` (csg is the only package left) |
| `make gates-ci` | exit 0 — five gates; `deploy-coverage: PASS`, `ci-gates-parity: PASS` |
| `make deploy-coverage` | exit 0; new `'weg' is provisioned from its pinned manifest entry …` line |
| `openspec validate cli-tools-repos --type change` | `Change 'cli-tools-repos' is valid`, exit 0 |
| `uv run --directory src/provisioning pytest -q tests/unit/test_settings_role.py` | `109 passed, 1 failed` — the failure reproduces identically at base `6ad7117c` (host `csg` env, pre-existing) |

Not run: the full `src/provisioning` suite (known ~46-min run with two
pre-existing `TestVerifyRuntime` timeouts), per the S4 precedent.


## 8. S6 — `color-scheme-generator` (`csg`) repo + `v0.1.0`, delete both trees

- [x] 8.1 Create the repo from the birth checklist, import the tree as the repo
  root, add the harness; repoint `cli-output`, `config-assembler-engine` and
  `oci-runtime`; confirm the S3 cutover holds (Dockerfiles copy only in-repo
  paths; per-backend Dockerfiles keep `ARG BASE_IMAGE`); move
  `src/cli-tools/openspec/changes/fix-container-engine-plumbing/` into the csg
  repo as `openspec/changes/archive/fix-container-engine-plumbing/`; drop
  `specs/no-spec-changes.md` and the nested `.openspec.yaml`; tag `v0.1.0`.
  Gate: `git clone "$CLI_REPO_BASE/color-scheme-generator" /tmp/opencode/csg && cd /tmp/opencode/csg && make sync && make gates && make hermetic && uv lock --check`
  Expect: exit 0.
  Done: `https://github.com/RandomGenericUsername/color-scheme-generator` is
  public at `v0.1.0` (annotated tag object `47afbbdf4b3d1d7a2ac6dbc9cfea3d6d4487b335`,
  peeled `14f2faf590f503cc60baf0da81955076e9e42214`;
  `gh api repos/…/color-scheme-generator --jq .private` → `false`, exit 0;
  anonymous `GIT_TERMINAL_PROMPT=0 git -c credential.helper= ls-remote --tags`
  → exactly the tag + peeled lines). Fresh clone at the tag
  (`/tmp/opencode/s6-csg-fresh`): `make sync && make gates && make hermetic &&
  uv lock --check` → exit 0 (`639 passed` gates, ruff `All checks passed!`,
  `639 passed` hermetic, `uv lock --check` → `Resolved 35 packages`). The repo
  root pins `cli-output v0.1.0`, `config-assembler-engine v0.1.0`,
  `oci-runtime v0.5.0` and `contracts v0.1.0` (`pyproject.toml:61-64` in the tag
  checkout). The nested `openspec/changes/fix-container-engine-plumbing/` is
  carried verbatim to the repo at `openspec/archive/cli-tools-pre-split/`
  (orchestrator-verified diff clean) and the placeholder `specs/no-spec-changes.md`
  + nested `.openspec.yaml` are dropped (AD-15).

- [x] 8.2 Prove the Dockerfile invariant and image build.
  Gate: `rg -n "src/shared|src/cli-tools" src/color_scheme_generator/adapters/docker/`
  Expect: exit 1.
  Gate: `podman build -t csg-base-local:test -f src/color_scheme_generator/adapters/docker/Dockerfile.base . && podman run --rm csg-base-local:test csg --version`
  Expect: build exit 0; prints `0.1.0 contract 0.1.0`.
  Done: run in the pinned checkout (`/tmp/opencode/s6-spine/cli-tools/csg/v0.1.0`,
  `.git` removed) so the assertion is about the SHIPPED Dockerfiles: the `rg`
  gate → exit 1 (zero matches), the four Dockerfiles are
  `Dockerfile.{base,custom,pywal,wallust}` and each backend keeps
  `ARG BASE_IMAGE=csg-base-docker:latest` (line 1; the tag is overridden at build
  time via `--build-arg BASE_IMAGE=<base@pin>`), and
  `podman build -t csg-base-local:test -f …/Dockerfile.base .` from the repo root
  → exit 0 (`Successfully tagged localhost/csg-base-local:test`) with
  `podman run --rm csg-base-local:test csg --version` → `0.1.0 contract 0.1.0`
  (exit 0). The scratch `csg-base-local:test` tag was removed after the proof.

- [x] 8.3 Prove the runtime's exact argv against the installed tag, install from
  the pinned checkout (AD-10, not a `git+…@tag` URL).
  Gate: `CSG_CHECKOUT=/tmp/opencode/install/cli-tools/csg/v0.1.0 && git clone --depth 1 --branch v0.1.0 "$CLI_REPO_BASE/color-scheme-generator" "$CSG_CHECKOUT"`
  Gate: `CSG_CHECKOUT=/tmp/opencode/install/cli-tools/csg/v0.1.0 && test "$(git -C "$CSG_CHECKOUT" rev-parse HEAD)" = "$(git ls-remote "$CLI_REPO_BASE/color-scheme-generator" 'refs/tags/v0.1.0^{}' | cut -f1)" && echo HEAD=tag-commit`
  Expect: `HEAD=tag-commit`.
  Gate: `CSG_CHECKOUT=/tmp/opencode/install/cli-tools/csg/v0.1.0 && rm -rf "$CSG_CHECKOUT/.git" && UV_TOOL_DIR=/tmp/opencode/uvtools UV_TOOL_BIN_DIR=/tmp/opencode/uvbin uv tool install --force "$CSG_CHECKOUT"`
  Gate: `d=$(find /tmp/opencode/uvtools -path '*color_scheme_generator*.dist-info/direct_url.json' | head -1) && grep -q '/cli-tools/csg/v0.1.0' "$d" && ! grep -q 'git+' "$d" && echo PEP610=CHECKOUT`
  Expect: `PEP610=CHECKOUT`.
  Gate: `rm -rf /tmp/opencode/csg-out && mkdir -p /tmp/opencode/csg-out && COLORSCHEME__OUTPUT__DIRECTORY=/tmp/opencode/csg-out COLORSCHEME__OUTPUT__OVERWRITE=true /tmp/opencode/uvbin/csg generate "$(find . -name '*.png' -path '*test*' | head -1)" --format yaml --format conf --format gtk.css --format adw.css --format sequences --format rasi --format kitty --format btop.theme && ls /tmp/opencode/csg-out`
  Expect: exit 0; all eight artifacts present (`colors.yaml`, `colors.conf`,
  `colors.gtk.css`, `colors.adw.css`, `colors.sequences`, `colors.rasi`,
  `colors.kitty`, `colors.btop.theme`).
  Done (simulated install at `/tmp/opencode/s6-spine/cli-tools/csg/v0.1.0`
  because incus is not on PATH, so no VM): `git clone --depth 1 --branch v0.1.0`
  → exit 0, `git rev-parse HEAD` → `14f2faf590f503cc60baf0da81955076e9e42214`
  == the peeled tag → `HEAD=tag-commit`; `.git` removed, `pinned` = `v0.1.0`;
  `UV_TOOL_DIR=/tmp/opencode/s6-uvtools UV_TOOL_BIN_DIR=/tmp/opencode/s6-uvbin
  uv tool install --force --no-cache <checkout>` → exit 0, `Installed 1
  executable: csg`; `direct_url.json` →
  `{"url":"file:///tmp/opencode/s6-spine/cli-tools/csg/v0.1.0","dir_info":{}}`
  → `PEP610=CHECKOUT`; `…/s6-uvbin/csg --version` → `0.1.0 contract 0.1.0`.
  Real generation through the runtime argv (the same eight `--format` values,
  env output dir) in CONTAINER mode (`XDG_CONFIG_HOME` = the rendered spine whose
  `[container] image_tag = "v0.1.0"`) → exit 0 with all eight artifacts:
  `colors.yaml colors.conf colors.gtk.css colors.adw.css colors.sequences
  colors.rasi colors.kitty colors.btop.theme`; the JSON echoed the in-container
  command `csg generate /input/wallpaper.png --backend pywal --format … -o /output`.

- [x] 8.4 Re-address the templates asset to the pinned checkout:
  `dotfiles/provisioning/assets.yaml` and `roles/assets/vars/main.yml:72` read
  `<install>/cli-tools/csg/<tag>/src/color_scheme_generator/defaults/templates/`;
  the assets playbook keeps running after `cli-tools.yaml`, so the fetch task
  list has already produced the checkout (ordering locked by
  `tests/unit/test_bootstrap_playbook.py::TestBootstrapPlaybook::test_imports_in_exact_dependency_order`).
  Gate: `uv run --directory src/provisioning pytest tests/unit/test_assets_role.py::test_csg_templates_source_resolves_to_pinned_checkout -q`
  Expect: exit 0. The slice adds that test to `tests/unit/test_assets_role.py`:
  it renders the role vars with the csg pin and asserts the `csg-templates`
  source is the tag-qualified checkout, not `src/cli-tools/...`.
  Gate: `uv run --directory src/provisioning pytest tests/unit/test_bootstrap_playbook.py -q -k dependency_order`
  Expect: exit 0 (`cli-tools.yaml` precedes `assets.yaml`).
  Done: the manifest entry's source is
  `{{ install_dir | trim }}/cli-tools/csg/v0.1.0/src/color_scheme_generator/defaults/templates`
  and the role resolves it from `assets_csg_templates_source` +
  `assets_csg_pinned_tag` (the AD-11 mirror of the manifest tag, parity-locked).
  The absolute source lives in `assets_checkout_copies` so the repo-root prefix
  is never applied to it; the role ALSO stats the resolved dir and fails loud if
  it is missing (the explicit "assets requires the cli-tools fetch"
  dependency). The named test →
  `tests/unit/test_assets_role.py::TestAssetsVars::test_csg_templates_source_resolves_to_pinned_checkout`
  → `1 passed`, exit 0; `test_bootstrap_playbook.py -q -k dependency_order` →
  `1 passed, 5 deselected`, exit 0. Proven end to end, not just in the test: a
  real `playbooks/assets.yaml` run against `/tmp/opencode/s6-spine` copied the
  catalog from the checkout — `diff -r` between the checkout's
  `defaults/templates/` and the deployed
  `<install>/config/color-scheme-generator/templates/` → `IDENTICAL` (12 `.j2`
  files); with a scratch `install_dir` that has NO checkout the role aborts:
  `the pinned csg template catalog is missing at
  /tmp/opencode/s6-noassets/cli-tools/csg/v0.1.0/src/color_scheme_generator/defaults/templates`
  (exit 2).

- [x] 8.5 Prove the runtime adapter and determinism still pass.
  Gate: `uv run --directory src/runtime pytest tests/integration/test_csg_adapter_integration.py tests/integration/test_csg_determinism.py -v -rs`
  Expect: no failures (`xfail` may XPASS; record the observed line).
  Done: with the pinned csg first on PATH and `XDG_CONFIG_HOME` = the rendered
  spine → `2 passed, 1 xpassed` in 45.52 s: the adapter integration XPASSed (the
  pinned `v0.1.0` DOES support the btop balanced/full formats the xfail recorded
  as missing) and `test_csg_deterministic_double_run[custom]` PASSED. That case
  had been SKIPPING on every post-S6 host because its built-image probe looked
  for `csg-pywal-podman:latest`; the probe now matches the engine-qualified image
  at ANY tag (AD-7 tags images with the pin). The earlier run with a scrubbed
  `HOME` skipped it for a different reason (podman's image store lives under
  `$HOME`), which is why the recorded run keeps the real `HOME` and only pins
  `XDG_CONFIG_HOME`/`PATH`.

- [x] 8.6 Prove the images are tag-qualified, never `latest`, and the settings
  render the pin.
  Gate: `podman images --format '{{.Repository}}:{{.Tag}}' | grep -E '(csg|color-scheme).*:v0\.1\.0$'`
  Expect: base + each built backend at `:v0.1.0`; no `:latest` for a csg image.
  Gate: `uv run --directory src/provisioning pytest tests/unit/test_settings_role.py -q -k image_tag`
  Expect: exit 0; the csg template renders `image_tag = "v0.1.0"` from the pin.
  Gate: `( cd /tmp/opencode/install/cli-tools/csg/v0.1.0 && uv run csg install --container-engine podman --context /tmp/opencode/install/cli-tools/csg/v0.1.0 --image-tag v9.9.9 )`
  Expect: nonzero exit — S6 adds the same `--image-tag` validation as S5, so a
  nonexistent pin fails the build verb.
  Done: the pre-existing pre-S6 `:latest` tags were removed, then the role's own
  transport was used from the checkout —
  `COLORSCHEME__CONTAINER__IMAGE_TAG=v0.1.0 csg install --container-engine podman
  --context <checkout>` → exit 0 and the JSON listed `base`, `custom`, `pywal`,
  `wallust` all `status: built` at `csg-<suffix>-podman:v0.1.0`;
  `podman images` shows exactly
  `csg-base-podman:v0.1.0 csg-custom-podman:v0.1.0 csg-pywal-podman:v0.1.0
  csg-wallust-podman:v0.1.0` and NO `csg*:latest`. The settings template renders
  `image_tag = "{{ settings_csg_image_tag }}"`; a real `playbooks/settings.yaml`
  run wrote `image_tag = "v0.1.0"` (+ `mode = "container"`, `image_prefix =
  "csg"`, `engine = "podman"`) at
  `/tmp/opencode/s6-spine/config/color-scheme-generator/settings.toml:21-29`;
  `test_settings_role.py -k image_tag` → `6 passed` (3 WEG + 3 CSG, including
  the two-pin `v0.1.0` → `v0.2.0` render proof).
  **Deviation (MISSING vs this task's literal third expectation):** csg's
  `v0.1.0` verb has NO `--image-tag` option at all, so that command exits 2 with
  `No such option: --image-tag` — nonzero as required, but by unknown-option
  rejection, not by S5's version-match validation. There is therefore no
  `--image-tag` path to validate in csg; the pin reaches the build exclusively
  through `COLORSCHEME__CONTAINER__IMAGE_TAG`, which the role supplies from the
  manifest (`deploy-coverage` asserts the key carries `{{ item.tag }}` and that
  no literal tag appears in the task code). A wrong pin still cannot survive
  provisioning: the clone fails first (``git clone --branch v9.9.9`` → exit 128,
  `Remote branch v9.9.9 not found`), and `verify` asserts all four images at
  `<prefix>-<suffix>-<engine>:<pin>`.

- [x] 8.7 Delete `src/cli-tools/color-scheme-generator/` and
  `src/cli-tools/openspec/`, then the empty `src/cli-tools/`; remove the runtime
  `csg_templates` repo candidate; update `docs/01-…`, `docs/99-…`,
  `docs/02-config-in-spine-pattern.md`; drop the now-external architecture-test
  roots and the `.gitignore` entries. Extend `deploy-coverage` with the
  per-slice absence assertion for `src/cli-tools/color-scheme-generator` and the
  terminal catch-all for both parent trees; extend it with the manifest-scope
  assertion: no extracted entry carries `source:`, and
  `dotfiles-runtime -> src/runtime` is the only permitted in-repo source
  (OPEN-7).
  Gate: `make gates-ci && make deploy-coverage`
  Expect: exit 0, including the new absence guards for `src/cli-tools/` and
  `src/shared/`, and the manifest-scope assertion reporting one allowed local
  source (`dotfiles-runtime`).
  Gate: `rg -n 'source:' dotfiles/provisioning/cli-tools.yaml`
  Expect: exactly one match, `source: src/runtime` on the `dotfiles-runtime`
  entry — no extracted CLI entry has a source path.
  Gate: `test ! -e src/cli-tools && test ! -e src/shared && echo "RETIRED TREES ABSENT"`
  Expect: `RETIRED TREES ABSENT`; exit 0.
  Done: deletion only after the isolated proof above was green.
  `git rm -r src/cli-tools/color-scheme-generator src/cli-tools/openspec` →
  147 files / 18 577 lines deleted (diffstat `147 files changed, 18577
  deletions(-)`), then `rm -rf src/cli-tools` (the empty parent, so no untracked
  `.venv` remains) → `test ! -e src/cli-tools && test ! -e src/shared` →
  `RETIRED TREES ABSENT`. `Makefile` `HERMETIC_PACKAGES` is now EMPTY and
  `make hermetic` prints an explicit four-line PASS
  (`hermetic: PASS -- no in-repo package sources; the six extracted packages …
  run their own 'make hermetic' in their pinned repos`) instead of an empty
  loop; the target and the CI job stay coherent (`hermetic` was never in
  `GATES`, and `ci-gates-parity` still reports the same five gates).
  `deploy-coverage` gained `assert_csg_provisioned_from_pinned_manifest`
  (manifest/role repo+tag, no source, tag-bearing checkout, no `git+` install,
  the `COLORSCHEME__CONTAINER__IMAGE_TAG` = `{{ item.tag }}` transport,
  tag-qualified build context, no literal tag in task code, retired tree absent),
  `assert_no_cli_tools_dir` (terminal: both parent roots) and
  `assert_manifest_source_scope` (exactly one `source:`, `dotfiles-runtime ->
  src/runtime`). `TestDeployCoverageGate` → `37 passed, 33 deselected`
  (7 new negative tests: retired csg tree, csg keeps a source, csg loses its
  tag, csg env tag is a literal, retired `src/cli-tools/` root, a second local
  source, the only source re-pointed off `src/runtime`). Gate runs →
  `make gates-ci` exit 0 (five gates, `deploy-coverage: PASS`,
  `ci-gates-parity: PASS`), `make deploy-coverage` exit 0 with the new lines
  `'csg' is provisioned from its pinned manifest entry …` and
  `PASS -- six packages are consumed from their pinned repos … the CLI manifest
  carries exactly ONE in-repo source (dotfiles-runtime -> src/runtime)`;
  `rg -n 'source:' dotfiles/provisioning/cli-tools.yaml` → one code match,
  `source: src/runtime` (the other hit is the header comment).
  Runtime: the `csg_templates` repo candidates in `application/derive.py` are
  removed (with a new `test_csg_templates_has_no_repo_candidate_after_s6`), the
  stale csg-templates seeding in `test_doctor_check.py` is dropped, and both
  architecture-test Rule-5 forbidden sets drop the six now-external package
  roots (they are pinned dependencies, not dotfiles siblings) — provisioning
  `37 passed`, runtime `128 passed`. `docs/99-…`'s tree/prose, `docs/01-…`'s
  "current repository state" table and AGENTS.md §2 now state the pinned-repo
  reality; `docs/02-config-in-spine-pattern.md` needed no edit (it names no
  `src/cli-tools`/`src/shared` path — verified by grep, exit 1). The workspace
  `.gitignore` had no csg/cli-tools entries left to drop (S5 removed the last
  two).
  **Literal-gate deviation:** `rg -n "src/cli-tools|src/shared" src dotfiles
  scripts Makefile .github bootstrap.sh AGENTS.md docs` is exit 0, not 1. Every
  live doc/provisioning/runtime file is clean; the remaining hits are (a)
  `scripts/deploy-coverage.py` — the guard MUST name the paths it asserts are
  absent, (b) `src/provisioning/tests/unit/test_compositor_configs_role.py`,
  `test_assets_role.py`, `test_cli_tools_role.py` and
  `adapters/test_yaml_manifest_reader.py` — the guard's negative tests and
  fixtures, which must construct the retired paths to prove rejection, and (c)
  `docs/investigation/**` — read-only historical evidence (out of scope by rule,
  the same carve-out the S4/S5 logs record). Recorded, not claimed green.

- [ ] 8.8 Merge S6 to `master`.
  Gate: `make gates-ci && make deploy-coverage` on the merged `master`
  Expect: exit 0, including the terminal absence guard.
  Status: NOT DONE — this slice's agent stops before merging. The branch
  `ticket/clitools-s6-consume-csg-final` (base `6e0633ba`) carries the
  implementation, the deletion, the docs record and the archive; the merge is the
  orchestrator's step, and the post-merge gate must be re-run on `master`.

### S6 verification log

Run in `.worktrees/clitools-s6` on `ticket/clitools-s6-consume-csg-final` (base
`6e0633ba`) plus the pinned checkout at the tag and a fresh clone of the csg
repo (2026-10-21). No VM: incus is absent, so the role was simulated from the
manifest values.

| Command | Observed |
| --- | --- |
| `gh api repos/RandomGenericUsername/color-scheme-generator --jq .private` | `false`, exit 0 — public pin channel |
| `GIT_TERMINAL_PROMPT=0 git -c credential.helper= ls-remote --tags …/color-scheme-generator 'refs/tags/v0.1.0*'` | `47afbbdf… refs/tags/v0.1.0`, `14f2faf5… refs/tags/v0.1.0^{}` — anonymous |
| fresh clone at `v0.1.0`: `make sync && make gates && make hermetic && uv lock --check` | exit 0; `639 passed` (gates), ruff `All checks passed!`, `639 passed` (hermetic), `Resolved 35 packages` |
| `rg -n "src/shared\|src/cli-tools" <checkout>/src/color_scheme_generator/adapters/docker/` | exit 1 — no sibling-repo path; four Dockerfiles, each backend keeps `ARG BASE_IMAGE=csg-base-docker:latest` (line 1) |
| `podman build -t csg-base-local:test -f …/Dockerfile.base .` + `podman run --rm csg-base-local:test csg --version` | exit 0; `0.1.0 contract 0.1.0` (scratch tag removed after) |
| `git clone --depth 1 --branch v0.1.0 …` + `git rev-parse HEAD` | exit 0; `14f2faf590f503cc60baf0da81955076e9e42214` → `HEAD=tag-commit` |
| `rm -rf <checkout>/.git`, `printf 'v0.1.0\n' > …/csg/pinned` | `.git` absent, `pinned` = `v0.1.0` |
| `UV_TOOL_DIR=/tmp/opencode/s6-uvtools UV_TOOL_BIN_DIR=/tmp/opencode/s6-uvbin uv tool install --force --no-cache <checkout>` | exit 0, `Installed 1 executable: csg` |
| `cat …/color_scheme_generator-0.1.0.dist-info/direct_url.json` | `{"url":"file:///tmp/opencode/s6-spine/cli-tools/csg/v0.1.0","dir_info":{}}` → `PEP610=CHECKOUT` |
| `…/s6-uvbin/csg --version` | `0.1.0 contract 0.1.0`, exit 0 |
| `COLORSCHEME__OUTPUT__DIRECTORY=… COLORSCHEME__OUTPUT__OVERWRITE=true csg generate <wallpaper> --format yaml --format conf --format gtk.css --format adw.css --format sequences --format rasi --format kitty --format btop.theme` (container mode, rendered spine settings) | exit 0; all eight artifacts (`colors.yaml colors.conf colors.gtk.css colors.adw.css colors.sequences colors.rasi colors.kitty colors.btop.theme`) |
| `playbooks/settings.yaml -e install_dir=/tmp/opencode/s6-spine` | exit 0 (`ok=7 changed=4 failed=0`); `settings.toml:21-29` → `mode = "container"`, `engine = "podman"`, `image_prefix = "csg"`, `image_tag = "v0.1.0"` |
| `COLORSCHEME__CONTAINER__IMAGE_TAG=v0.1.0 csg install --container-engine podman --context <checkout>` | exit 0; JSON lists `base`, `custom`, `pywal`, `wallust` `status: built` at `csg-<suffix>-podman:v0.1.0` |
| `podman images --format '{{.Repository}}:{{.Tag}}' \| grep -E '(csg\|color-scheme).*:v0\.1\.0$'` | four lines (`csg-base/-custom/-pywal/-wallust-podman:v0.1.0`); the `:latest` probe → `NO_LATEST` |
| `csg install --image-tag v9.9.9` | exit 2, `No such option: --image-tag` — csg's verb has no such flag (see 8.6 deviation) |
| negative: `git clone --depth 1 --branch v9.9.9 …` | exit 128, `Remote branch v9.9.9 not found`; checkout NOT created |
| negative: clone from `https://github.invalid/...` | exit 128, `Could not resolve host`; `NO_LOCAL_FALLBACK` (no local fallback) |
| `uv run --directory src/provisioning pytest tests/unit/test_assets_role.py::TestAssetsVars::test_csg_templates_source_resolves_to_pinned_checkout -q` | `1 passed`, exit 0 |
| `uv run --directory src/provisioning pytest tests/unit/test_bootstrap_playbook.py -q -k dependency_order` | `1 passed, 5 deselected`, exit 0 |
| real `playbooks/assets.yaml -e install_dir=/tmp/opencode/s6-spine` (weg pinned on PATH) | exit 0 (`ok=16 changed=5`); `diff -r <checkout>/…/defaults/templates <install>/config/color-scheme-generator/templates` → `IDENTICAL` (12 `.j2`) |
| negative: `playbooks/assets.yaml -e install_dir=/tmp/opencode/s6-noassets` | exit 2, `the pinned csg template catalog is missing at …/cli-tools/csg/v0.1.0/src/color_scheme_generator/defaults/templates` |
| `ansible-playbook playbooks/cli-tools.yaml --syntax-check` / `assets.yaml --syntax-check` | exit 0 / exit 0 |
| `ansible-playbook playbooks/cli-tools.yaml --check -e install_dir=<scratch>` | exit 0 (`ok=16 changed=10 failed=0 skipped=21`); scratch `install_dir` NOT created; pinned clone loop = `csg, weg, itr`; argv-tag build loop = `weg`; env-tag build loop = `csg`; source build loop = empty |
| `ansible-playbook playbooks/assets.yaml --check -e install_dir=<scratch>` | exit 0 (`ok=4 changed=1 failed=0 skipped=12`) — needs `ANSIBLE_COLLECTIONS_PATH=$HOME/.ansible/collections` because the scrubbed `HOME` hides the installed collections |
| `XDG_CONFIG_HOME=<rendered spine> PATH=<pinned bin>:$PATH uv run --directory src/runtime pytest tests/integration/test_csg_adapter_integration.py tests/integration/test_csg_determinism.py -v -rs` | `2 passed, 1 xpassed` in 45.52 s (adapter XPASS; `test_csg_deterministic_double_run[custom]` PASSED once its built-image probe stopped requiring `:latest`) |
| `git rm -r src/cli-tools/color-scheme-generator src/cli-tools/openspec` + `rm -rf src/cli-tools` | 147 files / 18 577 lines; `test ! -e src/cli-tools && test ! -e src/shared` → `RETIRED TREES ABSENT` |
| `uv run --directory src/provisioning pytest tests/unit/test_cli_tools_role.py tests/unit/test_verify_role.py -q -k "not TestVerifyRuntime"` | `140 passed, 9 deselected` |
| `uv run --directory src/provisioning pytest tests/unit/test_compositor_configs_role.py -q -k DeployCoverageGate` | `37 passed, 33 deselected` |
| `uv run --directory src/provisioning pytest tests/unit/test_settings_role.py -q -k image_tag` | `6 passed, 27 deselected` |
| `uv run --directory src/provisioning pytest tests/unit/test_settings_role.py -q` | `32 passed, 1 failed` — `TestSettingsPlaybook::test_runtime_gate_with_cli_tools`, the host-stale `csg` env (`ImportError: cannot import name 'engine_qualified_image' from 'oci_runtime'`), identical at base `6ad7117c` (S5 log) — pre-existing |
| `uv run --directory src/runtime pytest tests/unit/test_doctor_check.py tests/unit/test_derive_input_provenance.py -q` | `50 passed` |
| `uv run --directory src/runtime pytest tests/architecture/test_layering.py -q` | `128 passed` |
| `uv run --directory src/provisioning pytest tests/architecture/test_layering.py -q` | `37 passed` |
| `make hermetic` | exit 0 — explicit `hermetic: PASS -- no in-repo package sources …` |
| `make gates-ci` | exit 0 — five gates; `deploy-coverage: PASS`, `ci-gates-parity: PASS` |
| `make deploy-coverage` | exit 0; new `'csg' is provisioned …` + terminal `PASS -- six packages are consumed from their pinned repos …` lines |
| `openspec validate cli-tools-repos --type change` | `Change 'cli-tools-repos' is valid`, exit 0 |
| `openspec validate --all` | `99 passed, 27 failed` — the 27 are the same pre-existing delta-less legacy changes (unchanged; `cli-tools-repos` is not among them). One item fewer than S0b's 127 because the nested CLI-tools OpenSpec root is gone |
| `uv run --directory src/provisioning pytest tests/unit -q -k "not TestVerifyRuntime"` | see the gate run in §9 below |

Not run: the full `src/provisioning` suite (known ~46-min run with two
pre-existing `TestVerifyRuntime` timeouts), per the S4/S5 precedent.

## 9. Post-migration verification (after S6 merges)

Run in the S6 worktree on `ticket/clitools-s6-consume-csg-final` (2026-10-21).
The boxes stay UNCHECKED on purpose: the gate says "after S6 merges", and 8.8 is
the orchestrator's step. The worktree tree is byte-identical to what a merge
would land except for the merge commit itself, so re-running these three boxes on
the merged `master` is the confirmation step.

- [ ] 9.1 Run the terminal gates and reference scan.
  Gate: `make gates-ci && make deploy-coverage`
  Expect: exit 0; `deploy-coverage` reports the six pinned tools, zero
  extracted-package local sources, and exactly one allowed in-repo source
  (`dotfiles-runtime -> src/runtime`).
  Gate: `rg -n 'source:' dotfiles/provisioning/cli-tools.yaml`
  Expect: exactly one match, `source: src/runtime`.
  Gate: `rg -n "src/cli-tools|src/shared" src dotfiles scripts Makefile .github bootstrap.sh AGENTS.md docs`
  Expect: exit 1 (historical dirs are out of scope by rule).
  Gate: `git ls-files 'src/cli-tools/*' 'src/shared/*'`
  Expect: empty.
  Observed (worktree): `make gates-ci` exit 0 and `make deploy-coverage` exit 0
  with `PASS -- six packages are consumed from their pinned repos
  (cli-output, config-assembler-engine, oci-runtime, itr, weg, csg); src/cli-tools/
  and src/shared/ are retired, and the CLI manifest carries exactly ONE in-repo
  source (dotfiles-runtime -> src/runtime)`; the manifest `source:` scan → one
  code match (`source: src/runtime`, line 32) plus one comment mention;
  `git ls-files 'src/cli-tools/*' 'src/shared/*'` → empty (0 lines). The literal
  reference scan is **exit 0, not 1** — see 8.7's deviation: the only remaining
  hits are the `deploy-coverage` guard, its negative tests/fixtures, and
  `docs/investigation/**` (read-only historical evidence).

- [ ] 9.2 Run the installed-tool and pin checks.
  Gate: `for t in itr weg csg; do command -v "$t" && "$t" --version; done`
  Expect: three binaries; each line `<pkg-version> contract 0.1.0` with the tag
  version.
  Gate: `uv tool list | grep -E "color-scheme-generator|wallpaper-effects-generator|icon-templates-renderer"`
  Expect: three entries with versions matching the pins.
  Gate: `rg -n 'cli-invocation-contract = .*contracts", tag = "v[0-9]' src --glob 'pyproject.toml'`
  Expect: 4 matches, all the same tag.
  Observed (worktree): all three binaries exist on the host PATH, but they are
  the pre-S0b `~/.local/bin` installs whose tool envs point at the retired trees —
  `itr` → `ModuleNotFoundError: config_assembler_engine.adapters.config_validator`,
  `weg` → `ModuleNotFoundError: cli_output.adapters.factory`, `csg` →
  `ImportError: cannot import name 'engine_qualified_image' from 'oci_runtime'`.
  The DESIGNED path is the next bootstrap's `uv tool install --force` from the
  pinned checkout, proven here in isolated dirs (`csg --version` →
  `0.1.0 contract 0.1.0`). `uv tool list` shows all three entries at `v0.1.0`
  (matching the pins) with the same stale envs.
  **Deviation:** the contract-pin scan returns **1 match**
  (`src/runtime/pyproject.toml:27`), not 4 — the three CLI consumers are no
  longer in this repo, so their pins live in their own `pyproject.toml`s (csg's
  tag checkout pins `contracts v0.1.0` at line 61; itr/weg were verified in S4/S5).
  The runtime is the only in-repo consumer left, and it pins the same tag.

- [ ] 9.3 Prove the tag chain for every repo in one pass.
  Gate: `for r in contracts cli-output config-assembler-engine oci-runtime icon-templates-renderer wallpaper-effects-generator color-scheme-generator; do printf '%s: ' "$r"; git ls-remote --tags --refs "$CLI_REPO_BASE/$r" | sed 's#.*refs/tags/##' | tr '\n' ' '; echo; done`
  Expect: `contracts: v0.1.0`, `cli-output: v0.1.0`,
  `config-assembler-engine: v0.1.0`, `oci-runtime: v0.5.0`,
  `icon-templates-renderer: v0.1.0`, `wallpaper-effects-generator: v0.1.0`,
  `color-scheme-generator: v0.1.0`; no repo is missing a consumed tag and no tag
  listed twice. `--refs` keeps each tag to exactly one line.
  Observed (worktree, anonymous): exactly the seven expected lines, one tag each.

## Archive

Command: `openspec archive cli-tools-repos --yes` (run in the S6 worktree after
§9 was recorded). Its observed output is recorded in the archive commit message
and in the slice report; nothing above this line is ticked after the archive runs.

## Workflow follow-up

- Archive this change with `openspec archive cli-tools-repos` after the final
  slice merges and the post-migration verification is recorded as evidence.
  **Recorded:** the archive was run in the S6 worktree after §9 was recorded as
  evidence (see "Archive output" below); it lands with 8.8's merge, which is the
  orchestrator's step.
- Keep this change's capability specs as the cross-repo contract; per-package
  specs follow their code into the new repos (AD-15) and are not rewritten here.
