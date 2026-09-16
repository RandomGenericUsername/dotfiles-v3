## Why

Notifications are the only capture surface with no repo story at all: `dunst` is installed and autostarted, but its config is an unmanaged EndeavourOS default with no palette integration, and the capture backend never emits a notification — success and failure both vanish silently. The approved mockup (`spikes/capture-tool-ui/notifications.html`) defines the target: translucent top-right cards with a palette-resolved icon tile, a concrete title + path body, and action chips (Copy again / Open / Show in folder / Details).

Per the agreed decision, the surface is an AGS notification overlay (AstalNotifd) that becomes the session's notification daemon — full mockup fidelity, `colors.css`-driven, reloader-aware — rather than a themed `dunst`. This change carves the requirements that lead to that mockup.

## What Changes

- **New AGS notifd app** `src/gui-tools/notifications/` (standalone instance `notifications`, capture-tool deploy shape): renders the freedesktop notification stream as mockup cards — icon tile, bold title, dim body, action chips, urgency-differentiated styling (success expires, failure persists), top-right stack.
- **Daemon swap**: autostart launches the notifd AGS instance instead of `dunst`; `dunst` stays installed as a manual fallback but is no longer the session daemon, so every notification (including the existing `toggle-touchpad` `notify-send` traffic) renders in the new style.
- **Capture integration**: the capture backend emits success/failure notifications with palette-resolved `-i` icon paths and `actions`; action invocations (Copy/Open/Reveal/Details) are executed by the issuing side.
- **Styling**: exclusively `colors.css` tokens — critical severity uses the palette caution slot (`@color_03`), matching the bar's attention usage, so notification colour follows the wallpaper like every other surface; the existing AgsReloader covers the new `ags run -d` instance with no changes.

## Capabilities

### New Capabilities

- `capture-notifications`: the notifd overlay app (card layout, urgency/timeout/stack behavior, action rendering), the daemon swap, the capture backend's notification emission contract, and provisioning/autostart wiring.

### Modified Capabilities

*(None — `toggle-touchpad` and any other `notify-send` emitters keep working unchanged through the freedesktop interface.)*

## Impact

- **GUI**: new `src/gui-tools/notifications/` (`app.tsx`, notification card components, `style.css`); `gui_tools` role deploys to `<install>/config/ags-notifications/`; `config-links` symlinks `~/.config/ags-notifications`; autostart swaps `dunst` → `ags run -d ~/.config/ags-notifications`; `verify` updated.
- **Provisioning installs the notification stack**: the `packages` role installs the AstalNotifd binding (`libastal-notifd-git` via `aur_packages` in `roles/packages/vars/arch.yml`, same family as the installed `libastal-*-git` set); `verify` asserts the binding is importable (GIR/typelib present). A successful dependency provision is the GATE for the implementation below — the app is never scaffolded against a missing binding.
- **Runtime/backend**: capture finalize + typed-failure paths emit `Notify` requests with actions; action-invoked handling for copy/open/reveal/details.
- **Contracts**: none — the freedesktop `org.freedesktop.Notifications` interface is the contract; no event-contract changes.
- **Out of scope for v1**: notification history/log, do-not-disturb, per-app rules, replacing `notify-send` emitters, removing the `dunst` package.
