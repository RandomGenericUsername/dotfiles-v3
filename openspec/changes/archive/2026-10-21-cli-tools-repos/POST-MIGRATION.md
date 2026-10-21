# Post-migration closure record — `cli-tools-repos`

Written 2026-10-21, after the umbrella change was archived and S6 merged to
`master`.

**This file is additive.** `tasks.md` in this directory is the point-in-time
record of the change as it stood when it was archived, and its ten open boxes
(0.1–0.6, 8.8, 9.1–9.3) are **deliberately left unticked**: an archive is a
snapshot, not a live checklist. This file is the live answer to "did those ten
actually land?", with the command and the observed result for each.

Re-run target: `master` at `1b2f644a` (`git rev-parse master` →
`1b2f644ab38778a573cf1951d8870c411eb73a68`), a clean checkout
(`git status --short` → empty; `git ls-files src/shared src/cli-tools` → 0
lines; `src/shared` + `src/cli-tools` absent).

## 1. Completion table

### The six extracted repos (0.1–0.6, and 9.3's tag chain)

Checked against a shallow clone of each repo at its released tag
(`git clone --depth 1 --branch <tag> …` → `HEAD` equals the peeled commit
below). "runs" is `gh run list -R RandomGenericUsername/<r> --limit 3 --json
status,conclusion,headBranch`; all six returned three `completed/success`
entries, including one on the tag's own branch.

| Repo | `gh api … --jq '{private,visibility}'` | Consumed tag | Annotated tag object | Peeled commit (`^{}`) | Latest runs | Release asset |
| --- | --- | --- | --- | --- | --- | --- |
| `cli-output` | `{"private":false,"visibility":"public"}` | `v0.1.0` | `91489b73b54e6cd09dc54e360431a3ebb915fa05` | `ddae372786fd6053730133e82cf542a17e9a5ae5` | `success/main`, `success/v0.1.0`, `success/main` | `cli_output-0.1.0.tar.gz` |
| `config-assembler-engine` | `{"private":false,"visibility":"public"}` | `v0.1.0` | `5c5cc84e4103f1135a717320cf7cb809487d6e5e` | `cad8a91c6bcbc4087209911bc36d82f8b6349f66` | `success/main`, `success/v0.1.0`, `success/main` | `config_assembler_engine-0.1.0.tar.gz` |
| `oci-runtime` | `{"private":false,"visibility":"public"}` | `v0.5.0` | `38ce267ce966a831ba0617bc5a97660564f7880a` | `b631dfa511f5710d6e171d2ac3f0cdf58bc738af` | `success/v0.5.0`, `success/main` | `oci_runtime-0.5.0.tar.gz` |
| `icon-templates-renderer` | `{"private":false,"visibility":"public"}` | `v0.1.0` | `09271f64375ccfb2eeb36dc3c6b81a4b55b2bdd6` | `92895a068b7117832d0cbf2a5bfb158ca3fda68c` | `success/main`, `success/v0.1.0`, `success/main` | `icon_templates_renderer-0.1.0.tar.gz` |
| `wallpaper-effects-generator` | `{"private":false,"visibility":"public"}` | `v0.1.0` | `093d405129ef34a7d1bd78c64b692bca17129cb9` | `9672d89c117709afa6eb5b574bd8fdb71469f801` | `success/main`, `success/v0.1.0`, `success/main` | `wallpaper_effects_generator-0.1.0.tar.gz` |
| `color-scheme-generator` | `{"private":false,"visibility":"public"}` | `v0.1.0` | `47afbbdf4b3d1d7a2ac6dbc9cfea3d6d4487b335` | `14f2faf590f503cc60baf0da81955076e9e42214` | `success/main`, `success/v0.1.0`, `success/main` | `color_scheme_generator-0.1.0.tar.gz` |
| `contracts` (the seventh, contract home) | `{"private":false,"visibility":"public"}` | `v0.1.0` | `6ea43dcb8864ae749d4912878d70dc91e7376969` | `48cf3cfed4b192b241505789409c4f282921c896` | (unchanged since S0a; `contract-drift` green) | — |

Tag-chain one-pass (9.3), anonymous:

```text
contracts: v0.1.0
cli-output: v0.1.0
config-assembler-engine: v0.1.0
oci-runtime: v0.5.0
icon-templates-renderer: v0.1.0
wallpaper-effects-generator: v0.1.0
color-scheme-generator: v0.1.0
```

One tag per repo, no tag listed twice, every consumed tag present
(`git ls-remote --tags --refs https://github.com/RandomGenericUsername/<r>`,
exit 0 each).

### Per-task state

| Task (as archived) | Was | Now | Evidence |
| --- | --- | --- | --- |
| 0.1 harness byte-identical to `mu` | open | **satisfied** | In all six pinned checkouts: `diff -r /home/inumaki/Development/mu/<path> <path>` over the eight copied paths (`_bmad`, `.agents/skills`, `.opencode`, `scripts/worktree-guard.sh`, `skills-lock.json`, `tickets/_template`, `tickets/_fixtures`, `tickets/LIFECYCLE.md`) → 0 differing paths per repo (`harness_diff_failures=0`). `mu` ships no hash-recompute script, so byte-equality is the proof every `computedHash` matches. |
| 0.2 verbs resolve paths from any caller dir | open | **satisfied** | From `/tmp/opencode` (a foreign cwd): `make -C <repo> gates` → exit 0 for all six, suites `63` / `163` / `288` / `349` / `639` / `1107 passed, 2 skipped`. `rg -n '$(PWD)\|$(shell pwd)' <repo>/Makefile` → exit 1 for all six (`$(CURDIR)` only). |
| 0.3 CI parity runs before the first push | open | **satisfied** | `make -C <repo> ci-gates-parity` → exit 0, `PASS gates=[...] jobs=[...] exempt=[...]` for all six (weg/csg declare `image` + `release` exempt). `.github/workflows/gates.yml` present in all six; latest runs above are green. |
| 0.4 hermetic fixture and canary exist | open | **satisfied** | `rg -l 'XDG_CONFIG_HOME' <repo>/tests/conftest.py` → match (exit 0) in all six; `uv run pytest -q -k canary` at the pinned checkout → `1 passed` in each (`62`/`162`/`1108`/`287`/`348`/`638` deselected). |
| 0.5 pin channel is anonymous | open | **satisfied** | `gh api repos/…/<r> --jq '{private,visibility}'` → `private:false, public` (table above), and the credential-free probe `GIT_TERMINAL_PROMPT=0 git -c credential.helper= ls-remote …/<r> 'refs/tags/<tag>'` → exit 0, exactly one line, for all six **and** `contracts`. |
| 0.6 visibility decision + consequence recorded | open | **satisfied in the record, stale in the birth tickets** | This repo's S-slice logs + this file state the channel (anonymous `https`, no credential helper) and the consequence (a private repo would break `ansible.builtin.git`'s anonymous fetch). The per-repo birth tickets are **not** updated — see gap (g). |
| 8.8 Merge S6 to `master` | open | **done** | `master` = `1b2f644a` (`chore(openspec): archive the cli-tools-repos umbrella change`); `git rev-list --parents -n1 1b2f644a` → one parent `980365fc`, i.e. a single-commit-tip **fast-forward** of the S6 branch (`ticket/clitools-s6-consume-csg-final` = `1b2f644a`) over `6e0633ba`; the range `6e0633ba..1b2f644a` is 4 commits (`1d8d4fc8`, `8e8de381`, `980365fc`, `1b2f644a`). Push: `git ls-remote origin refs/heads/master` → `1b2f644ab38778a573cf1951d8870c411eb73a68  refs/heads/master`, exit 0. Post-merge gates on the merged tree: `make gates-ci` exit 0, `make hermetic` exit 0, `make deploy-coverage` exit 0. |
| 9.1 terminal gates + reference scan | open | **satisfied, with one recorded deviation** | `make gates-ci` → exit 0 (five gates: `contracts-check`, `ansible-embedded-template-lint`, `deploy-coverage`, `ci-gates-parity`, `per-app-drift-symbol-suites`). `make deploy-coverage` → exit 0 and the terminal line quoted below. `rg -n '^    source:' dotfiles/provisioning/cli-tools.yaml` → **exactly one** match, `34:    source: src/runtime`. `test ! -e src/cli-tools && test ! -e src/shared` → exit 0. `git ls-files 'src/cli-tools/*' 'src/shared/*'` → 0 lines. The literal `rg -n "src/cli-tools\|src/shared" src dotfiles scripts Makefile .github bootstrap.sh AGENTS.md docs` is **exit 0, not 1** — 338 lines in 9 files, all of them either the guard, its negative tests/fixtures, or read-only investigation docs (gap (f)). |
| 9.2 installed-tool + pin checks | open | **satisfied for the pins, host tools still stale** | `uv tool list` → `color-scheme-generator v0.1.0`, `icon-templates-renderer v0.1.0`, `wallpaper-effects-generator v0.1.0` (matching the manifest pins). But `command -v itr/weg/csg` resolve to `~/.local/bin/*` and each exits 1 at import (`ModuleNotFoundError: No module named 'cli_output'` / `'config_assembler_engine'` / `'oci_runtime'`) — gap (b). Contract-pin scan `rg -n 'cli-invocation-contract = .*contracts", tag = "v[0-9]' src --glob 'pyproject.toml'` → **1** match, `src/runtime/pyproject.toml:27` (the three CLI consumers left this repo; their own `pyproject.toml`s carry the same tag). |
| 9.3 tag chain in one pass | open | **satisfied** | The seven-line output above, anonymous, exit 0. |

### Headline gate output (verbatim, on `1b2f644a`)

```text
$ make deploy-coverage   # exit 0
deploy-coverage: PASS -- six packages are consumed from their pinned repos (cli-output, config-assembler-engine, oci-runtime, itr, weg, csg); src/cli-tools/ and src/shared/ are retired, and the CLI manifest carries exactly ONE in-repo source (dotfiles-runtime -> src/runtime)
```

```text
$ make hermetic          # exit 0
hermetic: PASS -- no in-repo package sources; the six extracted
  packages (cli-output, config-assembler-engine, oci-runtime,
  itr, weg, csg) run their own 'make hermetic' in their pinned
  repos; this repo's src/runtime + src/provisioning are covered
  by 'make gates-ci'
```

`openspec validate --all` → **exit 1, `Totals: 104 passed, 27 failed (131
items)`**. The 27 failures are the pre-existing legacy set, unchanged:
`openspec validate --all` at pre-merge base `6e0633ba` → `99 passed, 27 failed
(126 items)`, and the 27 failing item names are **identical** (`diff` of the
sorted names → empty). Composition: 19 legacy **change**-level defects
(`add-bluetooth-bar-popup`, `add-mic-live-dot-backdrop-state`,
`ags-apps-bar-first`, `ags-remove-bar-bridge`,
`declare-capture-test-dependencies`, `enhance-ags-bar`,
`gtk-theming-consumer`, `redesign-ags-audio-panel`, and eleven `wifi-*`
changes — mostly `Change must have at least one delta`, some a requirement
without a scenario, some a SHALL only in the header) and 8 pre-existing
**spec** shape defects (`cli-runtime-engine-scope`,
`container-image-engine-tagging`, `csg-image-naming`, `oci-doc-cleanup-v3`,
`oci-exec-semantics`, `oci-pipe-reader-port`, `oci-test-contracts`,
`oci-version-error-contract` — missing `## Purpose`, requirement outside
`## Requirements`, requirement without a scenario). The passing count rose
99 → 104 because the archive added five capability specs to
`openspec/specs/`.

### The post-merge failure that was found and fixed (operational note)

8.8's **first** post-merge `make deploy-coverage` on `master` failed even
though the merge was green in the worktree. Cause: the main checkout still
held untracked/ignored residue under `src/shared/` and `src/cli-tools/`
(most likely `.venv/` / `__pycache__` content left by earlier slices' runs).
No file was tracked — `git ls-files src/shared src/cli-tools` → 0 — but the
**directories still existed**, and the terminal guards assert directory
absence, so they fired. `rm -rf src/shared src/cli-tools` cleared it and every gate then
passed.

Reproduced on the merged tree to pin the exact messages (create an
ignored-only leftover, run the guard, remove it, run again):

```text
$ mkdir -p src/cli-tools/__pycache__ && touch src/cli-tools/__pycache__/x.pyc
$ git status --ignored --short src/cli-tools
!! src/cli-tools/
$ uv run --directory src/provisioning python ../../scripts/deploy-coverage.py   # exit 1
FAIL: the retired package root src/cli-tools/ still exists — every CLI tool and shared library is consumed from its pinned repo (spine AD-10); delete the directory
$ rm -rf src/cli-tools

$ mkdir -p src/shared/.venv && touch src/shared/.venv/marker
$ git status --ignored --short src/shared
?? src/shared/                       # (0 tracked files; only ignored content)
$ uv run --directory src/provisioning python ../../scripts/deploy-coverage.py   # exit 1
FAIL: the retired shared-library root src/shared/ still exists — every shared library is consumed from its pinned repo; delete the directory (an empty leftover must not become a new home for a vendored copy)
$ rm -rf src/shared
$ uv run --directory src/provisioning python ../../scripts/deploy-coverage.py   # exit 0
deploy-coverage: PASS -- six packages are consumed from their pinned repos …
```

**For future migrations:** a worktree merge and a main-checkout merge are not
the same evidence. Worktrees are created from a commit and carry no
untracked/ignored leftovers; the long-lived main checkout can, and the
absence guards look at the filesystem, not at `git ls-files`. After any
tree-deletion merge, `rm -rf` the retired roots in the checkout you are about
to gate, then run `make deploy-coverage` there before believing the merge.

## 2. What the repository looks like now (facts for future readers)

- **Seven pinned repos, one contract package.** `contracts` (tag `v0.1.0`)
  owns the invocation contract; the six extracted packages own their code:
  `cli-output`, `config-assembler-engine`, `oci-runtime` (tag `v0.5.0`),
  `icon-templates-renderer`, `wallpaper-effects-generator`,
  `color-scheme-generator` (all `v0.1.0`). Every one is public and fetched
  anonymously by tag.
- **Two consumption shapes only:**
  - the three **shared libraries** (`cli-output`, `config-assembler-engine`,
    `oci-runtime`) plus `cli-invocation-contract` are consumed as git-tag pins
    in each consumer's `pyproject.toml` `[tool.uv.sources]`
    (`{ git = "…/repo", tag = "vX.Y.Z" }`), and the resolved commit is what
    `uv.lock` records;
  - the three **CLIs** (`csg`, `weg`, `itr`) are consumed as
    `{name, repo, tag}` entries in `dotfiles/provisioning/cli-tools.yaml`
    (+ the `roles/cli_tools/vars/main.yml` mirror). The role shallow-clones
    `<repo>@<tag>` into `<install>/cli-tools/<name>/<tag>/`, drops `.git`,
    writes the `pinned` record, and installs **from that checkout** (never
    from a `git+…@tag` URL) so PEP 610 records a tag-bearing path.
- **The only in-repo Python is `src/runtime/` and `src/provisioning/`.**
  There are no in-repo package sources for anything extracted: `cli-tools/`
  and `shared/` package roots are retired and gated absent, and
  `dotfiles/provisioning/cli-tools.yaml` carries exactly one local
  `source:` (`dotfiles-runtime -> src/runtime`, line 34). `HERMETIC_PACKAGES`
  is empty, which is why `make hermetic` prints an explicit PASS.
- **Image tags are pins, never `latest`.** `weg`'s image tag is an argv tag;
  `csg`'s four images take the pin through
  `COLORSCHEME__CONTAINER__IMAGE_TAG` (see gap (c)).

## 3. Known gaps / follow-ups

Each item is a real, observed limitation — none is redressed in this record.

**(a) No real VM provisioning run (no incus on this host).** `command -v incus`
→ nothing. The roles' behaviour is proven by **simulation + `--check`** on the
merged tree, not by provisioning a machine:

```text
$ cd src/provisioning/ansible
$ ANSIBLE_COLLECTIONS_PATH=$HOME/.ansible/collections ../.venv/bin/ansible-playbook \
    playbooks/cli-tools.yaml --check -e install_dir=/tmp/opencode/close-scratch
localhost : ok=16 changed=4 unreachable=0 failed=0 skipped=21   # exit 0
$ ls -d /tmp/opencode/close-scratch        # dry run created nothing
No such file or directory
$ ANSIBLE_COLLECTIONS_PATH=$HOME/.ansible/collections ../.venv/bin/ansible-playbook \
    playbooks/assets.yaml --check -e install_dir=/tmp/opencode/close-scratch
localhost : ok=4 changed=1 unreachable=0 failed=0 skipped=12    # exit 0
```

`ansible-playbook` is not on the host `PATH`; it lives in
`src/provisioning/.venv/bin/`. `ANSIBLE_COLLECTIONS_PATH` is required because
the scrubbed `HOME` otherwise hides the installed collections. Syntax checks:
both playbooks `--syntax-check` exit 0. Follow-up: run
`playbooks/bootstrap.yaml` + `cli-tools.yaml` + `assets.yaml` for real on a
disposable VM and record the recap.

**(b) The host's `~/.local/bin/{csg,weg,itr}` are stale pre-migration uv-tool
envs.** `uv tool list` reports the right versions but the envs point at the
retired trees:

```text
$ uv tool list | grep -E 'color-scheme-generator|wallpaper-effects-generator|icon-templates-renderer'
color-scheme-generator v0.1.0
icon-templates-renderer v0.1.0
wallpaper-effects-generator v0.1.0
$ cat ~/.local/share/uv/tools/color-scheme-generator/…/color_scheme_generator-0.1.0.dist-info/direct_url.json
{"url":"file:///home/inumaki/Development/dotfiles-v3/src/cli-tools/color-scheme-generator","dir_info":{}}
   # same shape for weg (…/src/cli-tools/wallpaper-effects-generator), itr (…/icon-templates-renderer);
   # the bundled cli-output dep points at …/src/shared/cli-output
$ itr --version   # exit 1
ModuleNotFoundError: No module named 'config_assembler_engine'
$ weg --version   # exit 1
ModuleNotFoundError: No module named 'cli_output'
$ csg --version   # exit 1
ModuleNotFoundError: No module named 'oci_runtime'
```

The designed path is the next real bootstrap's `uv tool install --force` from
the pinned checkout (proven in isolated `UV_TOOL_DIR`s during S2/S6:
`csg --version` → `0.1.0 contract 0.1.0`). Fix = a real provisioning run, out
of scope here. Consequence while stale: `src/runtime`'s
`test_weg_adapter_integration_real_binary` does not skip (it only checks
`shutil.which("weg")`) and fails on the stale binary — see (d).

**(c) `csg install` has no `--image-tag` option.** The pin travels via the
setting, `COLORSCHEME__CONTAINER__IMAGE_TAG`, which provisioning renders into
`[container] image_tag`. So `csg install --image-tag v9.9.9` is rejected by
the CLI parser (`No such option: --image-tag`, exit 2) — that is *option
validation*, not the tag gate. The "nonexistent tag fails" gate is therefore
enforced upstream, at clone/verify (clone probe quoted from the S6 log in
`tasks.md` §8; the README line is re-read from the pinned checkout):

```text
$ git clone --depth 1 --branch v9.9.9 <csg repo>   # exit 128
Remote branch v9.9.9 not found; checkout NOT created
$ rg -n 'there is no separate' <csg checkout>/README.md
64:`COLORSCHEME__CONTAINER__IMAGE_TAG`); there is no separate `--image-tag` flag because the setting is
```

`verify` asserts each of the four images exists at the tag-qualified
reference, so a mistyped pin fails there rather than at install-time option
parsing. Recorded so nobody "fixes" the missing flag without also adding a
negative test for the setting path.

**(d) Pre-existing failures unrelated to this migration.**
`uv run --directory src/runtime pytest -q` → **exit 1, `2 failed, 2122
passed, 4 skipped` in 78 s**:

1. `tests/unit/test_recording_indicator.py::TestNoPollingInvariant::test_bar_widget_has_no_poll_loop`
   — `FileNotFoundError` on
   `dotfiles/config/ags/bar/widgets/recording.tsx`. The bar moved to the
   external `ags-apps` unit (this repo's bar sources are retired), so the
   test's hard-coded path is stale. Pre-existing and outside this migration.
2. `tests/integration/test_weg_adapter_integration.py::test_weg_adapter_integration_real_binary`
   — caused by the stale host `weg` from gap (b); it **skips** once the stale
   dir is off `PATH`.

With the stale `~/.local/bin` off `PATH` (the designed environment):

```text
$ src/runtime/.venv/bin/python -m pytest -q src/runtime/tests   # exit 1
FAILED tests/unit/test_recording_indicator.py::TestNoPollingInvariant::test_bar_widget_has_no_poll_loop
1 failed, 2122 passed, 5 skipped, 6 warnings in 73.19s
```

so exactly one known, pre-existing failure remains.

Provisioning side: `tests/unit/test_verify_role.py -k TestVerifyRuntime` →
**exit 1, `6 failed, 3 passed, 82 deselected` in 194 s**, and the *same six*
fail at pre-merge base `6e0633ba` (`6 failed, 3 passed, 80 deselected` in
202 s) — pre-existing, not caused by the merge. The cause is no longer the
120 s timeouts the S2 log recorded: the real `verify.yaml` run now fails fast
because the simulated "provisioned machine" fixture does not create
`<install>/cli-tools/itr/pinned`, which the verify role's pinned-checkout task
reads (`Task failed: Module failed: File not found:
…/install/cli-tools/itr/pinned`). Follow-up: extend
`_build_provisioned_layout` with the three pin records (and any other
pinned-checkout artifacts verify now requires) so this execution guard is
green again rather than permanently red.

**(e) `openspec validate --all` keeps 27 pre-existing failures.** `104 passed,
27 failed (131 items)`, exit 1; identical failing-item set at base
`6e0633ba` (`99 passed, 27 failed (126 items)`). Not delta-less-only: 19
legacy change-level defects **plus** 8 pre-existing spec shape defects (the
names and the error mix are in the 9.1 row). None is `cli-tools-repos`; the
archived specs validate. Follow-up: sweep them under their own change, or set
`skip_specs: true` on the pure-docs changes.

**(f) Literal stale-path `rg` residue remains.** `rg -n "src/cli-tools|src/shared"
src dotfiles scripts Makefile .github bootstrap.sh AGENTS.md docs` → exit 0,
338 lines in 9 files, all expected:

- `scripts/deploy-coverage.py` — the guard must name the paths it asserts
  absent;
- `src/provisioning/tests/unit/{test_compositor_configs_role,test_assets_role,test_cli_tools_role}.py`
  and `src/provisioning/tests/unit/adapters/test_yaml_manifest_reader.py` —
  the guard's negative tests/fixtures, which must construct the retired paths
  to prove rejection;
- `docs/investigation/{S1,S2,S3,S4}-*.md` — read-only historical evidence, out
  of scope by rule (same carve-out the S4/S5 logs record).

**(g) Birth-ticket bookkeeping is stale in five of six repos** (this is the
one place 0.6's "recorded" half falls short). The tickets were written before
the remotes existed and never closed out:
`cli-output` 8 unchecked / 0 checked acceptance boxes, `icon-templates-renderer`
8 / 0, `color-scheme-generator` 10 / 0, `wallpaper-effects-generator` 5 / 5
with a Closeout that still says `pending (blocked: no remote)` for
`gh run list`, the annotated tag, the anonymous fetch and the release assets,
`config-assembler-engine` 3 / 5 with two `pending` lines; only `oci-runtime`
is fully closed (0 / 10). The gates themselves are green (section 1) — only
the per-repo paperwork lags. Related: every released repo attaches the
**sdist only** (`*.tar.gz`) to its GitHub Release, while the birth acceptance
text asks for wheel + sdist; consumption is by git tag, so nothing is broken,
but the asset expectation and the CI `release` job disagree. Follow-up: close
each birth ticket against section 1's table, and either add the wheel to the
`release` job or relax the ticket text.

## 4. Verification log for this record

| Command | Observed |
| --- | --- |
| `git rev-parse master`; `git ls-remote origin refs/heads/master` | `1b2f644ab38778a573cf1951d8870c411eb73a68` both, exit 0 |
| `git status --short`; `git ls-files src/shared src/cli-tools` | empty; 0 lines |
| `test ! -e src/cli-tools && test ! -e src/shared` | exit 0 (both absent) |
| `rg -n '^    source:' dotfiles/provisioning/cli-tools.yaml` | one match, `34:    source: src/runtime` |
| `make gates-ci` | exit 0 — `contracts-check`, `ansible-embedded-template-lint` (`PASS`), `deploy-coverage` (`PASS`), `ci-gates-parity` (`PASS`), `per-app-drift-symbol-suites` (`OK`) |
| `make deploy-coverage` | exit 0, terminal `PASS -- six packages are consumed from their pinned repos …` |
| `make hermetic` | exit 0, `hermetic: PASS -- no in-repo package sources …` |
| `uv run --directory src/runtime pytest -q` | exit 1, `2 failed, 2122 passed, 4 skipped` (failure 2 = stale host `weg`) |
| same suite with `~/.local/bin` off `PATH` | exit 1, `1 failed, 2122 passed, 5 skipped` (only the bar-path failure) |
| `uv run --directory src/provisioning pytest tests/unit/test_verify_role.py -q -k TestVerifyRuntime` | exit 1, `6 failed, 3 passed, 82 deselected` in 194 s; same six at base `6e0633ba` in 202 s |
| `openspec validate --all` | exit 1, `104 passed, 27 failed (131 items)`; base `6e0633ba` → `99 passed, 27 failed (126 items)`, identical names |
| `diff -r mu/<8 paths>` ×6 repos | 0 differences per repo |
| `make -C <repo> gates` ×6 from `/tmp/opencode` | exit 0 each; `63`/`163`/`288`/`349`/`639`/`1107+2skip` passed |
| `make -C <repo> ci-gates-parity` ×6 | exit 0 each, `PASS …` |
| `uv run pytest -q -k canary` ×6 | `1 passed` each |
| `gh api repos/…/<r> --jq '{private,visibility}'` ×7 | all `private:false, visibility:public` |
| `git ls-remote --tags … 'refs/tags/v*'` and `'refs/tags/<tag>*'` ×7 | one tag each; annotated object + `^{}` commit as tabled |
| `gh run list -R … --limit 3 --json status,conclusion,headBranch` ×6 | all `completed/success` |
| `gh release view <tag> --json tagName,assets` ×6 | `tagName` matches; one asset, the sdist |
| anonymous `GIT_TERMINAL_PROMPT=0 git -c credential.helper= ls-remote` ×7 | exit 0, one line each |
| `ansible-playbook … --syntax-check` (cli-tools, assets) | exit 0 / exit 0 |
| `ansible-playbook … --check -e install_dir=<scratch>` | exit 0, `ok=16 changed=4 failed=0 skipped=21` / `ok=4 changed=1 failed=0 skipped=12`; scratch dir not created |
| `command -v incus` | absent |
| `uv tool list`; `{itr,weg,csg} --version` | three entries at `v0.1.0`; each binary exit 1 with `ModuleNotFoundError` |
