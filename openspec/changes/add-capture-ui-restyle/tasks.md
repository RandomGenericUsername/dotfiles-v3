# Tasks: add-capture-ui-restyle

Execution order: icons pipeline (1–4) → GUI (5–7) → persistence (8) → backend (9–10) → converge (11). Stories 5–7 MAY run in parallel with 1–4 (variant names are frozen in `design.md`); story 9–10 MAY run in parallel with everything (CLI contract frozen in `design.md §4`).

## 1. Convert and place icon templates

- [ ] 1.1 Copy the 14 source SVGs from `~/Downloads/recorder-icons/` (+ `~/Downloads/info.svg`) to `dotfiles/assets/icon-templates/capture-tool/default/` with the design.md filenames; substitute `black`/`#060606` → `{{COLOR_FOREGROUND}}`, region white fill → `{{COLOR_ACCENT}}`; verify no literal colors remain and each file has a valid `viewBox`
- [ ] 1.2 Register the `capture-tool` group in `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml` (14 variants, outputs `capture-tool-*.svg`, mappings per design.md); remove the `screen-recorder` group block and its template dir; delete `screenshot-tool.yaml`, its manifest block, and its template tree
- [ ] 1.3 Update `dotfiles/config/ags/bar/widgets/recording.tsx` group reference to `capture-tool`; update `test_verify_role.py`, `templates.mjs` fixtures, and `verify` expected-files (drop `icon-mappings/screenshot-tool.yaml`)
- [ ] 1.4 Run `itr render` (or the runtime seed path) and confirm all 14 outputs land in `current/icons/`; re-render on a second palette to confirm placeholder substitution; visually confirm pause/play/stop at 16px
- [ ] 1.5 Verify: `rg` legacy-name scan clean (except historical docs); icon group unit/integration tests for ITR pass

## 2. Provision icons to both AGS instances

- [ ] 2.1 `compositor_configs`: add a second JSON-manifest task writing the decoded manifest to `config/ags-capture/icons.json` (new `dest` var, same registered content)
- [ ] 2.2 `gui_tools`: ensure `ags-capture/lib/` dir + add per-file `lib/icon-registry.ts` placement (`force: true`)
- [ ] 2.3 `verify`: expect both `icons.json` paths + capture `lib/icon-registry.ts`; provision in check mode then converge, confirm `registry.resolve("capture-tool", "camera")` hits a real file on the target paths

## 3. Restructure CaptureWindow.tsx

- [ ] 3.1 Mode-switch header with resolved `camera`/`video` icons and `.active` mode tinting; view swapping (existing `selectMode` pattern extended)
- [ ] 3.2 Target tiles ×3 with resolved icons, exclusive `.selected` behavior, feeding `screenshotTarget`/`recordingTarget`
- [ ] 3.3 Setting rows for screenshot (delay/format/output) and recording (fps/format/audio/quality/duration) as label + segmented pills with icons; wire audio/duration/format into live state; pass `--audio`/`--duration` on `start`
- [ ] 3.4 GIF mode: conditional rows (audio removed, fps 10/15/20/30, size row), amber `info` notice; restore on deselect
- [ ] 3.5 Keyboard: `Escape` hides, `Enter` fires the primary action (key controllers on the window)
- [ ] 3.6 Verify: `ags bundle`/typecheck passes for the capture app; options-per-row match the mockups (screenshot.html, recording.html, recording-gif.html)

## 4. Port the stylesheet

- [ ] 4.1 Rewrite `src/gui-tools/capture-tool/style.css` from `spikes/capture-tool-ui/mockup.css` onto `@color_*` tokens per design.md §2 (no `color-mix`; use `alpha()`/`mix()`); mode-tinted primary CTA; selected = accent tint + border
- [ ] 4.2 Verify: visual comparison against the three mockup pages at the same 560px width; palette-swap smoke (second palette → reloader → new colors, no edits)

## 5. Persist last-used configuration

- [ ] 5.1 Read persisted state on window show; write on capture/record start; first-run defaults per spec
- [ ] 5.2 Verify: set → capture → close → reopen round-trip returns the same selections

## 6. Backend: audio, duration, GIF

- [ ] 6.1 `capture-tool start --audio/--duration` with PipeWire routing, auto-stop finalize, typed errors; unit tests mirroring existing capture tests
- [ ] 6.2 GIF pipeline (fps band, `--size`, no-audio-hardware guarantee, FFmpeg conversion); tests for scale math + typed failures
- [ ] 6.3 Verify: `capture-tool start --audio none --duration 10` produces a valid file; `--format gif --size 50` produces a half-scale GIF with no audio device opened

## 7. Converge

- [ ] 7.1 Full provisioning converge in the VM harness (`vm-fresh`/`vm-continue` per repo practice): `ags list` shows `capture`; `SUPER+PRINT` opens the restyled window; bar indicator shows new pause/play/stop art mid-recording
- [ ] 7.2 Update the "Adding an Icon" guide's `screen-recorder` examples to `capture-tool`
