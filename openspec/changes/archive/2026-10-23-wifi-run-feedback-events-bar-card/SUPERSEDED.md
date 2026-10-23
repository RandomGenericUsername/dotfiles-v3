# Superseded by `ags-apps`

This change targeted the in-repo AGS bar (`dotfiles/config/ags`), which moved
whole to the pinned `ags-apps` unit (REQ-001). The behavior is implemented and
tested in `ags-apps/bar`:

- Wi-Fi popup/details/signal tile/password reveal/known networks:
  `bar/components/wifi/WifiContent.tsx`
- Reactive signal icon: `bar/settings-panel/controls/wifi.tsx`,
  `bar/lib/wifi-signal.ts`
- Speedtest run feedback/interval/Ookla parse:
  `bar/services/speedtest-service.ts`, `bar/components/wifi/WifiContent.tsx`
- `nm-connection-editor` footer and STC chevron:
  `bar/components/wifi/WifiContent.tsx`
- Switch restyle: `bar/style.css` (`.settings-switch`)
- Mock parity: `bar/tests/mocks/wifi-popup-mockup.html`,
  `bar/tests/mocks/README.md`

Archived for provenance. Re-open work in `ags-apps`, not here.
