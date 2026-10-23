---
name: 'Assets split — residual ledger'
type: residual-ledger
purpose: 'Keep every known gap in the assets split visible, with its evidence, until it is closed by executed evidence'
status: open
created: '2026-10-22'
updated: '2026-10-23'
baseline: '2f5ee95e'
companions:
  - ARCHITECTURE-SPINE.md
  - SLICES.md
  - EVIDENCE-INDEX.md
  - .memlog.md
---

# Residual ledger — assets split

**Why this file exists.** The split's slices land in order (`SLICES.md`), but the last slice is where
the remaining gaps compete for attention. This ledger is the queue for that end: every gap is named,
given an ID, backed by a file:line or a command with its observed result, and closed only by
re-running a stated proof. It is deliberately not a wish list — an entry with no evidence does not
belong here, and an entry is not closed because the code "looks right".

## How to use this ledger

1. Read the summary table top-down. **P1** items block claims the split already makes; work them
   first. **P2** items must be scheduled before the split is declared complete but do not
   invalidate a landed slice. **P3** items are hygiene/process and may follow the split.
2. Open the item's detail section. It carries: ID, priority, status, owner (the closing slice),
   evidence, impact, planned resolution, and the **closure proof** (the exact command and expected
   observable).
3. To close an item: run the closure proof, paste the command and its observed result (exit code +
   key output) into the item, set the status to `CLOSED`, and move the item to *Resolved during the
   split* with the resolving commit SHA. **No residual is closed without executed evidence.**
4. A new gap gets the next free ID (`R-15`, …). Never renumber. If an item splits, add a new ID and
   mark the original `SUPERSEDED`.
5. Assets-repo evidence is cited **by tag** (`git -C ../dotfiles-assets show <tag>:<path>`) because
   the sibling checkout moves; `dotfiles-v3` evidence is against the baseline commit named below.

**Status vocabulary:** `OPEN` · `OPEN-BLOCKED` (waiting on an environment or an upstream decision) ·
`CLOSED` (closure proof executed and recorded).

## Measurement environment

| Item | Value |
| --- | --- |
| `dotfiles-v3` baseline | `2f5ee95e` — `fix(zsh): gate login-shell become, prune .zshrc.j2 residue, align schema glob`; `git status --porcelain` empty at start |
| This ledger's worktree | `.worktrees/residuals/`, branch `ticket/residuals-assets-split-residuals` (guard-created, docs-only) |
| Host | Linux; `python3 --version` → `Python 3.14.7`; `uv --version` → `uv 0.9.22`; `openspec --version` → `1.14.1` |
| Ansible | from the installed engine `v0.1.2` tool env; the CLI prepends that env's bin dir to the child `PATH` (R-15) |
| Pins | assets `v0.5.0` (`dotfiles/provisioning/assets.yaml:20`); installer engine `v0.1.4` (`d97c697`, `dotfiles/provisioning/installer.pin`); ags-apps `v0.4.1` (`66dc3c9`); six CLI/library pins per `deploy-coverage` |
| Engine release | `dotfiles-provision` `v0.1.4` = `d97c697` (v0.1.1 = `de0b92c`, v0.1.2 = `1b2195f`, v0.1.3 = `b957432`); wheel carries 87 `provisioning/_ansible/` entries |
| Assets release | `dotfiles-assets` `v0.5.1` = `4683c76` (gate-only `validate-configs`; zero corpus bytes); the composition still pins `v0.5.0` |
| Measurement date | 2026-10-22 |

> The assets checkout advanced from `v0.4.0` (`92100a6`) to `v0.5.0` (`d894f9b`) while this ledger was
> being measured. That is why every assets citation names the tag it was read at; a bare line number
> in a sibling checkout is not reproducible.

## Summary — open residuals, in address-at-end order

| ID | Priority | Residual | Closing slice | Status |
| --- | --- | --- | --- | --- |
| R-10 | P1 | VM end-to-end gate never run — `incus` unavailable here; every slice marks it `PLANNED` | final end-to-end (S7 or dedicated) | OPEN-BLOCKED |
| R-04 | P2 | Display-manager host apply skipped after the template move; only the file render is proven byte-identical | dedicated host apply | OPEN-BLOCKED (no passwordless sudo) |

---

## Open residuals

### R-10 — The VM end-to-end gate has never run

- **Priority / status:** P1 · OPEN-BLOCKED (no incus) · **Owner:** final end-to-end (S7 or a dedicated
  host/VM run).
- **Evidence:**
  - `command -v incus` → no output (not installed); `bash dev/check-prereqs.sh < /dev/null` →
    `ERROR: 'incus' is not installed on this host.` (exit 1, executed 2026-10-22).
  - The real entry point is **`make vm-fresh` / `make vm-verify`** → `./dev/vm fresh|verify`
    (`Makefile:325-346`), and `dev/vm:126-131` runs `dev/vm-assert.sh` for `verify`. **There is no
    `dev/vm-verify` file** (`ls dev` → `vm-assert.sh`, `vm-fresh.sh`, `vm-continue.sh`, …). Each of
    S1–S7 nevertheless writes `dev/vm-fresh.sh && dev/vm-verify` in its gate block
    (`SLICES.md:251,338,410,490,554,624,693`) and lines 29-30; those commands cannot be
    copy-pasted as written.
  - `SLICES.md:29-30` names `dev/vm-verify` and cites `ARCHITECTURE.md:563` for the "local-only,
    not CI" reason; the actual statement is at `ARCHITECTURE.md:597` ("No VM in CI. `dev/` drives an
    incus VM, but `incus` is absent on this host…").
  - All seven per-slice occurrences are marked `PLANNED`; no slice claimed VM evidence.
- **Impact:** the split's "still provisionable" invariant has component evidence (host runs, gates)
  but no fresh-machine proof. The bootstrap path that fetches the pinned assets and the extracted
  installer is exactly the path a VM run exercises.
- **Planned resolution:** run on a host with incus: `make vm-fresh && make vm-verify`, paste the
  recap. In the same change, correct the seven slice gate blocks and line 29 to the runnable form
  (`make vm-fresh && make vm-verify`) and fix the `ARCHITECTURE.md:597` citation.
- **Closure proof:** `make vm-verify` exit 0 inside the freshly provisioned guest; `dev/vm-assert.sh`
  reports no failure; the `dotfiles-provision verify` log in the guest ends `failed=0`.

### R-04 — Display-manager host apply skipped after the template move

- **Priority / status:** P2 · OPEN-BLOCKED (this host has no passwordless sudo: `sudo -n true` →
  exit 1) · **Owner:** dedicated host-apply cleanup (or S7's end-to-end with R-10).
- **Evidence:**
  - Engine `ansible/playbooks/display-manager.yaml:14` → `become: true`; the role installs
    packages, fetches/patches Pixie, writes `/etc/sddm.conf.d/10-dotfiles.conf` and enables/disables
    services (`ansible/roles/display_manager/tasks/main.yml:38-135`).
  - The render task now reads the pinned corpus
    (`ansible/roles/display_manager/tasks/main.yml:68-74` → `{{ display_manager_assets_templates_dir }}/display-manager/sddm.conf.j2`),
    and the pin is `v0.5.0` (`ansible/roles/display_manager/vars/main.yml`).
  - Executed render proof (2026-10-22), reproducible:
    ```bash
    ASSETS=/home/inumaki/Development/dotfiles/dotfiles-assets
    uv run --directory /home/inumaki/Development/dotfiles/dotfiles-provision python - "$ASSETS" <<'PY'
    import hashlib, sys
    from pathlib import Path
    from jinja2 import Environment, StrictUndefined

    assets = Path(sys.argv[1])
    template = (assets / "templates/display-manager/sddm.conf.j2").read_text()
    out = Environment(undefined=StrictUndefined, keep_trailing_newline=True).from_string(template).render(
        display_manager_sddm_display_server="wayland"
    )
    live = Path("/etc/sddm.conf.d/10-dotfiles.conf").read_text()
    print("rendered", hashlib.sha256(out.encode()).hexdigest())
    print("live    ", hashlib.sha256(live.encode()).hexdigest())
    print("byte_identical", out == live)
    PY
    ```
    → `rendered f2899e15068ff804ec6ae29ee2364f6cf533f83af6f644d413d25848e1b0d483`;
    `live f2899e15068ff804ec6ae29ee2364f6cf533f83af6f644d413d25848e1b0d483`;
    `byte_identical True`.
  - The schema declares exactly the one required name
    (`git show v0.4.0:templates/display-manager/sddm.conf.vars.schema.json` → `required:
    ["display_manager_sddm_display_server"]`).
- **Impact:** the file body is proven equal, but the post-move host apply was skipped (handover
  context; this ledger re-ran only the render), so the privileged path (package convergence, Pixie
  fetch/patch, service enable/disable) has not been exercised against the pinned template. A broken
  `install_dir` seam or a changed `become` task would not be caught by the render proof.
- **Planned resolution:** apply the role alone with become:
  `ANSIBLE_CONFIG=ansible/ansible.cfg uv run --directory src/provisioning ansible-playbook
  ansible/playbooks/display-manager.yaml -e install_dir="$HOME/.local/share/dotfiles"
  --ask-become-pass`; expect the template task `ok` (not `changed`), `sddm` enabled, the other DMs
  disabled; then run `dotfiles-provision verify`.
- **Closure proof:** playbook recap `failed=0`; `cmp` of the rendered file; `systemctl is-enabled
  sddm` → `enabled`; `verify` exit 0.

---

---

## Resolved during the split (history — kept so the same gap is not re-opened)

### R-90 — zsh login-shell `become` was unconditional — **CLOSED** (`2f5ee95e`)

The role demanded a sudo password on a host whose shell was already zsh, which broke unattended runs.
It now probes with an unprivileged `getent passwd` (`roles/zsh_config/tasks/main.yml:165-174`),
records the fact, and attaches `become` only to the mutation, gated on the probe differing
(`:200-208`). The regression is executable: `test_zsh_config_role.py:386-419`
(`test_already_zsh_never_invokes_become`) runs the role with a fake become executable and asserts it
was never invoked; `test_wrong_shell_still_attempts_the_privileged_task` covers the other branch.
Resolving commit: `2f5ee95e` ("gate login-shell become…"). Status: **CLOSED** (executed tests in that
commit's evidence; the tests remain in the suite).

### R-91 — `.zshrc.j2` and `wlogout/style.css.tpl` spine residues — **CLOSED** (`2f5ee95e`)

S3 moved the template sources into the pinned corpus, but a pre-S3 `config_copies` directory copy had
left `<spine>/config/zsh/.zshrc.j2` and `<spine>/config/wlogout/style.css.tpl` behind. Both roles now
prune idempotently (`zsh_config/tasks/main.yml:70-73`, `wlogout_config/tasks/main.yml:44-47`) and
`verify` re-asserts absence (`verify/tasks/main.yml:1878-1894` for zsh, `:1922-1938` for wlogout;
paths at `verify/vars/main.yml:879-896`). Tests: `test_zsh_config_role.py:348-361, 657-660`,
`test_verify_role.py:1034-1062, 1069-1096`. Resolving commit: `2f5ee95e`. Status: **CLOSED**.

### R-92 — Duplicate icon-mapping files retired — **CLOSED** (assets `v0.2.0`)

The import did not carry six stale duplicates (`battery.yaml`, `email-client.yaml`, `network.yaml`,
`power-menu.yaml`, `wallpaper-selector.yaml`, `wlogout.yaml`): nothing loaded them, they duplicated
groups owned by `icons.yaml`, and some had drifted. Evidence: `git -C ../dotfiles-assets show
v0.5.0:CHANGELOG.md | sed -n '145,161p'`; consumer-side absence guard
`scripts/deploy-coverage.py:314` (`RETIRED_ICON_MAPPINGS_DIR`) and its use in
`assert_no_assets_corpus`. The assets `validate-icons` gate now fails on any other `*.yaml` under
`icons/mappings/`. Status: **CLOSED**.

### R-93 — Manifest `templates` schema glob did not match the corpus — **CLOSED** (`2f5ee95e`)

The manifest and role mirror carried `**/vars.schema.json`, which matches none of the real
`<name>.vars.schema.json` files. Both now carry `**/*.vars.schema.json`:
`dotfiles/provisioning/assets.yaml:23`, `src/provisioning/ansible/roles/assets/vars/main.yml:22`.
The gate is `test_assets_role.py:610-626` (`test_templates_schema_glob_matches_the_corpus_naming`),
which asserts the string and that it matches a real filename. Resolving commit: `2f5ee95e`. Status:
**CLOSED**.

### R-15 — The engine wheel is not self-contained — **CLOSED** (`v0.1.1`, `de0b92c`)

Engine `v0.1.1` ships `ansible/` as package data under `provisioning/_ansible` (wheel
`force-include` in `pyproject.toml`), resolves it through `importlib.resources` in
`cli/main.py` (checkout fallback kept for editable development), and prepends the interpreter's
bin dir to child `PATH` so the tool venv's `ansible`/`ansible-playbook` resolve. Executed
evidence (2026-10-22):
- `uv build --wheel` → `dotfiles_provision-0.1.1-py3-none-any.whl`; `unzip -l … | awk
  '/provisioning\/_ansible\//'` → **87** entries (was 0 at `v0.1.0`).
- `UV_TOOL_DIR=/tmp/opencode/tool-v011-tag uv tool install
  "git+file://…/dotfiles-provision/.worktrees/residuals-v011@v0.1.1"` from `/tmp` →
  installed; `dotfiles-provision --output-format plain version` → `0.1.1`;
  `… manifests --manifests-dir <composition>` → `success: true`, `count: 5`, exit 0.
- Composition pin bumped to `v0.1.1` (`dotfiles/provisioning/installer.pin`); `bootstrap.sh`
  now installs `git+${ENGINE_REPO_URL}@${ENGINE_PIN}` (the cached checkout remains only for
  `ansible-galaxy`/inventory). `make deploy-coverage` → `CHECK pinned installer engine v0.1.1`,
  exit 0.
- The tag is local in this sweep; a fresh-machine bootstrap needs it pushed to origin (still
  part of R-10's VM proof). Resolving commit: `de0b92c`, tag `v0.1.1`. Status: **CLOSED**.

### R-17 — The engine tag is validated by `engine_checkout.py`, not by `verify` — **CLOSED** (`v0.1.1`, `de0b92c`)

Engine `v0.1.1` adds `verify --expected-engine-tag` → the `expected_engine_tag` extra-var; the
verify role runs `dotfiles-provision --output-format plain version`, normalizes the pin's leading
`v`, and asserts equality before any done-criterion. `bootstrap.sh` now passes
`--expected-engine-tag "$ENGINE_PIN"` on the final verify. Executed evidence (2026-10-22):
- Host verify (engine installed from the local `v0.1.1` tag):
  `dotfiles-provision --manifests-dir … --composition-root … verify --expected-engine-tag v0.1.1`
  → `rc=0`, every task `ok` (tail of the result view).
- Negative execution test: `pytest
  tests/unit/test_verify_role.py::TestEngineTagAssertion
  tests/unit/test_verify_role.py::TestVerifyRuntime::test_engine_tag_is_asserted_against_the_pin
  -q` → `4 passed`; the execution test runs the role with `--tags engine`, passes on `v9.9.9`,
  and fails on `v1.2.3` with both versions in the message.
- Fresh-machine placement remains part of R-10's VM run. Resolving commit: `de0b92c`, tag
  `v0.1.1`. Status: **CLOSED**.

---


### R-11 — S5 `schema_major` window + deployed pin content — **CLOSED** (engine `v0.1.2`, `1b2195f`)

`assets_schema_support` exists in the assets role and mirrors to `verify_assets_schema_support`;
the assets role asserts every `schema_major` before the first copy, and verify slurps
`assets/pinned` and re-reads the deployed contracts. Executed 2026-10-22 in the engine worktree:
`pytest tests/unit/test_assets_role.py -q -k schema` → `10 passed`; `pytest
tests/unit/test_verify_role.py -q -k assets` → `10 passed`; `make deploy-coverage` → PASS with
assets `v0.5.0`. The negative fetch case is in the 10-test selection (`schema_major 2` fails naming
the support window). Status: **CLOSED**.

### R-08 — Stale docs name retired paths — **CLOSED** (this sweep)

Updated `docs/POLKIT_AGENT_INTEGRATION.md` (pinned engine/corpus paths + historical banner),
`docs/99-dotfiles-hexagonal-architecture.md` (current role table, assets/engine note, annotated
patch record), `docs/01-dotfiles-provisioning-phase1-plan.md` and both investigation spikes
(historical banners), and the Bluetooth archive (`tasks.md`/`design.md` provenance banners). The
S7 acceptance grep `rg -n 'src/provisioning|dotfiles/assets/icon-templates' AGENTS.md
ARCHITECTURE.md` → exit 1; remaining `docs` hits are annotated historical rows. Status:
**CLOSED**.

### R-05 — The assets `configs` class has no validator — **CLOSED** (assets `v0.5.1`, `4683c76`)

Added `scripts/validate-configs.py` + `make validate-configs` (a `GATES` member with its own CI
job): no `*.j2`/`*.tpl`, no mutable/rendered file, every file non-empty, and exactly one render
token at `configs/hypr/hyprland.lua:7`. Executed with `PATH` carrying shellcheck:
`make gates-ci` → all gates PASS; the gate prints `PASS -- … exactly one render token at
configs/hypr/hyprland.lua:7`. Negative fixtures: a stray `.j2` fails naming the file; a second
token fails naming both `configs/hypr/hyprland.lua:7` and `configs/hypr/input.lua:31`. No corpus
bytes changed; the composition stays on assets `v0.5.0` (R-12). Status: **CLOSED**.

### R-02 — `TestVerifyRuntime` is red on a clean baseline — **CLOSED** (engine `v0.1.2`)

The fixture seeds the pinned `cli-tools/{csg,weg,itr}` checkouts and `pinned` records, and the WEG
negative-lock stub now reports the pinned `--version` but fails `weg info`. Executed 2026-10-22:
`uv run --with pytest-xdist pytest tests/unit/test_verify_role.py::TestVerifyRuntime -q -n 12`
→ `12 passed in 332.63s`; the class includes the negative locks and the R-17 engine-tag test. The
serial run exceeds five minutes, so the parallel invocation is the reproducible form. Status:
**CLOSED**.

### R-09 — `openspec validate --all` baseline failures — **CLOSED** (this sweep)

`openspec validate --all` → `135 passed, 0 failed (135 items)`; `openspec validate --specs` →
`53 passed, 0 failed`. Fixes: `skip_specs: true` on the 16 changes with no spec deltas, missing
scenarios added to the Bluetooth and capture-dependency changes, `## ADDED Requirements` on the
audio change, `## Purpose`/`## Requirements` added to the three legacy specs, delta headers removed
from the three OCI main specs, and scenarios added to the two OCI specs. Status: **CLOSED**.

### R-06 — `hyprland.lua` carries one render token — **CLOSED** (assets `v0.5.1`)

`make validate-configs` asserts exactly one token at `configs/hypr/hyprland.lua:7`; a second token
fails naming both locations. The file stays in `configs/` (no MAJOR). Status: **CLOSED**.

### R-12 — A docs correction after a release needs a PATCH — **CLOSED** (process)

Runbook line added to `ARCHITECTURE.md` §11: batch docs corrections before tagging; after a tag,
never move it — cut a PATCH; bump consumer pins only for consumed surfaces (catalog, schema, corpus
bytes). `dotfiles-assets v0.5.1` (gate-only, zero corpus bytes) is the dry run and the composition
stays on `v0.5.0`. Status: **CLOSED**.

### R-13 — `dotfiles-provision` is not on `PATH` — **CLOSED** (`99950f7c`)

`make provision ARGS="--help"` runs the installed console from `UV_TOOL_BIN_DIR` and lists
plan/apply/verify/bootstrap (exit 0); `ARCHITECTURE.md` §6.1 documents the short form and marks the
old in-tree `uv run --directory` path retired. Status: **CLOSED**.

### R-14 — Stale-env / `start-limit` trap — **CLOSED** (engine `v0.1.2`, `1b2195f`)

Three executable mitigations: `reset-failed` before enable/start (v0.1.1); a post-install
`direct_url.json` scan that fails naming any `file://` checkout that no longer exists (negative
fixture → `stale uv tool direct_url(s): …` rc=1); and a deployed-unit assert that `ExecStart`
carries no `{%`/`%}` or swallowed `#` continuation. Targeted tests: `92 passed`; the full targeted
suite is `347 passed, 12 deselected`. Status: **CLOSED**.

### R-16 — Composition gates need the cached engine checkout — **CLOSED** (this sweep)

`DOTFILES_PROVISION_OFFLINE=1` turns a cache miss into one sentence with no clone attempt, while a
pre-populated cache still gates offline. Executed: empty cache + offline → `FAIL offline: the
pinned engine checkout is missing at …` rc=1 (no git error); pre-populated cache + offline
`make deploy-coverage` → PASS rc=0. Status: **CLOSED**.


### R-01 — AD-8.4 parity is not run in CI — **CLOSED** (engine `v0.1.2`, run `39947299368`)

The engine CI `assets-parity` job runs `make assets-parity`, which clones the pinned corpus and
fails on any skip. The pushed `v0.1.2` run is green and its log shows
`PASS assets-parity: 7 tests executed, 0 skipped`; `test`/`hermetic` report `937 passed, 38
skipped` (the 38 are the documented non-parity skips). Negative run: cloned assets `v0.5.0`,
appended `fake_required_var_for_negative` to `templates/btop/btop.conf.vars.schema.json`, ran the
parity module with `DOTFILES_ASSETS_REPO`/`DOTFILES_ASSETS_TEMPLATES_DIR` → exit 1 naming
`btop_config … does not supply its required variable(s) ['fake_required_var_for_negative']`.
Status: **CLOSED**.

### R-03 — CI is red on `pillow==11.3.0` under CPython 3.15 — **CLOSED** (run `39947309809`)

All five `setup-uv` steps pin `python-version: "3.14"`. The pushed composition run is green:
`contracts-check`, `runtime-architecture`, `ansible-embedded-template-lint`, `deploy-coverage`,
`ci-gates-parity`, `per-app-drift-symbol-suites` all `success`; the logs show
`Using CPython 3.14.9` and no `Failed to build pillow`. Status: **CLOSED**.


### R-07 — `dotfiles/config/btop/active-theme` was still in the composition repo — **CLOSED** (ags-apps `v0.4.1`, engine `v0.1.4`)

The studio now writes the active-theme setting through `activeThemePath()` to
`<install>/config/btop/active-theme` (`btop-theme-studio/ui/StudioWindow.tsx`,
`lib/targets.ts`; ags-apps `66dc3c9`, tag `v0.4.1`). Engine `v0.1.4` (`d97c697`) reads the same
spine path and seeds it once from the legacy composition path, so an existing selection survives
the migration. The composition deletes `dotfiles/config/` and `deploy-coverage` asserts the tree is
absent (`dotfiles/ holds ['provisioning'] (config/ is absent; the active-theme is spine host
state)`). Executed evidence: `make btop-theme-studio-tests` → all suites pass (targets includes the
new path and the no-old-path guard); engine targeted suite `383 passed, 12 deselected`; btop
integration `2 passed`; composition `make gates-ci` → all six green; host
`verify --expected-engine-tag v0.1.4` → `rc=0`, `failed=0`. Status: **CLOSED**.

## Corrections made while writing this ledger

These are the places where the handover text and the executed evidence disagreed. They are recorded
here so a later reader does not "fix" the ledger back to the unverified wording.

| # | Handover said | Measured / corrected | Where |
| --- | --- | --- | --- |
| C-1 | R-02: "9 tests red on baseline" | **6 of 9 failed, 3 passed** at `2f5ee95e` (the 3 are negative tests that expect failure). The class is red; the count is 6. | R-02 detail |
| C-2 | R-10: gate is `dev/vm-fresh.sh && dev/vm-verify` | There is **no `dev/vm-verify`**; the entry points are `make vm-fresh` / `make vm-verify` → `./dev/vm` → `dev/vm-assert.sh` (`dev/vm:126-131`). The same wrong command is written in 7 slice blocks + `SLICES.md:29-30`. | R-10 detail |
| C-3 | R-10 cites `ARCHITECTURE.md:563` for the incus reason (`SLICES.md:29-30`) | The "No VM in CI … incus is absent" statement is `ARCHITECTURE.md:597`; line 563 is provisioning recipe prose. | R-10 detail |
| C-4 | R-01: parity "SKIPS in CI" | It is not run by any CI job today (`grep` of `gates.yml` → 0 provisioning references); if a job ran it on a bare checkout it would skip. The stronger measured statement is used. | R-01 detail |
| C-5 | R-05: "no `validate-configs` gate" | True at `v0.5.0`, but the sibling assets repo advanced from `v0.4.0` to `v0.5.0` during measurement (S4 landed). Assets citations are tag-qualified; the `GATES` line is 36 at `v0.5.0`, 35 at `v0.4.0`. | R-05 detail / measurement env |
| C-6 | R-12: `v0.3.1` docs correction | True; the stable citation is `git show v0.3.1:CHANGELOG.md \| sed -n '8,20p'` (the current working-tree line is 104 because `v0.4.0`/`v0.5.0` entries were added above it). | R-12 detail |
| C-7 | R-11: S5 step 4 "the current gate has none" | Only half true: `deploy-coverage` already asserts the retired corpus and the render-role pin shape (S1–S3). S5 adds the manifest repo/semver + role↔verify mirror parity to that gate (the parity unit tests exist but run in no CI job — R-01), not a duplicate absence check. | R-11 detail |
| C-8 | WIP changelog: R-02 "records the executed pass/negative evidence" | Not executed. The class collects 12 tests and exceeded a 290 s timeout (two tests in); the single green-path test exceeded 250 s because it runs the whole role. The fixture repair and WEG stub are real, but R-02 stays OPEN. | R-02 detail |
| C-9 | R-15 planned resolution: a self-contained wheel makes `git+…@tag` enough | The wheel is self-contained, but uv exposes only the project entry point on the tool bin dir, so `ansible`/`ansible-playbook` were still missing from `PATH`. `v0.1.1` also prepends the interpreter's bin dir to every child (`adapters/ansible_env.py`). | R-15 resolved |
| C-10 | R-13: canonical invocation `uv run --directory src/provisioning` | That tree was deleted by S6b; the form is no longer runnable. Use the installed tool or `uv run --directory .dev/dotfiles-provision-<tag>`. | R-13 detail |

## Evidence log — commands run for this ledger

| Used by | Command | Observed result |
| --- | --- | --- |
| Baseline | `git status --porcelain` / `git log --oneline -1` | empty / `2f5ee95e …` |
| R-01 | `grep -c 'DOTFILES_ASSETS' .github/workflows/gates.yml`; `grep -c 'src/provisioning' …` | `0`; `0` |
| R-01 | `grep -n '^  [a-z].*:$' .github/workflows/gates.yml` | six job keys, none a provisioning test |
| R-02 | `uv run --directory src/provisioning pytest tests/unit/test_verify_role.py::TestVerifyRuntime -q` | `6 failed, 3 passed in 219.62s`; `File not found: …/cli-tools/itr/pinned` |
| R-03 | `gh run view 39810366803 --log-failed` | `Using CPython 3.15.1`; `error: Failed to build pillow==11.3.0` |
| R-03 | `gh run list --workflow=gates --limit 40 --json conclusion …` | 40 failures, 0 successes |
| R-04 | Jinja render of `sddm.conf.j2` with `display_manager_sddm_display_server=wayland`, sha256 vs `/etc/sddm.conf.d/10-dotfiles.conf` | both `f2899e15…`; `byte_identical True` |
| R-05 | `git -C ../dotfiles-assets show v0.5.0:Makefile \| grep -n 'GATES :='`; `ls scripts/` | line 36, no `validate-configs`; no `validate-configs.py` |
| R-06 | `git -C ../dotfiles-assets show v0.5.0:configs/hypr/hyprland.lua \| sed -n '7p'` | `local cfg = "{{ compositor_configs_xdg_config_home }}/hypr"` |
| R-07 | `find dotfiles/config -type f`; `cat dotfiles/config/btop/active-theme` | one file: `dotfiles/config/btop/active-theme`; `colors.btop.theme` |
| R-09 | `openspec validate --all`; `openspec validate --specs` | `104 passed, 27 failed (131 items)`; `41 passed, 8 failed (49 items)` |
| R-10 | `bash dev/check-prereqs.sh < /dev/null`; `command -v incus`; `ls dev` | exit 1, "incus is not installed"; no output; no `vm-verify` |
| R-11 | `grep -rn 'assets_schema_support' src dotfiles scripts` | no output (0 matches) |
| R-12 | `git -C ../dotfiles-assets diff --stat v0.3.0 v0.3.1`; `rev-parse v0.3.1` | 5 files, 79/21; `4359b4f…` (`2ecd7cb`) |
| R-13 | `command -v dotfiles-provision`; `uv run --directory src/provisioning dotfiles-provision --help` | exit 1; exit 0, four commands |
| R-14 | `grep -rn 'direct_url' src/provisioning/ansible src/provisioning/src src/runtime/src`; `grep -rn 'reset-failed' …` | one comment (`cli_tools/tasks/main.yml:289`); no matches |
| R-90 | `pytest … test_zsh_config_role.py -k already_zsh` (from the resolving commit's evidence) | the test exists at `:386-419`; see the commit's recorded evidence |
| R-92 | `git -C ../dotfiles-assets show v0.5.0:CHANGELOG.md \| sed -n '145,161p'` | the six-file retirement entry |
| R-93 | `grep -n 'templates: { dest: templates' dotfiles/provisioning/assets.yaml …roles/assets/vars/main.yml` | both `**/*.vars.schema.json` |
| R-15 | `uv build --wheel` in `.dev/dotfiles-provision-v0.1.0`; `unzip -l … \| grep -E ' ansible/' \| wc -l`; `tar -tzf ….tar.gz \| grep -c '/ansible/'` | wheel built; **0** `ansible/` entries; sdist **87** |
| R-15 | `sed -n '106p' .dev/…/src/provisioning/cli/main.py`; `sed -n '329,368p' bootstrap.sh` | `_ANSIBLE_ROOT = … parents[3] / "ansible"`; editable install with the wheel/`ansible` reason |
| R-16 | empty cache + unreachable proxy (command in R-16) | exit 1, `FAIL cannot fetch the pinned installer engine v0.1.0 … Offline is a hard failure, never a silent pass` |
| R-17 | `rg -n 'dotfiles-provision\|installer\.pin\|provisioning_version\|engine tag' .dev/…/ansible/roles/verify` | 2 matches, both comments (`tasks/main.yml:62,70`); no task |
| R-01 fix | engine `v0.1.1`: `make assets-parity` | `PASS assets-parity: 7 tests executed, 0 skipped` |
| R-01 close | engine CI run `39947299368` (tag `v0.1.2`): `assets-parity` job log | job success; `PASS assets-parity: 7 tests executed, 0 skipped`; `test`/`hermetic` 937 passed |
| R-01 negative | cloned assets `v0.5.0` + fake required name; parity module | exit 1 naming `['fake_required_var_for_negative']` |
| R-02 update | engine `v0.1.1`: `timeout 290 uv run pytest …::TestVerifyRuntime -q`; single green-path test | `rc=124` (two tests in); single test `rc=124` after 250 s — not closed |
| R-03 fix | `.github/workflows/gates.yml`: `python3 -c 'yaml.safe_load(...)'` | YAML ok; five `setup-uv` steps carry `python-version: "3.14"` |
| R-03 close | composition CI run `39947309809`: all six jobs | `success`; logs `Using CPython 3.14.9`; no `Failed to build pillow` |
| R-14 fix | engine `v0.1.1`: `test_start_limit_is_cleared_before_enable_start` | passed in the 286-test targeted run; stale-env preflight still absent |
| R-15 fix | `uv build --wheel`; `unzip -l … \| awk '/provisioning\\/_ansible\\//'` | `dotfiles_provision-0.1.1-py3-none-any.whl`; **87** `_ansible/` entries |
| R-15 fix | isolated `UV_TOOL_DIR` install `git+file://…@v0.1.1` from `/tmp`; `version`; `manifests` | installed; `0.1.1`; `success: true`, `count: 5`, exit 0 |
| R-15 fix | composition `make deploy-coverage` after pin bump | `CHECK pinned installer engine v0.1.1 …`; PASS, exit 0 |
| R-17 fix | host `dotfiles-provision … verify --expected-engine-tag v0.1.1` | `rc=0`, every task `ok` |
| R-17 fix | `pytest TestEngineTagAssertion …::test_engine_tag_is_asserted_against_the_pin -q` | `4 passed`; `v1.2.3` mismatch fails naming both versions |
| Engine gates | `uv run pytest tests/test_packaging.py tests/unit/application/test_verify_capability_use_case.py tests/unit/cli/test_commands.py tests/unit/test_runtime_daemon_role.py tests/unit/test_verify_role.py tests/unit/adapters -q -m 'not integration'` | `286 passed, 12 deselected in 30.56s`; ruff + mypy clean; lock/docs/ci-gates-parity green |
| R-11 close | engine `pytest test_assets_role.py -q -k schema`; `pytest test_verify_role.py -q -k assets`; `make deploy-coverage` | `10 passed`; `10 passed`; PASS with assets `v0.5.0` |
| R-02 close | engine `pytest …::TestVerifyRuntime -q -n 12` (pytest-xdist) | `12 passed in 332.63s` |
| R-05 close | assets `make gates-ci` (shellcheck shim); negative `.j2` and second-token fixtures | all gates PASS; negatives fail naming the file / both `:7` and `:31` locations |
| R-09 close | `openspec validate --all`; `openspec validate --specs` | `135 passed, 0 failed`; `53 passed, 0 failed` |
| R-13 close | `make provision ARGS=--help` | exit 0; plan/apply/verify/bootstrap listed |
| R-14 close | engine targeted suite `347 passed`; stale `direct_url.json` negative; unit assertions | negative rc=1 naming the missing `file://` checkout; ExecStart assert present |
| R-16 close | empty cache + `DOTFILES_PROVISION_OFFLINE=1`; pre-populated cache + offline `make deploy-coverage` | one-sentence `FAIL offline: …`, rc=1, no clone; PASS rc=0 offline |
| R-08 close | `rg -n 'src/provisioning\|dotfiles/assets/icon-templates' AGENTS.md ARCHITECTURE.md` | exit 1 (no live rows) |
| R-07 blocker | `rg -n 'active-theme' <ags-apps>/btop-theme-studio` | `StudioWindow.tsx:179`, `targets.ts:22` still write `dotfiles/config/btop/active-theme` |
| R-04 blocker | `sudo -n true` | exit 1 (no passwordless sudo); host apply not run |
| R-15/R-17 host | tag install + `verify --expected-engine-tag v0.1.2` | installed `1b2195f`; verify `rc=0`, every task `ok` |
| R-07 close | `make btop-theme-studio-tests` (ags-apps `v0.4.1`); engine targeted suite; btop integration | all studio suites pass; `383 passed, 12 deselected`; `2 passed` |
| R-07 close | composition `make gates-ci`; `deploy-coverage`; host `verify --expected-engine-tag v0.1.4` | six gates green; `dotfiles/ holds ['provisioning'] (config/ is absent …)`; host `rc=0`, `failed=0` |
| R-07 host note | `rfkill list bluetooth` was soft-blocked before the first verify | `rfkill unblock bluetooth` → unblocked; the retry passed (host state, not a code defect) |

Every open item above names a closure proof that re-runs the same kind of observation. When an item
is closed, move it to *Resolved during the split* with the command output and the resolving commit;
that move is the only thing that makes this ledger shorter.
