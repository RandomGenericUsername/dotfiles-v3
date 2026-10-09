## 1. Baseline the drift

- [x] 1.1 Extract the `gates-ci` target list and the workflow's job keys, and
      reproduce the comparison in design §1:
      ```bash
      make -n gates-ci | grep -oE "\b[a-z][a-z-]+-{0,1}[a-z-]*" | sort -u   # or read GATES directly
      grep -E "^  [a-z-]+:" .github/workflows/gates.yml | tr -d ' :'
      ```
      MEASURED: `make -pn gates-ci 2>/dev/null | awk '/^gates-ci:/{print}'` gives
      11 targets; the workflow has 10 job keys. The `grep` above also catches
      `push` (the 2-space key under `on:`), so job keys were extracted with an
      `awk` walk of the `jobs:` block instead.
- [x] 1.2 Confirm `bluetooth-mock-parity` is the ONLY gate with no job, and that
      `contracts`/`capture-hexagonal` are the only renames. If the set differs
      from design §1, record the measurement and adjust the mapping table.
      MEASURED 2026-10-07: matches the table exactly — `bluetooth-mock-parity` is
      the only missing gate; `contracts-check → contracts` and
      `capture-hexagonal-gate → capture-hexagonal` are the only renames. **But
      design §1's `gates-ci` listing omitted `bluetooth-mock-parity` entirely**
      (10 names listed where the Makefile has 11, including the gate the section
      is about), making its own prose self-contradictory — corrected in place;
      see the MEASURED annotation there.
- [x] 1.3 Confirm the two typechecks are genuinely excluded for the stated
      reason (they need `ags` + Astal + GTK4), so the exclusion is not silently
      re-opened. MEASURED: both `capture-typecheck` and `bar-typecheck` depend on
      `capture-types`, whose recipe calls `ags types` (Makefile lines ~102/326);
      on this provisioned desktop `ags` is at `/usr/bin/ags`, which is exactly
      the desktop-stack dependency a stock runner lacks. `make gates` passed both
      here; neither is added to CI.

## 2. The missing job

- [x] 2.1 Add a `bluetooth-mock-parity` job running
      `python3 scripts/bluetooth-mock-parity.py`, modelled on the existing
      `battery-mock-parity` job (same stdlib-only shape, same `runs-on`).
- [x] 2.2 Confirm the gate passes on a stock-runner-shaped invocation — no AGS,
      no GTK, no Astal. The simplest proof is that the script imports nothing
      beyond the stdlib; say so explicitly rather than assuming it.
      MEASURED: `scripts/bluetooth-mock-parity.py` imports only `argparse`,
      `re`, `sys`, `pathlib` (stdlib) and reads mock HTML, `style.css` and the
      mapped TSX as text. `python3 scripts/bluetooth-mock-parity.py` exits 0.
- [x] 2.3 Note in the job comment that the gate is one of the two that fail
      non-zero on `KNOWN_GAPS` count changes, so the next reader is not surprised
      by the two tracked warnings.
      **CORRECTED BY MEASUREMENT.** This claim is false: no mock-parity harness
      fails on `KNOWN_GAPS`. `scripts/bluetooth-mock-parity.py` exits 0 while
      printing `2 known-gap warning(s)`; it exits non-zero only on an UNCOVERED
      token (verified by reading `main()` at lines 487–505 and by running it:
      exit 0). The job comment therefore states the measured behaviour — green
      with tracked warnings — rather than the claimed fail-on-count mechanism.
      Adding a count assertion would change gate semantics and is out of scope.

## 3. The parity check

- [x] 3.1 Write `scripts/ci-gates-parity.py` (stdlib + PyYAML via the
      provisioning env, like `icons-json-drift.py`):
      - parse the `Makefile`'s `GATES` variable and the `gates-ci` filter to
        derive the authoritative set;
      - parse `.github/workflows/gates.yml` for job keys;
      - resolve differences through a declared `RENAMES` mapping and a declared
        `CI_ONLY_EXEMPT` table, each entry carrying a reason;
      - fail non-zero naming anything unmatched **in either direction**.
      This also declares `CI_EXCLUDED_GATES` (the filtered typechecks, with
      reasons), which task 4.2 turns on.
- [x] 3.2 The mapping table must be the ONLY way a rename passes. Prove it: rename
      a job in the workflow without touching the table and confirm the check
      fails naming it. Restore.
      PROVEN: `contracts` → `contracts-renamed` (RENAMES untouched) fails naming
      both `contracts-check` (expected old key `contracts`) and the new key.
- [x] 3.3 Prove both failure directions:
      - remove the `bluetooth-mock-parity` job → fails naming it (this is the
        real baseline; it is red before task 2.1);
      - add a job with no gate → fails naming it.
      PROVEN: (a) removing the job fails naming `bluetooth-mock-parity`;
      (c) adding `probe-only` fails naming `probe-only`.
- [x] 3.4 Add a `ci-gates-parity` target and put it in `GATES` so it lands in
      `gates-ci` too — a check that proves the gate list is complete belongs in
      the list it proves. It runs through
      `uv run --directory src/provisioning` for PyYAML, and has a matching
      `ci-gates-parity` job in the workflow (else the check fails on itself).

## 4. Correct the header

- [x] 4.1 Rewrite the workflow header's claim from "this workflow is the place a
      future change cannot quietly drop one" to what is now true: the parity
      check enforces it, and here is where it lives. **Do not leave a claim in
      prose that the code does not back** — that is the defect being fixed.
- [x] 4.2 State the exclusion of `capture-typecheck`/`bar-typecheck` as a
      declared, checked exemption rather than an absence. The header already
      explains WHY they cannot run; this change makes the exclusion mechanical.

## 5. Verification

- [x] 5.1 `make gates` exit 0, including the new `ci-gates-parity`.
      OBSERVED: MAKE_GATES_EXIT=0.
- [x] 5.2 `make gates-ci` exit 0. OBSERVED: MAKE_GATES_CI_EXIT=0.
- [x] 5.3 The workflow YAML parses and the job list matches `gates-ci` exactly
      (modulo the declared mapping). OBSERVED: `yaml.safe_load` yields the 12 job
      keys; `make ci-gates-parity` passes.
- [x] 5.4 If a YAML linter or `act` is available, syntax-check the workflow; if
      not, say so rather than claiming it was validated. `act` is NOT available
      (`command -v act` empty). The workflow IS syntax-checked by PyYAML, which
      `ci-gates-parity.py` imports and runs on every `gates`/`gates-ci` run.
