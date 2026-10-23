## 1. Source relocation (no wiring yet)

- [x] 1.1 `git mv scripts/capture-tool src/gui-tools/capture-tool/bin/capture-tool` (keep executable bit)
- [x] 1.2 `git mv dotfiles/config/ags/capture/CaptureWindow.tsx src/gui-tools/capture-tool/ui/CaptureWindow.tsx`
- [x] 1.3 `git mv` the kept scaffolding verbatim: `RecordingView.tsx`, `ScreenshotView.tsx` → `ui/`; `types.ts` → root; `controllers/*` → `controllers/`
- [x] 1.4 Author `src/gui-tools/capture-tool/app.tsx` (`instanceName: "capture"`, per-monitor `CaptureWindow`, `apply_css(colors.css)`) and `style.css` (moved `window#capture-window` / `.capture-*` block)
- [x] 1.5 Slim the bar: remove `CaptureWindow` from `dotfiles/config/ags/app.tsx`; remove the capture CSS block from `dotfiles/config/ags/style.css`

## 2. Runtime wiring

- [x] 2.1 Keybind: `ags toggle capture-window` → `ags toggle capture-window -i capture` in `dotfiles/config/hypr/keybindings.lua`
- [x] 2.2 Autostart: add staggered `ags run -d ~/.config/ags-capture --log-file …` after the bar's `ags run`
- [x] 2.3 Local smoke on host: `ags list` shows both instances; toggle works; `ags quit -i capture` restart loop is bar-independent

## 3. Provisioning

- [x] 3.1 New `gui_tools` role (per-file copies → `<install>/config/ags-capture/`) + playbook slot after `compositor_configs`
- [x] 3.2 `config-links`: add `~/.config/ags-capture` → spine symlink
- [x] 3.3 `cli_tools`: retarget capture-tool `src:` to `src/gui-tools/capture-tool/bin/capture-tool` (`dest`/mode unchanged)
- [x] 3.4 `compositor_configs`: drop the 8 capture skeleton entries + `ags/capture{,/controllers}` dir creation
- [x] 3.5 `verify`: drop 8 old `ags/capture/*` assertions, add `ags-capture/*` assertions
- [x] 3.6 Update `test_compositor_configs_role.py` (file count/list) and `test_verify_role.py` (capture dirs)

## 4. Verify

- [x] 4.1 `openspec validate extract-capture-gui-tool` passes
- [x] 4.2 Provisioning unit suite green
- [x] 4.3 VM smoke: fresh login shows bar + `capture` instance; `SUPER+PRINT` toggles; start recording → bar timer runs → quit capture instance → pause/stop still work; monitor hotplug clean
