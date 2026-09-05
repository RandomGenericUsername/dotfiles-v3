## 1. Relocate helper

- [x] 1.1 Rebase onto (or commit first) the uncommitted `gloview-plugin` role work to avoid collision
- [x] 1.2 `git mv scripts/gloview-activate dotfiles/provisioning/scripts/gloview-activate` (keep executable bit)
- [x] 1.3 Update `cli_tools` role `src:` to `dotfiles/provisioning/scripts/gloview-activate`; `dest`/mode unchanged

## 2. Verify

- [x] 2.1 Grep repo for remaining `scripts/gloview-activate` references and update
- [x] 2.2 Dry-run `cli_tools` role + unit tests touching it
- [x] 2.3 `openspec validate relocate-gloview-activate` passes
