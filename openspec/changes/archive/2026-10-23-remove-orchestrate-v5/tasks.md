## 1. Remove legacy helper

- [x] 1.1 Confirm zero live references: grep for `orchestrate-v5` across `Makefile`, `bootstrap.sh`, `src/`, `dotfiles/`, `dev/` (historical docs under `docs/` and `_bmad-output/` are exempt)
- [x] 1.2 `git rm scripts/orchestrate-v5.sh`

## 2. Verify

- [x] 2.1 `openspec validate remove-orchestrate-v5` passes
- [x] 2.2 Unit suite passes (`test_bootstrap_script.py` at minimum)
