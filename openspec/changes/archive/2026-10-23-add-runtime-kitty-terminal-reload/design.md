## Context

The runtime palette chain: `csg_adapter` requests formats and hashes their
outputs; `derive.PALETTE_ARTIFACT_NAMES` is the completeness oracle;
`ensure_palette_entry_complete` evicts any cache entry missing an artifact name;
`reconcile` repoints the `current/` symlinks for every expected artifact;
`_build_reloaders` runs the desktop consumers after a swap.

Today: formats requested are `conf`, `gtk.css`, `adw.css`, `sequences`, `rasi`
(hardcoded `--format` flags); `PALETTE_ARTIFACT_NAMES` has six names; reloaders
are Hyprland, AGS, Hyprpaper, TerminalColorApplier. `TerminalColorApplier` writes
OSC to `/dev/tty`; from the daemon there is no tty, so every converge logs a
failure.

kitty: reloads its config on **SIGUSR1** (`kill -SIGUSR1 $KITTY_PID`), and
config supports `include`. Multiple kitty OS-windows are separate processes; a
reload applies the included colours to the window(s) of the signalled process.

## Goals / Non-Goals

**Goals**
- `colors.kitty` is produced, cached, and exposed at `current/colors.kitty`
  exactly like the other palette artifacts.
- A `KittyReloader` reloads kitty after a swap so all open windows re-theme —
  event-driven, no shell polling, no pty writes.
- The daemon stops logging a bogus `/dev/tty` failure on every converge.

**Non-Goals**
- CSG template (sibling change) and `kitty.conf` (provisioning change).
- OSC broadcast to `/dev/pts/*` (rejected).
- Timing guarantees finer than "after the reloader list runs".

## Decisions

### D1. `colors.kitty` is the seventh palette artifact
Added to `PALETTE_ARTIFACT_NAMES`, the `csg_adapter` requested formats and hashed
outputs, the cache-entry `artifact_hashes`, and the reconcile expected-artifact /
`current/` symlink set. Naming matches the format value (`kitty`).

### D2. Migration is automatic self-heal, no manual step
Adding a name makes every existing palette entry **incomplete**; the existing
`ensure_palette_entry_complete` (gt-2-1) already evicts incomplete entries and
re-derives them on the next need. No migration code.

### D3. `KittyReloader` signals kitty by `SIGUSR1`
Enumerate running kitty PIDs (`pgrep -x kitty`), send `SIGUSR1` to each (kitty
reloads its config, which includes the runtime palette). This is the same
subprocess-based pattern as `HyprlandReloader`/`AgsReloader`. kitty does not need
its config rewritten; the include already points at `current/colors.kitty`.

### D4. Absent kitty is vacuous success; a failed signal is surfaced
A terminal may legitimately not be open, so **no kitty process ⇒ `True`**. If a
kitty process exists and signalling it fails (permission/OSError), return `False`
(surfaced via `ReconcileResult.reload_failures`, R5) — the only genuinely
broken case.

### D5. `TerminalColorApplier` becomes interactive-only
It themes the *controlling* terminal via `/dev/tty`; the daemon has none, so
including it there is a guaranteed failure. `_build_reloaders` gains
`include_terminal: bool = True`; the CLI passes the default, the daemon passes
`False`. `KittyReloader` is included in both. R5's `/dev/tty` surfaced-failure
semantics are preserved for CLI runs.

### D6. Reloader order
`_build_reloaders` order becomes Hyprland, AGS, Hyprpaper, TerminalColorApplier
(when included), **KittyReloader** appended last — consumers are independent, and
appending avoids disturbing the pinned existing order.
