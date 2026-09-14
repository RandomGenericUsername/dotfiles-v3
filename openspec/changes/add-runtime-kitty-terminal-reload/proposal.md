## Why

Once CSG can emit a `colors.kitty` artifact (`add-csg-kitty-color-format`), the
runtime must actually request it, carry it through the palette cache and the
`current/` pointer, and make **all open kitty windows** adopt it — not just new
shells. Today the runtime requests `conf/gtk.css/adw.css/sequences/rasi`, and the
only terminal recolouring is `TerminalColorApplier`, which writes OSC to
`/dev/tty` and therefore reaches only the process's own terminal; from the daemon
there is no tty at all, so it fails every converge (the warning seen in the
journal). Open kitty windows never re-theme.

This change adds `colors.kitty` to the palette artifact set and a `KittyReloader`
that reloads kitty's config (SIGUSR1) so every kitty window follows the palette,
event-driven and without shell polling.

## What Changes

- `csg_adapter` requests `--format kitty` and hashes `colors.kitty`.
- `colors.kitty` joins the palette artifact set (`PALETTE_ARTIFACT_NAMES`), the
  reconcile expected-artifacts / `current/` symlink set, and the cache-entry
  `artifact_hashes`. Existing palette entries become incomplete and self-heal
  (evicted + re-derived) via `ensure_palette_entry_complete`.
- New `KittyReloader` (`IDesktopReloader`): sends `SIGUSR1` to running kitty
  processes so kitty reloads its config (which includes the runtime palette).
  Vacuous success when no kitty process is running; surfaced failure when a kitty
  process exists but signalling fails. Wired into `_build_reloaders`.
- Stop the daemon's `TerminalColorApplier` `/dev/tty` failure noise: skip it when
  there is no controlling terminal (downgrade to debug/info), keeping the OSC
  behaviour for terminals that invoke the runtime directly.

## Non-goals

- No CSG change (the format is the sibling change).
- No `kitty.conf` provisioning (that is `provision-kitty-color-config`).
- No attempt to write OSC into arbitrary `/dev/pts` entries (rejected: racy,
  invasive).
- No change to the ICC/profile or font handling.
