## 1. Palette artifact set grows to include `colors.kitty`

- [ ] 1.1 `adapters/csg_adapter.py` — add `--format kitty` to the requested formats and include `colors.kitty` in the hashed outputs
- [ ] 1.2 `application/derive.py` — add `"colors.kitty"` to `PALETTE_ARTIFACT_NAMES` and to the `artifact_hashes` written on population
- [ ] 1.3 `application/reconcile.py` — add `"colors.kitty"` to the expected palette artifacts (the `current/` symlink set)
- [ ] 1.4 Confirm `ensure_palette_entry_complete` self-heals old entries (add/extend a test asserting a six-artifact entry is evicted)

## 2. `KittyReloader`

- [ ] 2.1 `adapters/kitty_reloader.py` — `IDesktopReloader`: enumerate kitty PIDs, send `SIGUSR1`; vacuous `True` when none; `False` on a failed signal; injectable pid-source + signaller for tests
- [ ] 2.2 Unit tests: no kitty ⇒ `True`; multiple kitty ⇒ one signal each; signal OSError ⇒ `False`; no shell/pty use
- [ ] 2.3 Integration/E2E (private bus or direct): a swap with a fake kitty process receives `SIGUSR1`

## 3. Reloader wiring

- [ ] 3.1 `cli/main.py` `_build_reloaders(state_root, *, include_terminal: bool = True)` — append `KittyReloader`; include `TerminalColorApplier` only when `include_terminal`
- [ ] 3.2 Daemon path passes `include_terminal=False`; CLI commands keep the default
- [ ] 3.3 Tests: daemon reloaders exclude `TerminalColorApplier` and include `KittyReloader`; CLI reloaders include both; daemon converge no longer logs a `/dev/tty` failure

## 4. Verification

- [ ] 4.1 `uv run --directory src/runtime pytest` green; layering green; `make contracts-check` green
- [ ] 4.2 On-host: change the wallpaper; assert `current/colors.kitty` exists and running kitty processes received `SIGUSR1` (all windows re-theme)
