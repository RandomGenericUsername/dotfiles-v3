#!/usr/bin/env python3
"""ci-gates-parity -- the workflow's job set must equal `make gates-ci`.

WHY THIS GATE EXISTS. `.github/workflows/gates.yml` used to open by claiming it
was "the place a future change cannot quietly drop one" of the gates. No code
implemented that claim, and the claim was measurably false: `bluetooth-mock-parity`
sat in the `Makefile`'s `GATES` -- and therefore in `gates-ci`, the set the same
header names as authoritative -- with no workflow job, so the gate had run on
every developer's machine and never once on a push. A hand-maintained list that
is never compared to its source of truth drifts the first time one side is
edited. This check is the comparison the comment asserted must be true.

WHAT IT COMPARES. One direction is not enough, because each direction fails
differently:

  * a `gates-ci` target with no job -- the `bluetooth-mock-parity` case: the gate
    runs locally and never in CI;
  * a workflow job with no `gates-ci` target -- a CI-only check that is invisible
    to developers and drifts from the Makefile.

It derives the authoritative set from the `Makefile` itself, never from a copy:
`GATES` is parsed and the `gates-ci` rule's `filter-out` is applied to it, so the
Makefile remains the one place the set is written.

DECLARED DIFFERENCES, NOT ASSUMED ONES. Two kinds of difference are legal, and
both must be written down here rather than read past:

  * `RENAMES` -- a job key that differs from its `make` target. A rename is a
    claim, so it is an entry with a reason, the way `bluetooth-mock-parity.py`'s
    `CLASS_MAP` declares a token's shipped equivalent. An undeclared rename fails
    naming both the old and the new name.
  * `CI_ONLY_EXEMPT` -- a workflow job that is deliberately not a gate (a setup
    or lint job with no `make` target), also with a reason.

And one exclusion is declared rather than left as an absence: `CI_EXCLUDED_GATES`
names each gate the `gates-ci` filter removes and why it cannot run on a stock
runner. `capture-typecheck` and `bar-typecheck` are the two today.

Usage: ``python3 scripts/ci-gates-parity.py [--root REPO_ROOT]``
Exit 0 = the two sets are equal modulo the declared tables.
Exit 1 = an unmatched entry in either direction, or a declared entry that no
         longer matches the tree (a stale rename/exemption), or a missing/unreadable
         input.

PyYAML is imported and if it is unavailable this gate FAILS rather than skipping:
the workflow is parsed as YAML, not line-mangled. Run it through the provisioning
project so PyYAML is importable, exactly as `icons-json-drift` does:

    uv run --directory src/provisioning python ../../scripts/ci-gates-parity.py

The `../../` is load-bearing: `--directory` moves the interpreter's CWD to
src/provisioning, so a `scripts/...` path does not resolve from there. The script
locates the repo from its own `__file__`, so its own CWD does not matter -- only
the path you type to reach it does.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

MAKEFILE = "Makefile"
WORKFLOW = ".github/workflows/gates.yml"

# A rename: a job key that differs from its `make` target, with the reason the
# two names differ. The key is the `make` target (the authoritative name); the
# value is (workflow job key, why the names are not identical).
#
# These are the ONLY way a renamed job passes. A renamed job with no entry here
# is a failure, not an inferred correspondence: the two lists are compared by
# name, and a rename is a claim someone must review, exactly as
# `bluetooth-mock-parity.py`'s CLASS_MAP treats a token's shipped equivalent.
RENAMES: dict[str, tuple[str, str]] = {
    "contracts-check": (
        "contracts",
        "The job's `name:` already reads `contracts-check`; only the key is "
        "shortened. The job runs `make contracts-check` and the two names refer "
        "to the same target, so the correspondence is recorded rather than "
        "renaming a job for cosmetics.",
    ),
    "capture-hexagonal-gate": (
        "capture-hexagonal",
        "The job key drops the `-gate` suffix the `make` target carries; the job "
        "runs `python3 scripts/capture-hexagonal-gate.py`, the same script.",
    ),
}

# Workflow jobs that are deliberately not gates: a job with no `make` target,
# with the reason it exists in CI only. None exist today -- this table is here so
# that adding one is a reviewed decision rather than an accident, and so a job
# that is neither a gate nor declared here fails the check.
CI_ONLY_EXEMPT: dict[str, str] = {}

# Gates in `GATES` that the `gates-ci` filter removes (i.e. they do NOT run in
# CI), each with the reason it cannot. These are a declaration, not an absence:
# removing a gate from `gates-ci` without an entry here fails, and an entry here
# for a gate that is not actually filtered out fails as stale.
CI_EXCLUDED_GATES: dict[str, str] = {
    "capture-typecheck": (
        "Needs `ags` on PATH plus the Astal/GIR libraries, and `ags types` writes "
        "~49 MB of machine-specific .d.ts describing this host's GTK/Astal "
        "install; its tolerated-third-party bucket is keyed to the literal "
        "/usr/share/ags/js/ path. A stock runner has no AGS, no Astal and no "
        "GTK4, so the target has nothing to typecheck against."
    ),
    "bar-typecheck": (
        "Same desktop-stack dependency as capture-typecheck (it reuses the "
        "capture tool's generated /usr/share/ags/js declarations), so it too "
        "cannot run on a stock runner. `make gates` still runs both for a "
        "developer on a provisioned desktop."
    ),
}


class Drift(Exception):
    """Raised with the full list of unmatched/stale entries."""


def strip_comment(line: str) -> str:
    """Drop a `#` comment from a Makefile line (no token contains `#`)."""
    return line.split("#", 1)[0]


def parse_makefile_gates(text: str) -> tuple[list[str], list[str], list[str]]:
    """Return (GATES, gates-ci, excluded), deriving gates-ci from GATES + filter.

    `excluded` is the difference between the two, whatever form the filter takes,
    so CI_EXCLUDED_GATES is verified against the Makefile rather than a guess.
    """
    joined = re.sub(r"\\\n", " ", text)

    gates: list[str] | None = None
    excluded_from_filter: list[str] | None = None

    for raw in joined.splitlines():
        line = strip_comment(raw)
        if gates is None:
            m = re.match(r"^\s*GATES\s*[:+?]?=\s*(.*)$", line)
            if m:
                gates = m.group(1).split()
        m = re.match(r"^\s*gates-ci\s*:\s*(.*)$", line)
        if m:
            rhs = m.group(1)
            fm = re.search(r"filter-out\s+(.+?)\s*,", rhs)
            if fm:
                excluded_from_filter = fm.group(1).split()

    if not gates:
        raise Drift(
            f"could not parse the `GATES` variable from the {MAKEFILE}; refusing "
            f"to guess the authoritative set"
        )
    if excluded_from_filter is None:
        raise Drift(
            f"could not parse a `filter-out` from the `gates-ci` rule in "
            f"{MAKEFILE}; refusing to guess which gates are CI-capable"
        )

    gates_ci = [g for g in gates if g not in excluded_from_filter]
    excluded = [g for g in gates if g not in gates_ci]
    return gates, gates_ci, excluded


def parse_workflow_jobs(text: str) -> list[str]:
    """Return the workflow's job keys (the 2-space keys under `jobs:`), in order."""
    try:
        import yaml  # PyYAML ships with the provisioning project
    except ImportError as exc:  # pragma: no cover - environment guard
        raise Drift(
            f"PyYAML is not importable ({exc}); this gate parses the workflow as "
            f"YAML rather than by line-mangling and must not guess. Run it as: "
            f"uv run --directory src/provisioning python ../../scripts/ci-gates-parity.py"
        ) from exc

    data = yaml.safe_load(text)
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), dict):
        raise Drift(f"no `jobs:` mapping found in {WORKFLOW}")
    return list(data["jobs"].keys())


def check(gates: list[str], gates_ci: list[str], excluded: list[str], jobs: list[str]) -> list[str]:
    """Return a list of human-readable violations (empty == aligned)."""
    errors: list[str] = []
    job_set = set(jobs)

    # 1. Every gate filtered out of gates-ci must be declared, and every declared
    #    exclusion must actually be filtered out. No implicit exclusions.
    excluded_set = set(excluded)
    for gate in excluded:
        if gate not in CI_EXCLUDED_GATES:
            errors.append(
                f"gate {gate!r} is filtered out of gates-ci by the {MAKEFILE} but "
                f"has no CI_EXCLUDED_GATES entry -- declare why it does not run in CI"
            )
    for gate in CI_EXCLUDED_GATES:
        if gate not in excluded_set:
            errors.append(
                f"CI_EXCLUDED_GATES declares {gate!r} but that gate is not actually "
                f"filtered out of gates-ci (stale exemption)"
            )

    # 2. Map each gates-ci target to its workflow job key via the declared renames.
    mapped: dict[str, str] = {}
    for gate in gates_ci:
        if gate in RENAMES:
            job, _reason = RENAMES[gate]
        else:
            job = gate
        mapped[gate] = job

        if job not in job_set:
            where = "declared rename" if gate in RENAMES else "no declared rename"
            errors.append(
                f"gates-ci target {gate!r} has no CI job: expected job key "
                f"{job!r} ({where}) but the workflow has no such job"
            )

    # 3. Every workflow job must map back to a gates-ci target, or be declared as
    #    a deliberate CI-only job.
    matched_jobs = set(mapped.values())
    for job in jobs:
        if job in matched_jobs:
            continue
        if job in CI_ONLY_EXEMPT:
            continue
        errors.append(
            f"CI job {job!r} maps to no gates-ci target and is not in "
            f"CI_ONLY_EXEMPT -- it runs something the developer gate set does not"
        )

    # 4. Declared entries must not be stale in the other direction either, and a
    #    rename's target must itself exist (so an undeclared rename names both the
    #    old and the new name instead of looking like a deletion plus an addition).
    for gate in RENAMES:
        if gate not in gates_ci:
            errors.append(
                f"RENAMES declares {gate!r} but that is not a gates-ci target "
                f"(stale rename)"
            )
    for job in CI_ONLY_EXEMPT:
        if job not in job_set:
            errors.append(
                f"CI_ONLY_EXEMPT declares {job!r} but no such workflow job exists "
                f"(stale exemption)"
            )

    # 5. Two gates must not collapse onto the same job, which would let one job
    #    satisfy two gates that a reader believes are separate.
    seen: dict[str, str] = {}
    for gate, job in mapped.items():
        if job in seen:
            errors.append(
                f"gates-ci targets {seen[job]!r} and {gate!r} both map to job "
                f"{job!r}; the mapping is ambiguous"
            )
        seen[job] = gate

    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description="workflow jobs == make gates-ci")
    ap.add_argument("--root", default=None, help="repo root (default: parent of scripts/)")
    args = ap.parse_args()

    root = Path(args.root) if args.root else Path(__file__).resolve().parent.parent
    makefile_path = root / MAKEFILE
    workflow_path = root / WORKFLOW

    for path, label in ((makefile_path, MAKEFILE), (workflow_path, WORKFLOW)):
        if not path.is_file():
            print(f"MISSING {label}: {path}")
            return 1

    try:
        gates, gates_ci, excluded = parse_makefile_gates(makefile_path.read_text())
        jobs = parse_workflow_jobs(workflow_path.read_text())
    except Drift as exc:
        print(f"FAIL: {exc}")
        return 1

    errors = check(gates, gates_ci, excluded, jobs)

    print(
        f"ci-gates-parity: authoritative gates-ci set ({len(gates_ci)}): "
        + " ".join(gates_ci)
    )
    print(f"ci-gates-parity: workflow jobs ({len(jobs)}): " + " ".join(jobs))
    print(
        f"ci-gates-parity: declared gates-ci exclusions ({len(CI_EXCLUDED_GATES)}): "
        + (" ".join(CI_EXCLUDED_GATES) or "(none)")
    )
    print(
        f"ci-gates-parity: declared CI-only jobs ({len(CI_ONLY_EXEMPT)}): "
        + (" ".join(CI_ONLY_EXEMPT) or "(none)")
    )
    print(
        f"ci-gates-parity: declared renames ({len(RENAMES)}): "
        + (", ".join(f"{g}->{j}" for g, (j, _) in RENAMES.items()) or "(none)")
    )

    if errors:
        print(
            f"ci-gates-parity: FAIL -- {len(errors)} unmatched/stale "
            f"entr{'y' if len(errors) == 1 else 'ies'}:"
        )
        for err in errors:
            print(f"  - {err}")
        print(
            "  Fix the workflow, the Makefile, or the declared table in this "
            "script -- in whichever is actually wrong -- rather than silencing "
            "this check."
        )
        return 1

    print(
        "ci-gates-parity: PASS -- every gates-ci target has a CI job and every CI "
        "job is a gates-ci target (modulo the declared tables)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
