## Context

`scripts/dev/vmtest/` holds the Incus dev harness (`vm` dispatcher + `vm-fresh.sh`, `vm-continue.sh`, `run-vm.sh`, `provision-in-vm.sh`, `install.sh`). `Makefile:vm-*` delegates to `scripts/dev/vmtest/vm` and `REPO_ROOT` is derived via `../../..`. The broken `refactor/reorganize-scripts-and-gui-tools` branch moved this correctly but bundled it with the capture-tool extraction that broke `ags toggle capture-window`, so the safe move was never shippable alone.

## Goals / Non-Goals

**Goals:**
- `dev/` as the single home for host-only dev tooling with `./dev/vm` entry.
- Identical VM behavior: same Incus names, flags, image cache semantics, SSH flow.
- Mechanical, reviewable diff: `git mv` + path-constant edits only.

**Non-Goals:**
- No QEMU/Incus flag changes, no provisioning changes, no `capture-tool` / `gloview-activate` moves (separate changes).
- No `scripts/` deletion yet (that happens only after all three relocates land).

## Decisions

- **Copy-then-fix, not rewrite:** `git mv scripts/dev/vmtest/* dev/` then edit only `REPO_ROOT` derivations (`run-vm.sh`, `vm-fresh.sh`: `../../..` -> `..`) and `Makefile` + `.gitignore`. Alternative (symlink shim at old path) rejected: leaves dual truth and confuses `verify`.
- **Keep `.images/` semantics:** cache dir moves with the harness to `dev/.images/`; `.gitignore` updated in the same commit so a stale `scripts/dev/vmtest/.images/` is never committed.
- **No compat shim:** old path is removed outright. Rationale: harness is dev-only, not provisioned to target machines; grep shows only `Makefile` references it.

## Risks / Trade-offs

- **[Risk] Stale docs/runbooks reference old path** → Mitigation: grep for `scripts/dev/vmtest` post-move; update `dev/README.md` header to `./dev/vm`.
- **[Risk] `REPO_ROOT` off-by-one breaks 9p share / tar push** → Mitigation: assert `dev/run-vm.sh` resolves to repo root containing `bootstrap.sh`; `bash -n` all scripts; `make vm-help` smoke.
