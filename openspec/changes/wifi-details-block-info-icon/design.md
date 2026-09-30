# Design: Wi-Fi details block + repo info icon

## ITR wiring

- `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml`,
  `settings-panel` group, append (guard-exempt, no `bar_mappings`):
  `- name: info-caution, template: capture-tool/default/info.svg, output: settings-panel-info-caution.svg, color_mappings: {COLOR_FOREGROUND: color3}`.
- Regenerate via the `compositor-configs.yaml` playbook (same path that
  produced the `wifi-signal-*` entries); verify both
  `config/ags/icons.json` and `config/ags-capture/icons.json` contain it.
- Resolve in code as `registry.resolve("settings-panel", "info-caution")`.
  If the owner rejects the tint at mock review, the fallback is the
  untinted re-export (foreground) — one-line change, no new art either way.

## Component work (`WifiContent.tsx`)

- New `SecurityRow()`: info-glyph `<image pixel_size={16}>` + label;
  `visible={isWeakSecurity}` derived from the active network (WPA vs WPA2/3
  knowledge in `wifi-service`; if the service can't tell, hide the row —
  never show a lying warning).
- `ConnectionDetails()`: label/value rows MAC / IP·iface / Speed /
  Last test / Ran. Real data first: MAC+IP+iface from NM device props
  (extend `wifi-service` with a lightweight accessor if missing — read-only
  D-Bus, no new subscriptions beyond existing device watch); Speed/Last-test/
  Ran from speedtest `lastResult()` (+ timestamp — add `ranAt` to the
  service state if absent); `—` fallback per cell, never placeholders.

## Contract table

| Mock element | Code owner |
|---|---|
| Info glyph, caution tint | `icons.yaml` → `icons.json`, `registry.resolve("settings-panel","info-caution")` |
| Security row text/visibility | `SecurityRow`, `settings-security-warn` |
| Details table rows | `ConnectionDetails`, `settings-conn-details`, detail-row classes |

## Verification

- Parity gate → 0. Rendered glyph eyeballed against
  `capture-tool/default/info.svg` (same shapes, caution color).
- Live with real connection: MAC/IP match `nmcli`; weak-security row
  appears only for WPA-personal networks; screenshot vs `state-1-connected`.
