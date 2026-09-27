# Tasks: Wi-Fi details block + repo info icon

- [x] 1. Add `info-caution` variant to `icons.yaml` (`settings-panel` group); provision-regenerate `icons.json` (bar + capture); assert entries present.
- [x] 2. Implement `SecurityRow` + real-data `ConnectionDetails` in `WifiContent.tsx` (extend `wifi-service` with MAC/IP/iface accessor only if missing).
- [x] 3. Style `.settings-security-warn` / `.settings-conn-details` / rows per mock; remove placeholder CSS.
- [ ] 4. Provision + restart AGS; live-check against `nmcli device show` values.
- [ ] 5. Parity gate green; screenshot-vs-`state-1-connected` (+ `state-2-stc-expanded` table) sign-off.

Verification: no hardcoded `a4:32`/`192.168` strings remain in `WifiContent.tsx`
(grep); weak-security row hidden on WPA2/3 networks.
