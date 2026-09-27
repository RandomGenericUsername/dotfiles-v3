# Proposal: Wi-Fi Settings footer opens nm-connection-editor

## Why

The `Wi-Fi Settings` footer row has no click handler at all — a dead end
where the mock promises an action. Owner requirement: open
`nm-connection-editor`. Provisioning side already landed (`nm-connection-editor`
in `packages.yaml` + `network-manager-applet`/`network-manager-gnome`
mappings, tests green); this change is the wiring + fallback.

## What Changes

- `components/wifi/WifiContent.tsx`: attach a primary-click handler to the
  `settings-wifi-settings-row` box launching `nm-connection-editor` via
  `execAsync` (precedent: `execAsync(["pavucontrol"])` in the audio widget),
  with `.catch` error logging. Shared by popup and settings-view instances
  (both render `WifiContent`).
- Fallback: if the binary is missing, log + show the existing
  `settings-message` error slot (`nm-connection-editor not installed —
  run provisioning`) instead of failing silently.

## Non-goals

- No new packages (already provisioned).
- No editor theming/embedding (external app, as specified).
- No footer restyle beyond the mock's existing row (the `opens
  nm-connection-editor` caption in the mock is annotation, not shipped text
  — ship the plain row).

## Mock anchors

- `state-1-connected` (footer row), `state-2-stc-expanded` (footer row)
