# Proposal: Wi-Fi details block + repo info icon

## Why

The connection-details block is hardcoded placeholder text (`a4:32:…`,
`192.168.1.42`) with no icon, while the mock specifies a MAC / IP·iface /
Speed / Last-test / Ran table headed by the repo's info glyph. Owner
explicitly corrected: **info**, not warning.

## What Changes

- ITR (no new artwork): add a `settings-panel` variant re-exporting
  `capture-tool/default/info.svg`, tinted caution (`COLOR_FOREGROUND: color3`,
  following the `warning-caution` precedent in `icons.yaml`), regenerated
  through provisioning into `icons.json` (both bar + capture manifests).
- `components/wifi/WifiContent.tsx` (`ConnectionDetails` + security row):
  rebuild as the mock's table — security row with the info glyph +
  `Weak Security (WPA)` text (shown only when the active network is
  WPA/personal, else hidden); MAC / IP·iface rows from real data where the
  services provide them, clearly-marked fallbacks (`—`) where not; Speed row
  from the last speed-test result when present; Last-test / Ran rows.
- `style.css`: real `.settings-security-warn` / `.settings-conn-details`
  / detail-row styling per `state-1-connected` (current rules are
  placeholder-grade).

## Non-goals

- No new SVG artwork (re-export only — ITR owns the render).
- No speed-test logic (changes 6–8).
- No switch styling (change 4).

## Mock anchors

- `state-1-connected` (security row + details table)
- `state-2-stc-expanded` (details table variant without Last-test rows)
