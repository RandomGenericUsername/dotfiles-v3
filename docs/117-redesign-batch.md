# Redesign batch — architecture, live state and pending designs

Canonical batch record. Updated 2026-11-21. The old `/tmp/opencode` handoff is a
symlink to this file; this repo copy is the source of truth.

## Live state

| Item | Value |
| --- | --- |
| `ags-wallpaper-selector` | **v0.6.29** (in-page settings; owner-confirmed) |
| `dotfiles-assets` | **v0.22.3** installed (look-frame radius) |
| `dotfiles-provision` | **v0.1.97** released/installed (tag `f9a0fdb`) |
| `dotfiles-v3` composition | **v0.2.10** live (app v0.6.29 + assets v0.22.3 + engine v0.1.97) |
| `ags-bar` | v0.6.34 (sound panel reference) |
| `ags-platform` / contracts | v1.2.0 / v0.13.0 |

Live link: `~/.config/ags-wallpaper-selector` -> `apps/wallpaper-selector/v0.6.29`.

Rollback: composition v0.2.9 + assets v0.22.2 + engine v0.1.96 (app v0.6.24).

## Appearance/skin architecture (binding)

1. One appearance generation (palette + skin + mode), installed as one
   USER-priority CSS provider. Apps read `current/manifest.json` +
   `appearance/<configDir>.css`; the bundled app CSS is the fallback.
2. Surface roles are semantic: `surface.window` = outer toplevel;
   **`surface.panel` = AGS bar *and* layer-shell overlays**; `card` / `cell` /
   `control` / `pill` = inner surfaces. Do not invent per-app roles.
3. `[host]` delegates geometry — window/panel/card/control/cell radii and
   border widths — to the compositor. The wallpaper overlay follows Hyprland
   `rounding 0` / `border 1` through `surface.panel`.
4. App owns layout/structure/content; skin owns paint/type/ink. The skin
   template styles the app-declared classes with role tokens (the sound panel's
   `.audio-*` pattern). App CSS is layout + fallback only.
5. The app never reads appearance tokens (`appearance.value(...)` fails the
   layout gate) and never mimics role geometry with CSS inheritance. If an
   app-owned node needs role geometry, the template supplies it (e.g.
   `.ws-look-frame { border-radius: {{SKIN_SURFACE_CONTROL_RADIUS}}; }` in
   assets v0.22.3).
6. State replaces, never stacks: the selected chip's app ring suppresses the
   skin's base hairline, so there is one border.
7. Per-item/content accent is app-owned. The wallpaper palette hint drives the
   selected ring and Set button via a per-widget provider at `USER + 1`; the
   skin still owns the role surfaces.
8. No `Gtk.Popover` for in-overlay panels. A popover is a separate compositor
   popup; its grab/pointer focus can survive the unmap until motion and swallow
   the next same-spot click. Use the mock's in-page panel (`.settings-pop`)
   with a full-window catcher.
9. The `surface.overlay` experiment is **not consumed**. contracts v0.14.0 and
   assets v0.23.0 were released during exploration; the composition pins assets
   **v0.22.3**, which maps overlays to `surface.panel`.

## Pending design index (workspace paths)

Relative to the workspace root (`~/Development/dotfiles/`). Hashes are the
frozen mock sha256.

| Design | Ticket | Mock + hash | Status |
| --- | --- | --- | --- |
| Wallpaper selector | `ags-wallpaper-selector/tickets/REQ-005-overlay-redesign/ticket.md` | `…/mock.html` `60410943d66b326b7384cdb5949ed68f384d14404eea7df83d77dfc4e6d0db74` | **live v0.6.29** |
| Sound panel (reference) | `ags-bar/tickets/REQ-005-sound-panel-design/ticket.md` | `…/mock.html` `b4a731c39eba08c1e3c75d6283fa27f1f3f1d788c6c349daf7a126d7050310c3` | implemented in v0.6.34 |
| Clipboard | `ags-clipboard/tickets/REQ-009-clipboard-card-modes/ticket.md` | `…/mock.html` `9e3f6ecaa396837194697b1d6922d7946677ea18440e4d7b5bb9c2e1fd278d19` | pending |
| Wi-Fi | `ags-bar/tickets/REQ-007-wifi-panel-design/ticket.md` | `…/mock.html` `0f32f515a2081a9fa94baf9ae7d8f80ad80c19dc99f092a61d7477bcbcfba715` | pending |
| Battery | `ags-bar/tickets/REQ-008-battery-panel-design/ticket.md` | `…/mock.html` `2944b329d2e69a73b4c6e1fe8a59efdace2336e53ab83613e2051362872ef3f1` | pending |
| Bluetooth | `ags-bar/tickets/REQ-009-bluetooth-panel-design/ticket.md` | `…/mock.html` `0df4939a4c02b1df38f8f966d0539b9569ad27c17aa1c55532fb8807d3d57eed` | pending |

Supporting documents:

- Skin architecture and token groups:
  `dotfiles-assets/skins/README.md` (including “Overlay app implementation
  pattern”).
- Appearance contract:
  `contracts/schemas/appearance-manifest.schema.json` and
  `contracts/schemas/appearance-json.schema.json`.
- App skin integration: `ags-wallpaper-selector/README.md`
  (“Overlay and skin integration”).
- Live wallpaper record: `ags-wallpaper-selector/tickets/REQ-005-overlay-redesign/ticket.md`
  (post-release notes) and `dotfiles-v3/docs/tickets/REQ-137-skin-polish.md`.
- Batch composition pin: `dotfiles-v3/docs/tickets/REQ-137-skin-polish.md`.

## Guidance for pending refactors

- Use `surface.panel` for AGS overlays; `surface.window` only for true
  toplevels (rofi/wlogout/kitty).
- Put paint in the app's skin template using role tokens; keep app CSS to
  layout/fallback.
- Never read appearance tokens from app code; never use CSS inheritance to
  reproduce role geometry.
- Selected states replace the base role border, not stack on it.
- Per-item/content colour is app-owned (content palette); role surfaces are
  skin-owned.
- In-overlay panels are in-page (mock `.settings-pop`) with a catcher; do not
  ship a `Gtk.Popover` for them. Bar-anchored panels that remain popovers must
  handle the compositor pointer-focus/third-click behavior explicitly.
- Do not consume contracts v0.14.0 / assets v0.23.0 (`surface.overlay`).

## Wallpaper implementation (v0.6.29)

Full-monitor overlay; `surface.panel` shell painted by the active skin with
Hyprland geometry. Looks: `Original` + variants; selected ring is an overlay
above the picture, radius from the skin template, colour from the focused
wallpaper's palette hint (USER+1); selected state suppresses the base hairline.
Set/bar progress use the same accent with computed contrast ink. Commit: 120 s
watchdog, three event steps, 1.2 s hold then hide, deferred rescan. Settings:
in-page `.ws-settings` + full-window catcher; plain `Gtk.Button` gear covering
the full 42 px circle. Grid: one search pill, delegated focus, `.97` scrim.

## Non-blockers

- GTK has no `backdrop-filter`; blur tokens are inert.
- `AstalHyprland` emits `Json-CRITICAL` on this host (same in the capture tool).
- `wallpapers/test.png` is an 11-byte ASCII file; the scan skips it.
- The AGS bar user service can be inactive after a reboot (start
  `dotfiles-ags-bar.service`).
- Engine v0.1.96/v0.1.97: the historical-tag role test's Ansible timeout is
  600 s for cold hermetic hosts; assertions unchanged.
