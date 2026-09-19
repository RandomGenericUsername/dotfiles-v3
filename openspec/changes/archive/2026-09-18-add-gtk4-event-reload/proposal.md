## Why

`wallpaper set` / `reconcile` currently reload desktop consumers through
`_build_reloaders` (`src/runtime/src/runtime/cli/main.py:380-411`), which
includes `Gtk4AppReloader()` — an inline, synchronous, `/proc`-scan-and-kill
adapter (`src/runtime/src/runtime/adapters/gtk4_app_reloader.py`). It is the
odd one out: every other consumer of a palette swap already reacts to the hub's
domain-event surface (`org.dotfiles.Events1`, topic `wallpaper.state`).

The established pattern is proven in-tree:

- **ICME** is a thin consumer and does live palette refresh with **no restart**
  — it calls `app.apply_css(...)` on `wallpaper.state done`
  (`src/gui-tools/icon-color-mapping-editor/ui/EditorWindow.tsx:165-183`).
- **wallpaper-selector** subscribes to the same topic for progress/LIVE
  refresh (`src/gui-tools/wallpaper-selector/lib/event-bus.ts`).
- **AGS reloader** explicitly documents the distinction: apps that can refresh
  in-process are skipped and refresh "live from the `wallpaper.state` domain
  event instead (no restart needed)"
  (`src/runtime/src/runtime/adapters/ags_reloader.py:53-59`).
- The Python-side consumer protocol already exists and is pinned:
  `src/runtime/src/runtime/adapters/bar_subscriber.py` (subscribe-before-read
  hydration, `(epoch, seq)` discard, `JobsCleared`/`NameOwnerChanged`
  re-hydration, structural payload validation), contract at
  `contracts/event-contract.{json,xml,md}`.

The inline reloader also has two concrete defects this change removes:

1. **Relaunch race.** `_restart` sends SIGTERM and immediately relaunches with
   no wait for the old pid to exit (`gtk4_app_reloader.py:136-171`). Both
   targets are single-instance `GApplication`s (`power-options-gtk` is an ELF
   GTK4 frontend with `g_application_set_application_id`; `hyprmod` is a
   Python/GTK4 app with `StartupWMClass=io.github.bluemancz.hyprmod`). A new
   instance that starts while the dying old one still owns the session-bus name
   forwards activation to it and exits — the restart silently fails.
2. **Wrong coupling.** Restarting third-party apps is a side effect of the
   swap critical path, so it cannot express "palette-affecting only" and cannot
   be hosted where the hub actually lives (the daemon).

**Hard constraint (stated up front):** `hyprmod` and `power-options-gtk` are
third-party binaries; no dotfiles code runs inside them and GTK4 parses
`gtk.css` once at startup. There is **no in-app hot reload possible for them
without forking**. The event pattern does not eliminate the restart — it
restructures it into the same consumer shape as the bar, decoupled from the
swap chain and gated to palette-affecting changes only.

## What Changes

- **Contract (additive, non-breaking):** `wallpaper.state` payload gains
  `trigger: "s"` (`set` | `regenerate` | `reconcile` | `reactive`). The
  contract already declares `additionalProperties: True` for this topic
  (`contracts/event-contract.json:85-93`;
  `src/runtime/src/runtime/adapters/emit_validation.py:165-173`), so this is a
  non-breaking addition per the contract's own versioning rule. Update
  `contracts/event-contract.{json,xml,md}`, the embedded validation schema, the
  publisher `_publish_wallpaper_state` (`main.py:446-457`), and both GJS
  consumers' pinned contract literals + drift tests.
- **Publish coverage:** emit `wallpaper.state done/error` (carrying `trigger`)
  from the standalone `reconcile` command and the daemon's reactive converge as
  well, so no palette-affecting convergence is silent to subscribers.
- **Restart primitive hardening:** `_restart` waits for the old pid to die
  (bounded poll), escalates to SIGKILL, and only then relaunches — closing the
  `GApplication` single-instance race. Discovery (`_discover_gtk4_apps`,
  `TARGET_APPS`) is kept as the shared primitive; the module docstring records
  the per-app restart-safety rationale and the allowlist-only contract.
- **New consumer binding:** `src/runtime/src/runtime/adapters/gtk4_app_subscriber.py`
  mirrors the `BarSubscriber` protocol exactly and, on `wallpaper.state done`
  with a palette-affecting `trigger`, runs the hardened restart over the
  allowlisted apps. `trigger == "regenerate"` is skipped (icons-only; the adw
  stylesheet did not change).
- **Hosting:** the subscriber runs as a background thread inside
  `dotfiles-runtime daemon run` (`main.py:2074`) — the always-on
  `dotfiles-runtime-daemon.service` that owns `org.dotfiles.Events`. No new
  process, no new Ansible role, no provisioning change.
- **Chain rewiring:** remove `Gtk4AppReloader()` from `_build_reloaders`;
  update the composition tests and docstrings.
- **Escape hatch:** new `dotfiles-runtime gtk4 restart` command invoking the
  same primitive, for degraded mode (daemon/hub absent) and manual recovery.

## Non-goals

- **No fork** of `hyprmod` / `power-options-gtk`; no in-app subscriber; no
  claimed hot reload for third-party GTK4 apps (impossible — see Why).
- No changes to `AgsReloader`, `HyprlandReloader`, `HyprpaperReloader`,
  terminal/kitty reloaders, or their reload order.
- No change to `wallpaper set` visible-first phase ordering or the meanings of
  `applying`/`visible`/`done`/`error` beyond the additive `trigger` field.
- No new daemon process or systemd unit; no Ansible/provisioning edits.
- No packaging of the contract into a new bus interface version (additive field
  stays on `org.dotfiles.Events1`).
