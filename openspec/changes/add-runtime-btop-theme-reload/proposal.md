## Why

The theme file updates automatically on a wallpaper change — the runtime
re-derives the palette, writes a new `colors.btop.theme` into a new cache entry,
and repoints `current/` plus the spine consumer pointer. But a **running btop
does not re-read it**: btop resolves its theme once at startup, so an open
instance kept showing the previous wallpaper's palette until relaunched.

Every other palette consumer re-themes live (Hyprland via `hyprctl reload`, kitty
via `SIGUSR1`, GTK4 apps via `Gtk4AppReloader`). btop was the odd one out, and the
reason was not that it lacked a mechanism — we had simply never read its signal
table.

## What Changes

- New `BtopReloader` (`adapters/btop_reloader.py`): implements the existing
  `IDesktopReloader` port, enumerates running btop processes, sends each
  `SIGUSR2`. Vacuous `True` when no btop is running; `False` when a btop exists
  but signalling fails. Injected pid-source + signaller, exactly like
  `KittyReloader`.
- Appended **last** in `_build_reloaders` (`cli/main.py`), after `KittyReloader`.
  The consumer pointer must already have been repointed by the seeder before a
  reload reads it, so ordering is load-bearing.

## Why SIGUSR2, and not SIGUSR1

btop registers `SIGUSR1` as a bare "Input::poll interrupt" **no-op**
(`btop.cpp:314-315`) and `SIGWINCH` as resize-only. Only `SIGUSR2` sets
`reload_conf`, which the main loop turns into `init_config` + `Theme::updateThemes()`
+ `Theme::setTheme()` + a forced redraw (`btop.cpp:1053`, `:1121-1130`).

`Theme::updateThemes()` **re-scans** the themes directory rather than re-reading a
cached path, which is why a theme file *replaced* on disk is picked up without a
restart. Verified against btop 1.4.7: swapped the file with no signal and the
rendered background stayed on the old value; after `SIGUSR2` the new value appeared
and a **second** `Loading theme file` line was logged — proving the reload path ran
rather than a redraw artefact.

## Non-goals

- Not a btop-as-source backend (separate change).
- No change to the theme content or the single-format decision.
- No restart, kill, or relaunch of btop: the process keeps running and keeps its
  state. `SIGUSR2` re-reads btop's whole config, not just the theme, so menu-driven
  config changes are re-applied too — that is btop's own semantics for the signal.

## Verification

- unit: vacuous true; each pid gets exactly one `SIGUSR2`; **never** `SIGUSR1` or
  `SIGWINCH`; failed signal → false; partial failure → false; `pgrep -x btop`
  parsing incl. junk/negative tokens and a missing `pgrep` degrading to `[]`.
- integration against a **real btop on a pty**: swap the theme file, assert the new
  background colour is **absent** (negative control — btop has no watcher), then
  `SIGUSR2` and assert it appears plus a second `Loading theme file` line. The
  reloader is driven with an injected pid source returning that exact process, so a
  vacuous pass is impossible.
- composition root: `BtopReloader` is last in both the terminal and daemon paths.