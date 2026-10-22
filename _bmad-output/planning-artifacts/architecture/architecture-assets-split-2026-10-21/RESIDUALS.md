---
name: 'Assets split — residual ledger'
type: residual-ledger
purpose: 'Keep every known gap in the assets split visible, with its evidence, until it is closed by executed evidence'
status: open
created: '2026-10-22'
updated: '2026-10-22'
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
| Ansible | from `src/provisioning/.venv` via `uv run --directory src/provisioning` |
| Assets checkout | `../dotfiles-assets` at `v0.5.0` (`d894f9b`); the composition repo still pins `v0.4.0` (`dotfiles/provisioning/assets.yaml:20`) — S4's consumer cut is not merged at the baseline |
| Measurement date | 2026-10-22 |

> The assets checkout advanced from `v0.4.0` (`92100a6`) to `v0.5.0` (`d894f9b`) while this ledger was
> being measured. That is why every assets citation names the tag it was read at; a bare line number
> in a sibling checkout is not reproducible.

## Summary — open residuals, in address-at-end order

| ID | Priority | Residual | Closing slice | Status |
| --- | --- | --- | --- | --- |
| R-11 | P1 | Runtime/verify `schema_major` support window and the deployed `assets/pinned` **content** assertion are S5 work, not landed | S5 | OPEN |
| R-07 | P1 | `dotfiles/config/btop/active-theme` — mutable preference still in the composition repo (OPEN-5) | S7 | OPEN |
| R-08 | P1 | Stale docs name retired paths (`docs/POLKIT_AGENT_INTEGRATION.md:67`, `docs/99-…` table, openspec history) | S7 | OPEN |
| R-10 | P1 | VM end-to-end gate never run — `incus` unavailable here; every slice marks it `PLANNED` | final end-to-end (S7 or dedicated) | OPEN-BLOCKED |
| R-01 | P1 | AD-8.4 required-var parity is not run in CI (and would skip without an assets checkout); only the static shape is gated by `deploy-coverage` | S7 / dedicated CI cleanup | OPEN |
| R-05 | P2 | Assets `configs` class has no `validate-configs` gate; content invariants are release-time manual commands | dedicated assets cleanup | OPEN |
| R-04 | P2 | Display-manager host apply skipped after the template move; only the file render is proven byte-identical | dedicated host apply | OPEN |
| R-02 | P2 | `TestVerifyRuntime` is red on a clean baseline: the fixture does not create pinned `cli-tools/{itr,weg,csg}` checkouts (pre-existing) | dedicated cleanup | OPEN |
| R-03 | P2 | `contracts-check` + `runtime-architecture` fail in CI on `pillow==11.3.0` under CPython 3.15 (pre-existing) | dedicated CI cleanup | OPEN |
| R-09 | P2 | `openspec validate --all` → 27 failures (19 change-level + 8 spec-level, pre-existing) | dedicated cleanup | OPEN |
| R-06 | P3 | `hyprland.lua` (configs class) carries one render token — documented exception; moving it is a MAJOR | assets cleanup with R-05 | OPEN (accepted) |
| R-12 | P3 | A docs correction after a release forces a PATCH tag (`v0.3.1` happened) — process note | S7 process | OPEN |
| R-13 | P3 | `dotfiles-provision` is not on `PATH`; run it through `uv run --directory src/provisioning` | S7 docs | OPEN |
| R-14 | P3 | Host stale-env / systemd `start-limit` trap after package-tree moves: documented, no provisioning-time mitigation | dedicated installer cleanup | OPEN |
| R-15 | P2 | The engine wheel is not self-contained — it packages `provisioning/` only, no `ansible/`; bootstrap installs the checkout editable | `dotfiles-provision` packaging (next engine tag) | OPEN |
| R-16 | P2 | Composition gates need the cached engine checkout; a cold offline checkout cannot gate | dedicated installer/CI cleanup | OPEN |
| R-17 | P2 | The engine tag is validated by `engine_checkout.py`, not by `verify` on a fresh machine | `dotfiles-provision` + host/VM proof | OPEN |

---

## Open residuals

### R-11 — S5: `schema_major` window + deployed `assets/pinned` content

- **Priority / status:** P1 · OPEN · **Owner:** S5 (the scheduled contract slice).
- **Evidence:**
  - `verify/tasks/main.yml:918-921` states the gap in the role itself: *"S5 adds the stronger
    assertion that the pin file's CONTENT equals the manifest tag; this slice asserts presence"*.
  - `verify/tasks/main.yml:922-938`: the assets check is a `stat` over `assets/pinned` + the tag dir
    + five class dirs, asserting one regular file and six directories. It never reads the file.
  - `grep -rn 'assets_schema_support' src dotfiles scripts` → **no output** (0 matches). The variable
    S5 step 1 introduces does not exist.
  - The corpus does carry the versions to check: `git -C ../dotfiles-assets show v0.5.0:icons/schema.json`
    → `"schema_major": 1` at line 3; `…templates/kitty/kitty.conf.vars.schema.json` → line 7. No
    consumer reads either today.
  - `SLICES.md:510-533` is the S5 scope + steps 1–5. Note: step 4's premise ("the current gate has
    none") is now only half true — `deploy-coverage.py:1862-1946` already asserts the retired corpus
    is absent and the five render roles resolve through their pin. S5 should add the **manifest
    repo + semver tag + role/verify mirror parity** to `deploy-coverage` (the mirror parity exists as
    unit tests but runs in no CI job — R-01), not a second absence check.
- **Impact:** a deployed corpus whose `assets/pinned` says `vX` while the directory is `vY` passes
  `verify`; a corpus whose `schema_major` is outside what the consumer parses is deployed happily and
  fails later at render/runtime. AD-12's "provision refuses … verify re-asserts" is prose, not a gate.
- **Planned resolution:** land S5 steps 1–3 and 5 (`assets_schema_support` in the assets role vars,
  mirrored in the manifest and verify; fetch-time `assert` on every `schema_major` before the first
  copy; verify slurps `assets/pinned` and asserts it equals the manifest tag; two negative tests).
  Narrow step 4 as above. OPEN-4's default is "accept exactly one major".
- **Closure proof:**
  ```bash
  uv run --directory src/provisioning pytest tests/unit/test_assets_role.py -q -k schema
  uv run --directory src/provisioning pytest tests/unit/test_verify_role.py -q -k assets
  rg -n 'assets_schema_support' src/provisioning/ansible/roles/{assets,verify}/vars/main.yml
  make deploy-coverage
  ```
  Expected: both pytest runs exit 0 including the negative cases; `rg` finds ≥2 matches; the gate
  exits 0. Also run the negative: point the pin at an older tag and observe the fetch assert name
  the file and the expected window.

### R-07 — `dotfiles/config/btop/active-theme` is still in the composition repo (OPEN-5)

- **Priority / status:** P1 · OPEN · **Owner:** S7 (composition closeout).
- **Evidence:**
  - `find dotfiles/config -type f` → exactly one file: `dotfiles/config/btop/active-theme`.
  - `cat dotfiles/config/btop/active-theme` → `colors.btop.theme` (mutable preference, written by
    the btop studio).
  - `src/provisioning/ansible/roles/btop_config/vars/main.yml:59-63` declares
    `btop_config_active_theme_file: "{{ btop_config_repo_root }}/dotfiles/config/btop/active-theme"`;
    `roles/btop_config/tasks/main.yml:52-63` reads it from the repo path.
  - `ARCHITECTURE-SPINE.md:371-386` (AD-11) forbids it in assets; `:683` (OPEN-5) names this file and
    the default resolution: move it to the spine as a host-owned file, written by the studio and read
    by the renderer.
  - Assets' own boundary agrees: `git -C ../dotfiles-assets show v0.5.0:configs/README.md |
    sed -n '73,75p'` — "Mutable preference and state … neither is in this class".
- **Impact:** S7 step 2's catch-all ("`dotfiles/config/` absent") cannot land while this file exists;
  a mutable preference inside a git-tracked composition repo can be silently reverted by a checkout,
  and a pinned corpus must never hold it.
- **Planned resolution:** per OPEN-5's default, move the file to the install spine as host-owned
  state (a seeded default written on first provision, then owned by the studio), repoint
  `btop_config_active_theme_file` at that path, delete `dotfiles/config/btop/active-theme`, and let
  S7's absence guard assert `dotfiles/config/` is gone. Do **not** put it in assets.
- **Closure proof:** `find dotfiles/config -type f` → no output; `rg -n 'dotfiles/config/btop' src
  dotfiles` → no live reference; a studio round-trip (write theme → render → verify) passes; S7's
  deploy-coverage catch-all exits 0.

### R-08 — Stale docs name retired paths

- **Priority / status:** P1 · OPEN · **Owner:** S7 (step 5's "make the docs true" sweep).
- **Evidence (verified against `2f5ee95e`):**
  - `docs/POLKIT_AGENT_INTEGRATION.md:67` — "Remove from `dotfiles/config/hypr/autostart.lua`". That
    file now ships as `configs/hypr/autostart.lua` in the pinned corpus; the doc is labelled
    **historical** in `ARCHITECTURE.md:629`, and the playbook it asks to import
    (`src/provisioning/ansible/playbooks/polkit-agent.yaml`) does not exist.
  - `docs/99-dotfiles-hexagonal-architecture.md:232` — the role table row
    `| 7 | config_copies | repo dotfiles/config/* → spine config/ |`. `config_copies` now reads the
    pinned `configs` class (`docs/02-config-in-spine-pattern.md:76-77`, `:212`). `:1185` is the same
    stale claim in a present-tense "all IMPLEMENTED" list; `:1285`/`:1288` are a dated Phase-1 patch
    record (historical provenance).
  - `openspec/changes/archive/2026-09-25-bluetooth-row-battery-signal/tasks.md:5` (retired
    `dotfiles/assets/icon-templates/...`) and `design.md:96` — archive provenance, not live
    instructions.
  - S7's own acceptance gate is explicit: `SLICES.md:662-663` (step 5) and `SLICES.md:697-699`
    (`rg -n 'src/provisioning|dotfiles/assets/icon-templates' AGENTS.md ARCHITECTURE.md` → expect
    exit 1, historical dirs excluded).
- **Impact:** a reader following the POLKIT doc edits a file that no longer exists; the as-built
  role table (`Domain 1 As-Built (reference)`, `docs/99-dotfiles-hexagonal-architecture.md:197-235`)
  describes a source that moved. S7's "docs are not lying" gate is a stated acceptance criterion.
- **Planned resolution:** S7 sweep: fix the live/as-built docs; for documents already labelled
  historical, either add a one-line "moved to `dotfiles-assets` at `<tag>`" provenance note or list
  them as an explicit historical exemption in the S7 closeout (do not rewrite archive provenance).
  Also add the missing `dotfiles-provision` invocation form to the same sweep (R-13).
- **Closure proof:** `rg -n 'dotfiles/config/(hypr|zsh)|dotfiles/assets/icon-templates' docs
  AGENTS.md ARCHITECTURE.md` → no live rows (historical rows either annotated or explicitly
  exempted in the S7 closeout); `make gates-ci` exit 0.

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

### R-01 — AD-8.4 parity is developer-only; CI would skip it

- **Priority / status:** P1 · OPEN · **Owner:** S7 (composition gate set) or a dedicated CI cleanup.
- **Evidence:**
  - `src/provisioning/tests/unit/assets_templates.py:18-21` states the skip rule: *"CI has no assets
    checkout, so most of these tests skip there — which is why `test_template_vars_parity.py`
    reports its coverage instead of pretending a skip is a pass."* The skip itself is at `:99-108`
    (`require_templates_root`).
  - `test_template_vars_parity.py:160-222` (`TestRequiredVarsAreSupplied`) resolves the corpus
    through `assets_templates.schema_for` → `require_templates_root`, so both the forward
    (`required[] ⊆ supplied`) and reverse (`explicit vars ⊆ properties`) assertions skip when the
    corpus is absent.
  - `scripts/deploy-coverage.py:1864-1876` is explicit about the split: the CI-runnable half is the
    static shape (retired sources gone, render tasks read `<role>_assets_templates_dir`, pin mirror
    present); the parity test needs the corpus "and skips on a runner without a checkout".
  - Measured: `grep -c 'DOTFILES_ASSETS' .github/workflows/gates.yml` → `0`; `grep -c
    'src/provisioning' .github/workflows/gates.yml` → `0`. The workflow's six jobs are `contracts-check`,
    `runtime-architecture`, `ansible-embedded-template-lint`, `deploy-coverage`, `ci-gates-parity`,
    `per-app-drift-symbol-suites` (`gates.yml:59-143`). The provisioning unit suite — including the
    parity test — runs in **no** CI job today.
  - **Precision correction:** "skips in CI" is true only counterfactually (it would skip if a job ran
    it on a bare checkout). The measured state is stronger: it is not run at all.
- **Impact:** AD-8.4 — the only executable link between the assets schemas and the installer's
  render tasks — is proven on a developer machine with the sibling checkout, never on a push. A
  schema rename or a new required var can merge and pass all six gates; it fails later, on a user's
  machine, at render time.
- **Planned resolution:** add a CI-only job (e.g. `assets-parity`) declared in `CI_ONLY_EXEMPT`
  (`scripts/ci-gates-parity.py:93`) so `gates-ci` stays at its six targets: checkout
  `dotfiles-assets` at the manifest's `assets.tag`, export `DOTFILES_ASSETS_TEMPLATES_DIR`, run
  `uv run --directory src/provisioning pytest tests/unit/test_template_vars_parity.py -q -rs`, and
  fail if any parity test is skipped. Alternatively add `make assets-parity` to `GATES` and accept a
  seventh gate (then update `SLICES.md` S7 step 3's six-target sentence).
- **Closure proof:** a green CI run in which the job log shows the parity tests **executed** (no
  `skipped` for `TestRequiredVarsAreSupplied`, `TestTheCorpusActuallyHasTheseTemplates`), plus a
  negative run: add a fake required name to one schema → the job fails naming the missing var.

### R-05 — The assets `configs` class has no validator

- **Priority / status:** P2 · OPEN · **Owner:** dedicated assets-repo cleanup (after S7; the class
  boundary is already documented).
- **Evidence:**
  - `git -C ../dotfiles-assets show v0.5.0:Makefile | grep -n 'GATES :='` → line 36:
    `validate validate-icons validate-content validate-templates validate-desktop lint hermetic`.
    There is no `validate-configs`; `scripts/` holds `validate-catalog.py`, `-content.py`,
    `-desktop.py`, `-icons.py`, `-templates.py`, `ci-gates-parity.py`, `worktree-guard.sh`.
  - `git show v0.5.0:catalog.yaml | sed -n '44,56p'` → the configs class declares `schema: null`,
    `schema_major: null` (deliberate: no contract file to parse).
  - `git show v0.5.0:configs/README.md | sed -n '77,98p'` → "The per-file boundary has no validator
    of its own at this tag", followed by four **release-time manual commands** (no `.j2`/`.tpl`, no
    `active-theme`, no rendered output, exactly one `{{` at `hyprland.lua:7`).
  - Consumer side: verify only asserts the six configs subdirectories exist
    (`verify/tasks/main.yml:944-962`), and `deploy-coverage` only asserts the in-tree corpus is gone
    (`deploy-coverage.py:1831-1859`). No consumer gate reads the class content.
- **Impact:** a second render token, a stray `.j2`/`.tpl`, a mutable file, or a rendered file under
  `configs/` is caught only if a person runs the README commands at release time. The assets README's
  "Each class validator arrives **with** its corpus" (`git show v0.5.0:README.md | sed -n '28,29p'`)
  is not true for this class; the tag can ship content the release check never saw.
- **Planned resolution:** add `scripts/validate-configs.py` + `make validate-configs` (a `GATES`
  member with its own CI job), implementing the four release commands as executable checks, with
  negative fixtures. Assert exactly one token and name `configs/hypr/hyprland.lua:7` in the failure
  message. This also closes R-06's coverage gap without moving the file.
- **Closure proof:** `make validate-configs` exit 0; a negative test (add a second `{{` token, or a
  `.j2` file) fails naming the file; the assets CI run shows the new job green.

### R-04 — Display-manager host apply skipped after the template move

- **Priority / status:** P2 · OPEN · **Owner:** dedicated host-apply cleanup (or S7's end-to-end with
  R-10).
- **Evidence:**
  - `src/provisioning/ansible/playbooks/display-manager.yaml:14` → `become: true`; the role installs
    packages, fetches/patches Pixie, writes `/etc/sddm.conf.d/10-dotfiles.conf` and enables/disables
    services (`roles/display_manager/tasks/main.yml:38-135`).
  - The render task now reads the pinned corpus
    (`roles/display_manager/tasks/main.yml:68-74` → `{{ display_manager_assets_templates_dir }}/display-manager/sddm.conf.j2`),
    and the pin is `v0.4.0` (`roles/display_manager/vars/main.yml:34-35`).
  - Executed render proof (2026-10-22), reproducible:
    ```bash
    ASSETS=/home/inumaki/Development/dotfiles/dotfiles-assets
    uv run --directory src/provisioning python - "$ASSETS" <<'PY'
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

### R-02 — `TestVerifyRuntime` is red on a clean baseline (pre-existing)

- **Priority / status:** P2 · OPEN (pre-existing, not caused by the split) · **Owner:** dedicated
  cleanup.
- **Evidence (executed at `2f5ee95e`):**
  ```
  uv run --directory src/provisioning pytest tests/unit/test_verify_role.py::TestVerifyRuntime -q
  → 6 failed, 3 passed in 219.62s
  ```
  First failure: `TASK [verify : Read the itr pin record]` fails with
  `File not found: /tmp/…/install/cli-tools/itr/pinned` (`verify/tasks/main.yml:424`).
  - The class has 9 tests. Failing: `test_verify_passes_on_a_provisioned_machine`,
    `test_verify_fails_when_parse_gate_binary_fails`, `test_verify_fails_when_dunst_is_not_masked`,
    `test_verify_fails_when_ags_overlay_is_down`, `test_verify_fails_when_directory_handler_is_wrong`,
    `test_verify_criterion_6_checks_current_only`. Passing:
    `test_verify_fails_when_settings_reference_missing_dir`,
    `test_verify_fails_when_csg_color_template_missing`, `test_verify_fails_when_not_provisioned`
    (negative tests that expect failure anyway).
  - Cause: `_build_provisioned_layout` (`test_verify_role.py:3487-3976`) seeds the spine, the assets
    checkout, the ags units, the runtime state and the `~/.config` links — but no
    `install/cli-tools/{itr,weg,csg}/<tag>/` checkout and no `pinned` records. The verify role's
    pinned-CLI assertions were added on 2026-10-20 (`0bc85765`, "install itr from its pinned repo");
    the fixture's spine set predates that (`1dc9741d`, 2026-08-16).
  - **Correction:** this item was handed over as "9 tests red". Execution narrows that to **6 of 9
    red, 3 passing** at the baseline. The class as a whole is red; the count is 6.
- **Impact:** the only execution test of `verify` — the negative lock that proves the gate is not
  vacuous — cannot run green on a clean master. A real verify regression is indistinguishable from
  the fixture gap, and the class trains developers to ignore a red run.
- **Planned resolution:** extend the fixture with a `_seed_cli_tools(install)` helper that creates
  `install/cli-tools/{itr,weg,csg}/<pinned tag>/` plus the `pinned` files (and whatever the weg image
  reference / itr version assertions require), keeping the negative-lock tests intact. Alternatively
  scope the verify playbook's CLI-pin assertions to a separate execution test and seed them there.
- **Closure proof:** `pytest tests/unit/test_verify_role.py::TestVerifyRuntime -q` → 9 passed;
  delete one criterion element and confirm the negative lock still fails (the class's original
  purpose); no skips.

### R-03 — CI is red on `pillow==11.3.0` under CPython 3.15 (pre-existing)

- **Priority / status:** P2 · OPEN (pre-existing) · **Owner:** dedicated CI cleanup.
- **Evidence:**
  - `gh run view 39810366803` (`2f5ee95e`): jobs `contracts-check` **failure**, `runtime-architecture`
    **failure**; the other four success. Log:
    `Using CPython 3.15.1` … `error: Failed to build \`pillow==11.3.0\`` (also
    `cause: Call to backend.build_wheel failed`).
  - Same failure at `0a33a1da` (run 39804642349, CPython 3.15.1) and `6ab95767` (run 39698753273,
    CPython 3.15.0) — so it predates this ledger and reproduces on multiple master runs.
  - `gh run list --workflow=gates --limit 40` → 40 failures, 0 successes (measured 2026-10-22). The
    count is a run-level observation, not proof that every run failed for this reason; the three
    sampled runs above are.
  - Cause chain: `src/runtime/pyproject.toml:5` (`requires-python = ">=3.14"`) lets `uv` select the
    newest CPython; `:12` caps Pillow at `<12`; `src/runtime/uv.lock:329-332` pins `11.3.0`, whose
    release has no `cp315` wheel, so `uv` builds from the sdist and the build fails. The workflow sets
    no `python-version` (`gates.yml:64,81,94,113,131` are bare `astral-sh/setup-uv@v5`).
- **Impact:** no recent master push has a green CI; the two failing jobs are the contract-source gate
  and the runtime architecture guard, so a real regression in either is invisible behind the install
  failure. "`make gates-ci` is green in CI" is false today.
- **Planned resolution:** pin `python-version: "3.14"` on each `setup-uv` step (or commit a
  `.python-version`) so `uv` selects a CPython with a `cp314` Pillow wheel; alternatively raise the
  Pillow cap only when a `cp315` wheel exists. Then re-run the workflow.
- **Closure proof:** a green run on master where `gh run view <id> --json jobs` shows all six jobs
  `success`, and the log shows `Using CPython 3.14.x` (no `Failed to build`).

### R-09 — `openspec validate --all` baseline failures (pre-existing)

- **Priority / status:** P2 · OPEN (pre-existing) · **Owner:** dedicated cleanup.
- **Evidence (executed at `2f5ee95e`):**
  - `openspec validate --all` → `Totals: 104 passed, 27 failed (131 items)`.
  - `openspec validate --specs` → `Totals: 41 passed, 8 failed (49 items)`.
  - `ARCHITECTURE.md:601` records the same shape: 27 failures = 19 legacy change-level + 8 legacy
    spec-shape defects. The 8 measured `--specs` failures match that decomposition.
  - Representative errors: the `wifi-*` changes fail with "Change must have at least one delta. No
    deltas found" (pure-refactor/doc changes without `skip_specs: true`); `oci-test-contracts` and
    `oci-version-error-contract` fail with delta headers inside a main spec.
- **Impact:** a local quality gate that cannot be green; S7 adds
  `openspec/specs/assets-repo-consumption/spec.md` into a validator with 27 known failures, so a new
  invalid spec is indistinguishable from the baseline.
- **Planned resolution:** triage in two buckets — (a) set `skip_specs: true` in the `.openspec.yaml`
  of the pure-refactor/doc-only changes that legitimately have no deltas; (b) repair the 8 main-spec
  shape defects (move delta headers/content back under `## Requirements`, or rewrite the requirements
  in place). If full repair cannot land before S7, record the exact failing names and add a
  "no new failures" ratchet (diff the failing set before/after) rather than claiming green.
- **Closure proof:** `openspec validate --all` → `0 failed`; `openspec validate --specs` → `0 failed`;
  or a recorded baseline file + a script that fails only on a newly-added failing name.

### R-06 — `hyprland.lua` carries one render token (accepted exception)

- **Priority / status:** P3 · OPEN (accepted, documented) · **Owner:** the assets cleanup that closes
  R-05 (do not move the file).
- **Evidence:**
  - `git -C ../dotfiles-assets show v0.5.0:configs/hypr/hyprland.lua` → line 7:
    `local cfg = "{{ compositor_configs_xdg_config_home }}/hypr"`.
  - `git -C ../dotfiles-assets show v0.5.0:configs/README.md | sed -n '46,58p'` documents it as
    the one render-time value; the class is "deployment-fixed", not brace-free.
  - `git -C ../dotfiles-assets show v0.3.1:CHANGELOG.md | sed -n '8,20p'` records the boundary
    correction (the v0.3.0 README had claimed "nothing here is rendered").
  - Consumer: `compositor_configs` deploys this one entry with `template`, not `copy`
    (`roles/compositor_configs/vars/main.yml:118-131`; task comment at
    `roles/compositor_configs/tasks/main.yml:31`).
- **Impact:** one file in a "configs" class is rendered; the class contract now has an exception a
  future contributor can widen silently (no gate — see R-05). Moving it to `templates/` would change
  its addressed path and therefore require a MAJOR tag, which the split does not need.
- **Planned resolution:** keep the file where it is. R-05's `validate-configs` asserts exactly this
  one token (the `grep -rn '{{' configs` release command), so a second token fails. No MAJOR.
- **Closure proof:** `make validate-configs` asserts one line, `configs/hypr/hyprland.lua:7`; adding a
  second token in a negative fixture fails.

### R-12 — A docs correction after a release needs a PATCH (process note)

- **Priority / status:** P3 · OPEN · **Owner:** S7 process/runbook.
- **Evidence:**
  - `git -C ../dotfiles-assets show v0.3.1:CHANGELOG.md` → lines 8-20: "The `configs/` boundary prose
    was wrong for `hypr/hyprland.lua`… Corpus bytes are identical to v0.3.0 — this is a documentation
    correction, and the tag is new rather than moved."
  - `git -C ../dotfiles-assets diff --stat v0.3.0 v0.3.1` → 5 files (CHANGELOG, README, catalog.yaml,
    configs/README.md, openspec spec), 79 insertions / 21 deletions — no corpus file.
  - `git -C ../dotfiles-assets rev-parse v0.3.1` → `4359b4f…` (`2ecd7cb`, "docs(configs): the
    boundary is deployment-fixed, not brace-free"). The tag was created new; the v0.3.0 tag was not
    moved.
- **Impact:** a consumer pinned at `v0.3.0` never sees the corrected README/catalog. The fix cost a
  PATCH tag for prose alone; repeated doc slips add tag noise, and a consumer that treats
  README/catalog as the consumed surface must bump its pin for a typo.
- **Planned resolution:** add a release-runbook line (assets repo + S7 pin table): batch docs
  corrections before tagging; after a tag, cut a PATCH and never move the tag; bump the consumer pin
  only when the corrected file is a consumed surface (catalog/schema), otherwise record the correction
  and leave the pin. The next docs-only correction is the dry run.
- **Closure proof:** the runbook path + line exist; the next docs-only change either lands before its
  tag or ships as a PATCH with the same 5-file shape (no corpus bytes).

### R-13 — `dotfiles-provision` is not on `PATH`

- **Priority / status:** P3 · OPEN · **Owner:** S7 docs (one line) plus an optional Makefile helper.
- **Evidence:**
  - `command -v dotfiles-provision` → no output (exit 1).
  - The console script exists only inside the project venv:
    `src/provisioning/.venv/bin/dotfiles-provision` exists.
  - The declared script is `src/provisioning/pyproject.toml:14-15`
    (`dotfiles-provision = "provisioning.cli.main:app"`).
  - The canonical invocation is `uv run --directory src/provisioning dotfiles-provision …`
    (`bootstrap.sh:415,421`; `ARCHITECTURE.md:172-173`), and it works:
    `uv run --directory src/provisioning dotfiles-provision --help` exits 0 and lists
    `plan|apply|verify|bootstrap`.
- **Impact:** a reader copy-pasting `dotfiles-provision verify` from a ticket or an older doc gets
  `command not found`; the docs assume a PATH install that the repo deliberately does not create.
- **Planned resolution:** add a `make provision ARGS="verify"` wrapper that runs the `uv run` form,
  and a one-line note in `src/provisioning/README.md` (the repo has no root `README.md`) plus the S7
  docs sweep. Do not add a global install step to provisioning; the pinned-engine model wants the
  source dir.
- **Closure proof:** from a clean shell, `make provision ARGS=--help` exits 0 and prints the four
  commands; the note is in the docs.

### R-14 — Stale-env / `start-limit` trap has no provisioning-time mitigation

- **Priority / status:** P3 · OPEN (idea) · **Owner:** dedicated installer cleanup (post-split).
- **Evidence:**
  - `ARCHITECTURE.md:598` documents the systemd trap: an `ExecStart` line ending in a Jinja block tag
    gets the next line merged (`daemon run# …` → `No such command 'run#'` → `start-limit-hit`);
    `roles/runtime_daemon/vars/main.yml:26-35` is the workaround, and the unit template repeats the
    warning (`roles/runtime_daemon/templates/dotfiles-runtime-daemon.service.j2:24-30`).
  - `ARCHITECTURE.md:599` documents the stale uv-tool env: `uv tool list` can report the right version
    while `direct_url.json` points at a deleted path, so every console dies with
    `ModuleNotFoundError` after a tree move.
  - Neither has a provisioning-time check: `grep -rn 'direct_url' src/provisioning/ansible
    src/provisioning/src src/runtime/src` → one comment only (`roles/cli_tools/tasks/main.yml:289`);
    `grep -rn 'reset-failed'` in the same roots → no matches. `daemon_reload` exists
    (`display_manager/tasks/main.yml:122`, `runtime_daemon/handlers/main.yml:22`) but does not detect
    the stale-env case or clear a start-limit.
- **Impact:** after a package-tree move, a host can look provisioned while its tool consoles are
  dead; a unit that hit `start-limit` stays down until a human runs `reset-failed`, and the next
  provision can report green because the unit is merely "enabled".
- **Planned resolution (idea, not decided):** add a preflight to `bootstrap`/`apply` that (a) scans
  `~/.local/share/uv/tools/*/…/direct_url.json` for URLs under retired roots and reinstalls those
  tools, (b) after unit render asserts `systemctl --user show -p ExecStart <unit>` contains no `{%`
  or swallowed `#` continuation, and (c) runs `daemon-reload` + `reset-failed` before
  `enable --now`. A negative fixture with a stale `direct_url.json` and a block-ending `ExecStart`
  proves both checks bite.
- **Closure proof:** the preflight fails on both negative fixtures and passes on a clean host; a real
  host apply after a tree move comes up with the daemon active and no `start-limit-hit`.

### R-15 — The engine wheel is not self-contained (S6 packaging caveat)

- **Priority / status:** P2 · OPEN · **Owner:** `dotfiles-provision` packaging (next engine tag).
- **Evidence (2026-10-22, engine checkout at `v0.1.0`):**
  - `pyproject.toml`'s wheel target is `packages = ["src/provisioning"]`; only
    `[tool.hatch.build.targets.sdist] only-include` lists `ansible`.
  - `cd .dev/dotfiles-provision-v0.1.0 && uv build --wheel --out-dir /tmp/opencode/engine-dist`
    → `Successfully built …/dotfiles_provision-0.1.0-py3-none-any.whl`; then
    `unzip -l …/dotfiles_provision-0.1.0-py3-none-any.whl | grep -E ' ansible/' | wc -l` → **0**.
    The same tree's sdist has the tree: `tar -tzf /tmp/opencode/engine-dist/*.tar.gz | grep -c
    '/ansible/'` → **87**.
  - The CLI locates it beside the package: `src/provisioning/cli/main.py:106`
    (`_ANSIBLE_ROOT = Path(__file__).resolve().parents[3] / "ansible"`), which resolves into the
    checkout (editable) and into a `lib/pythonX/ansible` that does not exist (installed wheel).
  - `bootstrap.sh:329-368` therefore clones the tag and runs
    `uv tool install --force --editable "$ENGINE_DIR"`, with the reason in its comment.
- **Impact:** the engine cannot be installed from a wheel or `git+…@tag` (the console script starts
  but every playbook path is missing); the composition's "pinned tag" is still true for the
  **checkout**, not for a portable artifact. Publishing to PyPI would ship an unusable console.
- **Planned resolution:** make `ansible/` package data of the Python package (or resolve it via
  `importlib.resources`), release a new engine tag, and switch `bootstrap.sh` to
  `uv tool install git+…@<tag>`; keep the checkout install for engine development only.
- **Closure proof:** `unzip -l` the new wheel → an `ansible/` entry count > 0; install it into an
  isolated `UV_TOOL_DIR` from the tag; then `dotfiles-provision --help` and a `bootstrap --check`
  against the composition manifests exit 0 without the checkout.

### R-16 — Composition gates need the cached engine checkout

- **Priority / status:** P2 · OPEN · **Owner:** dedicated installer/CI cleanup.
- **Evidence (2026-10-22):** with an empty cache and an unreachable proxy, the gate fails rather
  than skips:

  ```text
  $ DOTFILES_PROVISION_CACHE_DIR=/tmp/opencode/engine-offline \
      HTTPS_PROXY=http://127.0.0.1:9 https_proxy=http://127.0.0.1:9 \
      uv run --no-project --with pyyaml python scripts/deploy-coverage.py   # exit 1
  FAIL cannot fetch the pinned installer engine v0.1.0 into
  /tmp/opencode/engine-offline/dotfiles-provision-v0.1.0 (fatal: unable to access
  'https://github.com/RandomGenericUsername/dotfiles-provision/': Failed to connect
  to github.com:443 over proxy 127.0.0.1 after 0 ms: Could not connect to server).
  The composition gates need the engine checkout; connect once, or pre-populate
  /tmp/opencode/engine-offline/dotfiles-provision-v0.1.0 at v0.1.0. Offline is a
  hard failure, never a silent pass.
  ```

  `scripts/engine_checkout.py:65-140` is the only resolver; `fetch=False` raises with the same
  path/pin but no gate exposes it as a mode.
- **Impact:** a cold, network-less composition checkout (a sealed CI runner, a review laptop) cannot
  run `make deploy-coverage` or `make gates-ci`, even though nothing on the host changed. The
  failure is loud and correct — but it is an availability gap, not a shape gap.
- **Planned resolution:** cache `.dev/dotfiles-provision-<tag>/` in CI keyed by the pin, document the
  pre-populate command in `bootstrap.sh`/`ARCHITECTURE.md` (done in §12), and surface an explicit
  `--offline`/`DOTFILES_PROVISION_OFFLINE=1` mode that turns a missing cache into one sentence
  instead of a `git` error. Do not vendor the engine tree here.
- **Closure proof:** on a network-disabled runner with a pre-populated cache, `make deploy-coverage`
  exits 0; with the cache absent and the offline mode set, it exits 1 with the one-sentence message
  and no clone attempt.

### R-17 — The engine tag is validated by `engine_checkout.py`, not by `verify`

- **Priority / status:** P2 · OPEN · **Owner:** `dotfiles-provision` + host/VM proof.
- **Evidence (2026-10-22):**
  - `scripts/engine_checkout.py:35-101` validates the pin's semver shape and the cached checkout's
    HEAD equals the tag — but only on the machine that runs the gate.
  - The engine's `verify` role has **no** engine-tag assertion:
    `rg -n 'dotfiles-provision|installer\.pin|provisioning_version|engine tag'
    .dev/dotfiles-provision-v0.1.0/ansible/roles/verify` → only two comments
    (`tasks/main.yml:62,70`), no task.
  - `bootstrap.sh:488-501` passes `--manifests-dir`, `--composition-root` and `--inventory` to
    `verify`, but not an expected engine tag.
- **Impact:** on a fresh machine, "which engine provisioned this host?" is answered by the bootstrap
  log's `engine install (vX.Y.Z)` line and the installed tool env, not by `verify`. A hand-run
  `verify` against a different engine checkout can be green while claiming the composition's tag.
- **Planned resolution:** add `expected_engine_tag` as a verify extra-var, assert
  `dotfiles-provision version` (or its installed metadata) equals it, and have `bootstrap.sh` pass
  `-e expected_engine_tag="$ENGINE_PIN"`; keep the composition's `installer.pin` as the one source.
- **Closure proof:** `dotfiles-provision verify -e expected_engine_tag=v0.1.0` exits 0 on a host
  provisioned from that tag; passing `v9.9.9` fails naming both the expected and observed tags. On a
  fresh machine this must be part of the VM run still tracked by R-10.

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

---

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

Every open item above names a closure proof that re-runs the same kind of observation. When an item
is closed, move it to *Resolved during the split* with the command output and the resolving commit;
that move is the only thing that makes this ledger shorter.
