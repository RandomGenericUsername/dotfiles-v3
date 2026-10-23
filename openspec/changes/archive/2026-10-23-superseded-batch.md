# 2026-10-23 superseded batch

These 27 changes targeted the in-repo AGS bar/apps, which moved whole to the pinned `ags-apps` unit (REQ-001). Each archived change carries a `SUPERSEDED.md` pointer to the code that now owns the behavior. Archived with `--skip-specs`; the artifacts are preserved for provenance.

| Change | New owner |
| --- | --- |
| `add-ags-notifd-notifications` | `ags-apps/notifications` |
| `add-ags-settings-panel` | `ags-apps/bar/settings-panel` |
| `add-battery-status-panel` | `ags-apps/bar/components/battery` |
| `add-bluetooth-bar-popup` | `ags-apps/bar/components/bluetooth` |
| `add-capture-settings` | `ags-apps/capture-tool` |
| `add-capture-ui-restyle` | `ags-apps/capture-tool` |
| `add-hypr-pano-clipboard-manager` | `ags-apps/hypr-pano` |
| `add-icon-color-mapping-editor` | `ags-apps/icme` |
| `add-mic-live-dot-backdrop-state` | `ags-apps/bar/audio` |
| `add-recording-indicator-popup` | `ags-apps/bar + ags-apps/capture-tool` |
| `ags-bar-validate-at-install` | `ags-apps/bar/bar/validate.ts` |
| `ags-delete-redundant-code` | `ags-apps/bar + ags-platform` |
| `ags-remove-bar-bridge` | `ags-apps/bar (the bridge is retired)` |
| `enhance-ags-bar` | `ags-apps/bar` |
| `extract-ags-shared-components` | `ags-platform + ags-apps/bar` |
| `finish-audio-bar-migration` | `ags-apps/bar/audio` |
| `fix-audio-panel-default-output-and-duplicate-rows` | `ags-apps/bar/audio` |
| `fix-capture-webm-codec` | `ags-apps/capture-tool` |
| `fix-capture-window-identity` | `ags-apps/capture-tool` |
| `fix-sound-panel-icon-sync` | `ags-apps/bar/audio` |
| `gtk-theming-consumer` | `ags-platform/ports/theme.ts + adapters/theme.ts` |
| `harden-capture-typecheck-config` | `ags-apps/capture-tool/tsconfig*` |
| `redesign-ags-audio-panel` | `ags-apps/bar/audio` |
| `refactor-ags-settings-panel-dbus` | `ags-apps/bar/settings-panel` |
| `refactor-capture-tool-hexagonal` | `ags-apps/capture-tool (domain/ports/adapters)` |
| `verify-capture-placement-coverage` | `ags-apps/capture-tool (whole-unit deploy; per-file list retired)` |
| `wallpaper-selector-contrast-toggle` | `ags-apps/wallpaper-selector/lib/contrast.ts` |

Validation after the batch: `openspec validate --all`.
