## Purpose

A palette-driven AGS notification surface that renders capture outcomes as the approved mockup cards, and becomes the session's notification daemon in place of the unmanaged `dunst`.

## ADDED Requirements

### Requirement: Provisioned notification stack (implementation gate)

Provisioning SHALL install every dependency the notification surface needs — notably the AstalNotifd binding (`libastal-notifd-git` in `aur_packages`, same family as the installed `libastal-*-git` set) — and the `verify` role SHALL assert the binding is importable (GIR/typelib present on the machine). The app implementation SHALL NOT begin until this provision succeeds.

#### Scenario: Binding present after provision
- **WHEN** the `packages` playbook converges
- **THEN** `pacman -Q libastal-notifd-git` succeeds and the `AstalNotifd` GIR namespace resolves

#### Scenario: Verify pins the dependency
- **WHEN** the `verify` role runs
- **THEN** it fails if the notifd binding is not importable

### Requirement: Notifd overlay app

A standalone AGS app SHALL serve `org.freedesktop.Notifications` and render incoming notifications as top-right stacked cards matching `spikes/capture-tool-ui/notifications.html` (icon tile, bold title, dim body, action chips), styled exclusively with `colors.css` tokens.

#### Scenario: Plain notification renders as a card
- **WHEN** `notify-send "Touchpad" "enabled"` is issued
- **THEN** a card appears top-right with the summary as title and the body as dim text, expiring on the default timeout

#### Scenario: Stack is bounded
- **WHEN** more than 5 notifications are live
- **THEN** the oldest is dismissed so at most 5 cards show

### Requirement: Urgency-differentiated failures

`critical`-urgency notifications SHALL persist until dismissed and render the icon tile in the palette caution slot (`@color_03`); `normal` notifications SHALL expire on timeout. The notification sheet SHALL contain no literal colors.

#### Scenario: Failure persists
- **WHEN** a capture failure arrives with urgency critical
- **THEN** its card stays until dismissed and matches the mockup's "Capture failed" card

### Requirement: Capture emission contract

The capture backend SHALL emit `Notify` requests for screenshot capture, recording completion, and categorized failures, with palette-resolved `current/icons/` icon paths, the specified actions, and urgency normal/critical respectively; the emitting side SHALL execute Copy/Open/Reveal/Details on `ActionInvoked`.

#### Scenario: Screenshot success notifies
- **WHEN** a screenshot capture finalizes
- **THEN** a card shows `Screenshot captured`, the output path, and Copy-again/Open actions with the `capture-tool-camera` icon

#### Scenario: Recording success notifies
- **WHEN** a recording finalizes
- **THEN** a card shows `Recording saved · MM:SS · size`, the output path, and Open/Show-in-folder actions with the `capture-tool-video` icon

#### Scenario: Failure notifies without tracebacks
- **WHEN** a capture fails (e.g. screencopy permission denied)
- **THEN** a persistent card shows `Capture failed`, the short categorized message, and a Details action — never a raw traceback

#### Scenario: Actions execute
- **WHEN** the user invokes the Open action on a recording-saved card
- **THEN** the file opens in the default application

### Requirement: Daemon swap

Autostart SHALL launch the notifd AGS instance instead of `dunst` (same stagger/log discipline as the other AGS instances); provisioning SHALL deploy the app sources and symlinks; `verify` SHALL expect them.

#### Scenario: Session daemon is the overlay
- **WHEN** logging in after provisioning converges
- **THEN** the notifications AGS instance is running, `dunst` is not started by autostart, and `notify-send` traffic renders as cards

#### Scenario: dunst cannot steal the bus
- **WHEN** provisioning converges on a machine where the dunst user unit was enabled
- **THEN** `dunst.service` is stopped and masked, so the overlay owns `org.freedesktop.Notifications` instead of losing it to a respawning dunst

#### Scenario: Foreign daemon is detected, not crashed
- **WHEN** the overlay starts while another process already owns `org.freedesktop.Notifications`
- **THEN** it logs the conflict and exits cleanly (no half-initialised instance)
