# Design: add-ags-notifd-notifications

Reference UI: `spikes/capture-tool-ui/notifications.html`.

## 1. Notifd app

`src/gui-tools/notifications/`, capture-tool deploy shape:
- `app.tsx`: `instanceName: "notifications"`; applies `style.css` then `~/.config/ags/colors.css` (same order as the capture app); subscribes to the AstalNotifd daemon (exact binding per the Astal version on the machine — the implementing agent confirms `AstalNotifd.Notifd.get_default()` availability first; if the binding is absent, the change stops and reports rather than hand-rolling a daemon).
- Card (per mockup `.toast`): 56px icon tile (notification's image path, which the emitter sets to a `current/icons/` file), title (13px bold), body (11.5px dim, paths `word-break`), action chips row. Urgency mapping: `normal` → default card, auto-expire on the daemon's timeout; `critical` → icon tile in the palette caution slot (`@color_03`, palette-derived — the mockup's fixed red is not carried over), persists until dismissed (matches the "Capture failed" card).
- Stack: top-right, newest on top, cap at 5 (oldest dismissed overflow, mirroring the old `notification_limit = 5`).
- Styling: panel translucency + hairline + radius tokens identical to the capture panel recipe; no new color vocabulary.

## 2. Emission contract (capture backend)

Requests go through `org.freedesktop.Notifications.Notify` with:
- `app_name`: `capture-tool`
- `summary`/`body`: concrete outcome text — never a raw backend traceback. Success: `Screenshot captured` + path; `Recording saved · MM:SS · size` + path. Failure: `Capture failed` + the categorized short message from the existing typed-error channel (plan §49 categories: permission denied, backend unavailable, encoder unavailable, audio unavailable, file error).
- `app_icon`: absolute path into `current/icons/` resolved from the same manifest + variant scheme the AGS registry uses (`capture-tool-camera` for screenshots, `capture-tool-video` for recordings, `capture-tool-warning` for failures) — no hardcoded paths; resolution logic mirrors `icon-registry.ts`.
- `actions`: `[["copy","Copy again"],["open","Open"]]` (screenshot), `[["open","Open"],["reveal","Show in folder"]]` (recording), `[["details","Details"]]` (failure).
- `urgency`: 1 (normal) for success, 2 (critical) for failure.
- The emitting side listens for `ActionInvoked` and executes: `copy` → `wl-copy < file`, `open` → `xdg-open`, `reveal` → open the containing folder, `details` → re-emit/append the full error text the daemon log holds (agent's choice of presentation, must not dump tracebacks into the card).
- Emitting primitive: the helper posts `Notify` directly over Gio (PyGObject) and subscribes to `ActionInvoked` / `NotificationClosed`, executing the invoked action itself. `dunstify --wait` is NOT usable for the round trip: our daemon emits `NotificationClosed` immediately before `ActionInvoked`, so dunstify prints the numeric close reason (`2`) and exits and the action id never reaches the emitter (verified on the session bus). The plain, action-less paths still prefer `notify-send`, falling back to `dunstify` without `--wait`; when Gio/the bus is unavailable the action card degrades to a plain toast rather than vanishing.

## 3. Daemon swap

- `dotfiles/config/hypr/autostart.lua`: replace the `dunst` line with the staggered `ags run -d ~/.config/ags-notifications` launch (same stagger discipline as the capture instance: `sleep` offset, log file under `~/.local/state/ags/`).
- `packages.yaml` untouched (`dunst` remains installed as fallback).
- `gui_tools` + `config-links` + `verify` updated for the new app dir; the AgsReloader already covers new `ags run -d` instances.
- The existing `toggle-touchpad` `notify-send` calls keep working — they now render as notifd cards (plain, no actions).

## 4. Non-goals (v1)

History/log view, do-not-disturb, per-app filtering, notification sounds, replacing `notify-send` emitters, `dunst` package removal.
