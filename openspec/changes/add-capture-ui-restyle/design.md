# Design: add-capture-ui-restyle

Reference UI: `spikes/capture-tool-ui/` (approved mockups; `index.html` gallery, `mockup.css` token sheet).

## 1. Icon pipeline (A1 + A2)

Authored inputs, per the "Adding an Icon" pipeline doc (SVG template → `icons.yaml` → provisioned `icons.json` → ITR render to `current/icons/` → `IconRegistry` → widget):

| Source file (`~/Downloads/…`) | Template (`dotfiles/assets/icon-templates/capture-tool/default/`) | Variant | Output (`current/icons/`) | Job in UI |
|---|---|---|---|---|
| `recorder-icons/camera.svg` | `camera.svg` | `camera` | `capture-tool-camera.svg` | Screenshot mode + CTA |
| `recorder-icons/video-recorder.svg` | `video.svg` | `video` | `capture-tool-video.svg` | Recording mode |
| `recorder-icons/recorder-region.svg` | `region.svg` | `region` | `capture-tool-region.svg` | Region tile |
| `recorder-icons/recorder-monitor.svg` | `monitor.svg` | `monitor` | `capture-tool-monitor.svg` | Screen tile |
| `recorder-icons/recorder-window.svg` | `window.svg` | `window` | `capture-tool-window.svg` | Window tile |
| `recorder-icons/clipboard.svg` | `clipboard.svg` | `clipboard` | `capture-tool-clipboard.svg` | Clipboard output |
| `recorder-icons/save.svg` | `save.svg` | `save` | `capture-tool-save.svg` | Save output |
| `recorder-icons/speaker.svg` | `speaker.svg` | `speaker` | `capture-tool-speaker.svg` | System audio |
| `recorder-icons/mic.svg` | `mic.svg` | `mic` | `capture-tool-mic.svg` | Mic audio |
| `info.svg` | `info.svg` | `info` | `capture-tool-info.svg` | GIF notice |
| `recorder-icons/warning.svg` | `warning.svg` | `warning` | `capture-tool-warning.svg` | Error feedback |
| `recorder-icons/recorder-pause.svg` | `pause.svg` | `pause` | `capture-tool-pause.svg` | Bar + popup |
| `recorder-icons/recorder-play.svg` | `play.svg` | `play` | `capture-tool-play.svg` | Bar + popup |
| `recorder-icons/recorder-stop.svg` | `stop.svg` | `stop` | `capture-tool-stop.svg` | Bar + popup |

Placeholder conversion (committed templates MUST NOT contain literal colors):
- All `stroke="black"` / `fill="black"` / `fill="#060606"` → `{{COLOR_FOREGROUND}}`.
- `recorder-region`'s `fill="white"` region body → `{{COLOR_ACCENT}}` (deliberate two-tone: accent region, foreground stroke).
- Keep the 1024 `viewBox`; keep stroke widths (they scale down to 15–24px render sizes; verify legibility at `pixel_size=16` before finalizing).

Group registration in `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml`:

```yaml
capture-tool:
  color_mappings:
    COLOR_FOREGROUND: foreground
    COLOR_ACCENT: color13
  variants:
    - name: camera
      template: capture-tool/default/camera.svg
      output: capture-tool-camera.svg
    # … (one entry per row above)
```

`COLOR_ACCENT: color13` follows the existing `battery` precedent; the user retunes via the icon color mapping editor (`SUPER+I`) — no hand-editing of rendered output, ever.

Retirement (same change, no orphans):
- Delete `screen-recorder` group block from `icons.yaml` and `dotfiles/assets/icon-templates/screen-recorder/`.
- Delete `screenshot-tool.yaml`, its `icons.yaml` block, and `dotfiles/assets/icon-templates/screenshot-tool/`.
- Bar `recording.tsx`: `registry.resolve("screen-recorder", variant)` → `registry.resolve("capture-tool", variant)`.
- Regenerate `dotfiles/config/ags/icons.json` through the manifest task; update `verify` expected-files (remove `icon-mappings/screenshot-tool.yaml`, add the new template/manifest entries); update `test_verify_role.py` and `templates.mjs` fixtures.
- Rendered leftovers in `current/icons/` (`screen-recorder-*.svg`, `all-screen-selection.svg`, …) are inert once unreferenced; a VM/provisioning converge replaces them.

Provisioning for capture icons: `compositor_configs` adds a second content task writing the decoded manifest to `config/ags-capture/icons.json` (same registered content, new `dest` var); `gui_tools` per-file list gains the `lib/` dir ensure + `lib/icon-registry.ts` placement (same `force: true`, repo-authoritative discipline as the capture app files); `verify` gains the two expected paths.

## 2. Capture window restructure (A3 + A4)

Markup contract (mirrors `spikes/capture-tool-ui/screenshot.html` / `recording.html` / `recording-gif.html`):

```text
mode-switch (2 buttons, icons via resolve("capture-tool", "camera"/"video"))
target tiles ×3 (icons region/monitor/window, single-select group)
setting rows: label-left micro-cap + segmented pills right
    screenshot: delay(None/3s/5s/10s) · format(PNG/JPEG) · output(clipboard/save, icons)
    recording:  fps(24/30/60) · format(MP4/WebM/GIF) · audio(speaker/mic/none, icons) ·
                quality(low/medium/high) · duration(∞/10s/30s/60s/custom)
GIF mode: audio row removed; fps → (10/15/20/30); + size row (original/75%/50%);
          + amber notice ("GIF has no audio track…")
primary CTA: full-width, mode-tinted (accent for screenshot, the palette's
             caution slot for recording),
             icon + label; footer: Esc/Enter hints + "remembers last choices"
```

State: the mockups are static; the TSX keeps the existing `let`-variable + `select()` group pattern (already in `CaptureWindow.tsx`) and extends it to audio/duration/format (currently unwired). Backend passthrough: `start` gains `--audio`/`--duration` args; `screenshot` unchanged.

Keyboard: `Escape` hides the window (cancel), `Enter` triggers the primary action. The window already runs `keymode=ON_DEMAND`; add explicit key controllers (pattern: existing keybind handling in sibling GUI apps, e.g. hypr-pano).

Stylesheet: port `mockup.css` component classes onto GTK4 CSS with `@color_*` variables:
`--panel-bg → alpha(@color_00, .92)`, `--surface → alpha(@color_background, .45)`,
`--hairline → alpha(@color_foreground, .12)`, `--accent → @color_06`-family (bright accent),
recording accent + caution → `@color_03` (the bar's pre-existing paused/attention slot;
palette-derived like rofi's generated `colors.rasi`, so a blue wallpaper yields a blue record
CTA — the mockup's hardcoded record red is NOT carried into the implementation).
Selected pill = accent tint + accent border (departure from the bar's
`@color_01` fill, per approved design decision). GTK4 CSS has no `color-mix` — precompute via `alpha()`/`mix()`.
The capture window's sheet contains NO literal colors.

## 3. Persistence (A5)

JSON state file (GUI-tool-local, e.g. alongside the app's state dir): `{ screenshot: {target, delay, format, save}, recording: {target, fps, format, audio, quality, duration} }`. Read on window show, written on capture/record start. No provisioning surface; no hub involvement.

## 4. Backend (A6)

`bin/capture-tool start`: `--audio {none,system,mic}` (default none — note: the mockup shows System selected; the persisted default comes from A5, the CLI default stays conservative `none`), `--duration {<seconds>|0=infinite}` (default 0). Audio routes into the recorder backend's device selection (PipeWire source mapping per project plan §9/§44); duration implements auto-stop → finalize (plan §11). GIF (`--format gif`): NOT a recorder passthrough — capture frames/video at the selected fps band then convert (FFmpeg pipeline per plan §43), apply `--size` scale (original/75%/50%), never open audio hardware. Failures surface through the existing typed-error channel so the UI can categorize them (plan §49; notification surfacing is Change 3).
