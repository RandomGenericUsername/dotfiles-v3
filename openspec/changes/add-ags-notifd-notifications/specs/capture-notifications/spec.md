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

Notification icons SHALL be palette-tinted per outcome (success copies render in the stack accent, failure in the caution slot) so the cards carry the wallpaper's colour, matching the tinted tile the overlay draws. File actions (Open / Copy again / Show in folder) SHALL be offered only for captures that produced a file: a clipboard capture keeps NO file (the UI's Clipboard/Save pill is the user's explicit choice) and therefore emits an action-less card. `Open` SHALL launch the file with the XDG opener.

#### Scenario: Clipboard capture stays file-less
- **WHEN** a screenshot is captured with the Clipboard output selected
- **THEN** nothing is written to the screenshots directory and the card shows only `Copied to clipboard` with no actions

#### Scenario: Saved capture offers file actions
- **WHEN** a screenshot is captured with the Save output selected
- **THEN** the file is written under the configured screenshots directory and the card offers Copy again / Open against that path

#### Scenario: Recording success notifies
- **WHEN** a recording finalizes
- **THEN** a card shows `Recording saved · MM:SS · size`, the output path, and Open/Show-in-folder actions with the accent-tinted `video` icon

#### Scenario: Failure notifies without tracebacks
- **WHEN** a capture fails (e.g. screencopy permission denied)
- **THEN** a persistent card shows `Capture failed`, the short categorized message, and a Details action with the caution-tinted `warning` icon — never a raw traceback

#### Scenario: Actions execute
- **WHEN** the user invokes the Open action on a recording-saved card
- **THEN** the file opens in the default application

#### Scenario: Action delivery does not depend on the notifier CLI
- **WHEN** any action chip is invoked
- **THEN** the emitting helper receives `ActionInvoked` over the session bus and executes it — the round trip never relies on a CLI printing the action id to stdout

#### Scenario: Stale-chip race avoided
- **WHEN** the overlay invokes an action
- **THEN** it does not clear the card in the same tick (the daemon emits `NotificationClosed` before `ActionInvoked`), so the action is always delivered

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
