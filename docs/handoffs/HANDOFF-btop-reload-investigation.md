# Investigation: making btop react to palette changes

**Status: FEASIBLE.** Verified empirically against btop 1.4.7 on this host.

This reverses the earlier "deferred, probably not possible" position in the three
btop change specs. btop *does* expose a hot-reload path; I had not read its signal
table before deferring it.

## The mechanism

`src/btop.cpp:1053` registers a handler for `SIGUSR2`:

```cpp
case SIGUSR2:
    Global::reload_conf = true;
    Input::interrupt();
```

and the main loop honours it at `src/btop.cpp:1121-1130`:

```cpp
//? Hot reload config from CTRL + R or SIGUSR2
else if (Global::reload_conf) {
    Global::reload_conf = false;
    if (Runner::active) Runner::stop();
    Config::unlock();
    init_config(cli.low_color, cli.filter);
    Theme::updateThemes();     // re-scan the themes directory
    Theme::setTheme();         // re-read the file from disk + regenerate colors
    Draw::banner_gen(0, 0, false, true);
    Global::resized = true;    // force a full redraw
}
```

Note `Theme::updateThemes()` — the reload **re-scans** `~/.config/btop/themes`, so
it is not merely re-reading a cached path. A theme file added or replaced on disk
is picked up without restarting btop.

`SIGUSR1` is also handled but is a no-op ("Input::poll interrupt", `:314-315`).
`SIGWINCH` only forces a resize redraw. So `SIGUSR2` is the signal to use.

This is the exact mirror of the existing `KittyReloader`, which sends `SIGUSR1` to
kitty so every open window re-reads its config (`auto_reload_config -1` disables
kitty's own file-watching precisely so the runtime drives it).

## Empirical proof

Method: run btop on a real pty with an isolated `XDG_CONFIG_HOME`, complete 48-key
theme with a unique `main_bg`, swap the file's contents between phases, and sample
only `48;2` background sequences (constant per theme; gradient colours are
interpolated 101 ways and are useless as a signal).

```
phase 1  theme bg = #010203   -> frame bg #010203   loaded
phase 2  file swapped to #abcdef, NO signal -> still #010203  (btop does not poll)
phase 3  SIGUSR2 sent         -> frame bg #abcdef   ALSO 2 "Loading theme file" log lines
```

VERDICT: reactive hot-reload via `SIGUSR2` = **True**.

Two `Loading theme file` lines appear (initial load + reload), confirming
`updateThemes()` + `setTheme()` actually ran rather than the change being a
redraw artefact.

## Harness bug worth recording

The first three attempts reported failure and were **my** fault, not btop's:

- I set `XDG_CONFIG_HOME` to `<root>/config/btop` instead of `<root>/config`.
  `get_config_dir()` appends `btop` itself, so btop looked for
  `<root>/config/btop/btop/` and **never read the config at all** — it silently
  ran on `Default_theme`. The tell was that no `Loading theme file` line appeared
  and the frame showed stock-default colours (`#556d59`).
- I asserted on the *whole* colour set, but gradients emit 101 interpolated values
  per family, so the set is dominated by sampling noise and differs between any
  two captures even with no theme change.

Both are recorded because the committed harness
(`spikes/btop-theme-prototype/assert_theme_applies.py`) shares the second weakness
and should be hardened: assert on **background (`48;2`) sequences only**, and
always confirm a `Loading theme file` line exists before trusting a frame.

## Proposed implementation

A `BtopReloader` implementing the existing `IDesktopReloader` port, mirroring
`KittyReloader` (`adapters/kitty_reloader.py`):

- enumerate `btop` PIDs (injected pid-source for testability, as `KittyReloader` does)
- send `SIGUSR2` to each
- **vacuous `True`** when no btop is running
- **`False`** when a btop exists but signalling fails
- append to `_build_reloaders` in `cli/main.py`, respecting the pinned order
  (`HyprlandReloader` → `AgsReloader` → `TerminalColorApplier` → `KittyReloader`)

Because the theme files are symlinks into the content-addressed palette cache, the
reload reads whatever the cache entry currently holds — so by the time the reloader
runs, the pointer is already repointed. No ordering hazard between the seeder and
the reloader, provided the reloader stays last (as `KittyReloader` already is).

## Verification (machine-checkable, no eyes)

- **positive**: with a btop running under a pty, swap the theme file, send
  `SIGUSR2`, assert the new `48;2` background colour appears and a second
  `Loading theme file` line is logged
- **negative control**: swap the file and assert the colour is **absent** without
  the signal — proving the assertion discriminates signal from no-signal
- **vacuous**: no btop running ⇒ reloader returns `True` and sends nothing
- **failure**: btop running but `os.kill` raises ⇒ returns `False`
