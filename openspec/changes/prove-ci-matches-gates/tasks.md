## 1. Baseline the drift

- [ ] 1.1 Extract the `gates-ci` target list and the workflow's job keys, and
      reproduce the comparison in design §1:
      ```bash
      make -n gates-ci | grep -oE "\b[a-z][a-z-]+-{0,1}[a-z-]*" | sort -u   # or read GATES directly
      grep -E "^  [a-z-]+:" .github/workflows/gates.yml | tr -d ' :'
      ```
- [ ] 1.2 Confirm `bluetooth-mock-parity` is the ONLY gate with no job, and that
      `contracts`/`capture-hexagonal` are the only renames. If the set differs
      from design §1, record the measurement and adjust the mapping table.
- [ ] 1.3 Confirm the two typechecks are genuinely excluded for the stated
      reason (they need `ags` + Astal + GTK4), so the exclusion is not silently
      re-opened.

## 2. The missing job

- [ ] 2.1 Add a `bluetooth-mock-parity` job running
      `python3 scripts/bluetooth-mock-parity.py`, modelled on the existing
      `battery-mock-parity` job (same stdlib-only shape, same `runs-on`).
- [ ] 2.2 Confirm the gate passes on a stock-runner-shaped invocation — no AGS,
      no GTK, no Astal. The simplest proof is that the script imports nothing
      beyond the stdlib; say so explicitly rather than assuming it.
- [ ] 2.3 Note in the job comment that the gate is one of the two that fail
      non-zero on `KNOWN_GAPS` count changes, so the next reader is not surprised
      by the two tracked warnings.

## 3. The parity check

- [ ] 3.1 Write `scripts/ci-gates-parity.py` (stdlib + PyYAML via the
      provisioning env, like `icons-json-drift.py`):
      - parse the `Makefile`'s `GATES` variable and the `gates-ci` filter to
        derive the authoritative set;
      - parse `.github/workflows/gates.yml` for job keys;
      - resolve differences through a declared `RENAMES` mapping and a declared
        `CI_ONLY_EXEMPT` table, each entry carrying a reason;
      - fail non-zero naming anything unmatched **in either direction**.
- [ ] 3.2 The mapping table must be the ONLY way a rename passes. Prove it: rename
      a job in the workflow without touching the table and confirm the check
      fails naming it. Restore.
- [ ] 3.3 Prove both failure directions:
      - remove the `bluetooth-mock-parity` job → fails naming it (this is the
        real baseline; it is red before task 2.1);
      - add a job with no gate → fails naming it.
- [ ] 3.4 Add a `ci-gates-parity` target and put it in `GATES` so it lands in
      `gates-ci` too — a check that proves the gate list is complete belongs in
      the list it proves.

## 4. Correct the header

- [ ] 4.1 Rewrite the workflow header's claim from "this workflow is the place a
      future change cannot quietly drop one" to what is now true: the parity
      check enforces it, and here is where it lives. **Do not leave a claim in
      prose that the code does not back** — that is the defect being fixed.
- [ ] 4.2 State the exclusion of `capture-typecheck`/`bar-typecheck` as a
      declared, checked exemption rather than an absence. The header already
      explains WHY they cannot run; this change makes the exclusion mechanical.

## 5. Verification

- [ ] 5.1 `make gates` exit 0, including the new `ci-gates-parity`.
- [ ] 5.2 `make gates-ci` exit 0.
- [ ] 5.3 The workflow YAML parses and the job list matches `gates-ci` exactly
      (modulo the declared mapping).
- [ ] 5.4 If a YAML linter or `act` is available, syntax-check the workflow; if
      not, say so rather than claiming it was validated.
