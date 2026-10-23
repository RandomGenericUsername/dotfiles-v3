## 1. Relocate harness

- [x] 1.1 `git mv scripts/dev/vmtest dev-tmp && mkdir -p dev && git mv dev-tmp/* dev/ && rmdir dev-tmp` (preserve history; keep executable bits)
- [x] 1.2 Update `REPO_ROOT` in `dev/run-vm.sh` and `dev/vm-fresh.sh` to single-level traversal and assert `$REPO_ROOT/bootstrap.sh` exists
- [x] 1.3 Update `dev/README.md` header/usage from `scripts/dev/vmtest/vm` to `./dev/vm`

## 2. Retarget callers

- [x] 2.1 Update all `Makefile` `vm-*` targets to `./dev/vm <verb>`
- [x] 2.2 Update `.gitignore` `/scripts/dev/vmtest/.images/` -> `/dev/.images/`
- [x] 2.3 Grep repo for remaining `scripts/dev/vmtest` references (docs, scripts, tests) and update or file follow-ups

## 3. Verify

- [x] 3.1 `bash -n dev/vm dev/vm-fresh.sh dev/vm-continue.sh dev/run-vm.sh dev/provision-in-vm.sh dev/install.sh`
- [x] 3.2 `make vm-help` and `make -n vm-status` show `./dev/vm` delegation
- [x] 3.3 `openspec validate relocate-dev-vm-harness` passes
