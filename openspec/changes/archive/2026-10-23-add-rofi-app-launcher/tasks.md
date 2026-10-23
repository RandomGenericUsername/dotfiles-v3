# Tasks: rofi launcher (live)

## Status

The launcher is live in the split layout. The original pre-split plan is
preserved in `tasks-pre-split.md`; the specs beside it are the pre-split design
record. The live implementation is:

- `dotfiles-assets/configs/rofi/launcher/config.rasi` (`rofi-ui` toggle theme)
- `dotfiles-assets/configs/hypr/keybindings.lua:32-35` (`rofi-ui` bind)
- `src/runtime` `colors.rasi` artifact + `config/rofi/colors.rasi` pointer
- `dotfiles/provisioning/packages.yaml` `rofi` package

## Acceptance (2026-10-23)

- [x] G1 runtime palette/reconcile suites green (existing `src/runtime` tests)
- [x] G2 engine/provisioning suites green (existing gates)
- [x] G3 host provisioning: `~/.config/rofi` -> `<install>/config/rofi`; `launcher/config.rasi` present; bootstrap idempotent
- [x] G4 `current/colors.rasi` exists; `<install>/config/rofi/colors.rasi` -> `current/colors.rasi`; `rofi -config … -dump-theme` exit 0
- [x] G5 owner green: `SUPER+D` opens the themed launcher, and a wallpaper change is followed on relaunch
