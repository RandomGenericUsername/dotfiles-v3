# Gate 2 Review — R‑3 (Derivation Inputs Spine‑Only)

Status: APPLIED — all items resolved and verified (runtime 1006 passed/2 skipped; provisioning verify 43 passed; ruff/mypy no new; layering green; verify syntax rc=0).

## Applied

- **Item 1** `find` now `recurse: true`; `test_verify_role._build_provisioned_layout` seeds nested `icon-templates` + flat csg templates + sibling mappings → the 3 red provisioning tests are green.
- **Item 2** dev repo candidates repointed at `dotfiles/assets/icon-templates/` and `dotfiles/config/icon-template-color-scheme-mappings/`; test uses the real layout.
- **Item 3** a repo‑sourced input now reports `status="diverged"` → `doctor` is not clean / exits 1; new test.
- **Item 4** the dead repo‑ancestor fallback in `itr_adapter.py` removed (inputs are injected; else a clear error).
- **Item 5** sibling `icon-mappings/*.yaml` pinned in verify; `verify_derivation_template_dirs` added to the not‑empty guard.
- **Item 6** `require_input` enumerates all spine candidates; warn‑once for the override; `derive.py` docstring updated; tests `delenv` the override for isolation.
- **Item 7** tests: repo‑shaped ancestor ignored without override; `require_input` parametrized over all four keys.
- **Ratified:** `find_*` stay non‑raising (`None` = absent) for the read‑only check wiring; the derivation path raises `MissingDerivationInputError`.

---

## Original review (pre-apply)

## Verification

- Runtime: 1000 passed, 2 skipped; ruff/mypy no new; layering green; `verify` playbook syntax rc=0.
- Panel: Blind Hunter = patches required; Edge Hunter = several; Acceptance Auditor = **REWORK** (AC1/AC2 pass; **AC3 FAIL**, **AC4 partial**). Provisioning test suite is red (3 `test_verify_role` failures) — introduced by this change.

## Blocking

### Item 1 — `verify` false‑fails on a correctly provisioned machine (AC3, critical)

**Problem:** the new `find` task (`verify/tasks/main.yml:237`) uses `ansible.builtin.find` with default `recurse: false`, but `<install>/icon-templates` has **0 top‑level files** (all 55 are nested `status-bar/.../icon.svg`). So `... | min > 0` fails on a healthy install. Reproduced by both hunters; the provisioning suite (`test_verify_role.py::TestVerifyRuntime` ×3) is red because the fixture builds empty template dirs.

**Patch:** add `recurse: true` to the find task; update `_build_provisioned_layout` (`test_verify_role.py:1538`) to seed flat csg templates + nested icon‑templates; assert the provisioning suite green.

### Item 2 — the dev override does not work for icon inputs (AC2, critical)

**Problem:** the repo candidates for `icon_templates`/`icon_mappings` point at `src/cli-tools/icon-templates-renderer/...` which **does not exist** in this repo (real sources: `dotfiles/assets/icon-templates/`, `dotfiles/config/icon-template-color-scheme-mappings/`). With `DOTFILES_DEV_INPUTS_ROOT=$PWD`, icons resolve `missing`. The new test passes only because it fabricates the wrong layout.

**Patch:** repoint the two repo candidates at the real assets‑role sources (add the mappings **dir** form too); fix `_populate_repo` to build the real paths; add a parity test reading `assets/vars/main.yml` sources.

### Item 3 — AC4: repo‑sourced provenance is not surfaced loudly

**Problem:** `doctor._check_input_provenance` classifies a repo‑sourced input as `status="ok"` (detail only) → `clean` stays True and the CLI exits 0; a leaked `DOTFILES_DEV_INPUTS_ROOT` is invisible to exit‑code checks. AC4 wants it loud in production. No test covers a `source=="repo"` doctor item.

**Patch:** give repo‑sourced a non‑`ok` status (it can only arise with the override set, i.e. wrong outside dev) so it dirties `clean`/exit code (or gate it behind an explicit dev‑mode flag); add a doctor test for a repo item.

## Should‑fix (edge finds)

### Item 4 — a second silent repo walk survives

`adapters/itr_adapter.py` keeps `_find_default_icon_templates()`/`_find_default_icon_mappings()` walking repo ancestors (`:55-104`). Unreachable from the pipeline today (paths always injected) but it's a live re‑entry point for the exact bug AD‑43 removes. Delete it or gate it behind the override.

### Item 5 — verify sibling mappings (AC3 literal)

AD‑43 says `icon-mappings/icons.yaml` **+ siblings**; only `icons.yaml` is asserted. Pin the sibling set (or assert the dir non‑empty). Also add `verify_derivation_template_dirs` to the existing "list vars not empty" guard so an emptied list fails friendly, not with a `min` error.

### Item 6 — resolver hardening

`require_input` names only the first spine candidate (enumerate all); decide whether `icon_mappings` may be a **dir** (runtime accepts it, verify now requires the file — contract skew); dedupe the dev‑override warning (currently ~12/command); stale `derive.py:12-13` docstring ("walks repo ancestors"); tests should `delenv("DOTFILES_DEV_INPUTS_ROOT")` for isolation.

### Item 7 — AC1 coverage

Add a test that a repo‑shaped ancestor is **ignored** with the override unset (guards the removed silent walk), and cover `require_input` for all four keys (currently only csg).

## Ratified deviation

`find_*` intentionally stay non‑raising (`None` = absent) for the read‑only check wiring; the **derivation** path raises `MissingDerivationInputError`. This is the split that keeps `reconcile --check-inputs` able to report a missing input rather than crash. (AC1's "missing raises" applies to derivation.)

## Ballot (Approve / Request changes PER ITEM)

- Item 1 (verify recurse + test fixture + siblings)?
- Item 2 (fix dev candidate paths + real-layout test)?
- Item 3 (AC4 loud repo provenance + test)?
- Item 4 (remove/gate itr_adapter repo walk)?
- Item 5 (verify siblings + empty-list guard)?
- Item 6 (resolver hardening)?
- Item 7 (AC1 coverage)?
- Ratify the find_*/require split?
