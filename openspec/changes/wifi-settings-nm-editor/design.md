# Design: Wi-Fi Settings footer opens nm-connection-editor

## Implementation (`WifiContent.tsx`)

- The footer is a `<box>` today; attach `Gtk.GestureClick(button=PRIMARY)`
  in `$` (same pattern as `WifiRow.act`), calling:
  `execAsync(["nm-connection-editor"]).catch((e) => console.error(...))`.
- Missing-binary fallback: pre-check is racy; instead catch spawn failure
  (`ENOENT`-class) and surface through the existing `failure`
  (`settings-message`) channel with provisioning guidance. No new error UI.
- Cursor affordance: the row already carries pointer styling via
  `settings-wifi-settings-row:hover`; confirm hover feedback reads
  clickable after wiring (mock row shows `›` + hover wash).

## Contract table

| Mock element | Code owner |
|---|---|
| Footer row click → editor (`state-1/2`) | gesture handler + `execAsync` |
| Missing binary message | `failure` channel reuse |

## Verification

- Parity gate → 0 (no new classes; handler-only change).
- Live: click footer → `nm-connection-editor` window appears; kill the
  binary from PATH in a scratch env → click shows the guidance message,
  no crash. Provision on a fresh machine includes the package (already
  covered by the `packages.yaml` + group_vars mapping + role tests).
