## 1. Adapter

- [x] 1.1 `adapters/btop_reloader.py` — `IDesktopReloader`: enumerate btop PIDs, send `SIGUSR2`; vacuous `True` when none, `False` on signal failure; injectable pid-source + signaller; no shell, no pty
- [x] 1.2 Docstring cites btop.cpp:1053 (`SIGUSR2` → `reload_conf`) and :1121-1130 (`init_config` + `updateThemes` + `setTheme`), and records why `SIGUSR1` is wrong

## 2. Wiring

- [x] 2.1 `cli/main.py` `_build_reloaders` — append `BtopReloader` LAST, after `KittyReloader`, in both the terminal and daemon paths
- [x] 2.2 Comment the ordering constraint: the seeder must have repointed the consumer pointer before btop re-reads it
- [x] 2.3 Update `btop.conf.j2` prose: SIGUSR2 reload is wired; provisioning itself never signals a running btop

## 3. Tests

- [x] 3.1 `tests/unit/test_btop_reloader.py` — vacuous true; each pid signalled exactly once; **never** `SIGUSR1`/`SIGWINCH`; failed signal → false; partial failure → false; implements the port
- [x] 3.2 `pgrep -x btop` parsing: stdout, no-match, junk/negative tokens, missing `pgrep` → `[]`
- [x] 3.3 `tests/integration/test_btop_reloader_integration.py` — real btop on a pty; swap the file → new colour ABSENT (negative control); `SIGUSR2` → new colour appears AND a second `Loading theme file` line is logged
- [x] 3.4 Drive the adapter in the integration test with an injected pid source returning that exact process, so a vacuous pass is impossible
- [x] 3.5 Assert the default pid source actually finds the spawned btop
- [x] 3.6 Composition-root tests updated: `BtopReloader` last in both paths

## 4. Verification

- [x] 4.1 `uv run --directory src/runtime pytest` green (2111 passed)
- [x] 4.2 `cd src/runtime && uv run pytest tests/architecture/test_layering.py` green (127)
- [x] 4.3 `make contracts-check` green (34)
- [x] 4.4 On-host: with btop open, change the wallpaper, assert the frame adopts the new palette without relaunching btop
