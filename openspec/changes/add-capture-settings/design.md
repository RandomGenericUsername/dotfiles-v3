# Design: add-capture-settings

Reference UI: `spikes/capture-tool-ui/settings.html`.

## 1. Config file

Path: `$XDG_CONFIG_HOME/capture-tool/config.json` (`~/.config/capture-tool/config.json`), created with `mkdir_with_parents` on first write. Never provisioned; the app owns it. Schema (all keys optional — missing keys fall back per §3):

```jsonc
{
  "screenshot_dir": "~/Pictures/Screenshots",
  "recording_dir": "~/Videos/Recordings",
  "filename_pattern": "{kind}_%Y-%m-%d_%H-%M-%S",
  "notifications": true,
  "screenshot": { "format": "png", "output": "clipboard", "cursor": false },
  "recording": { "fps": 60, "quality": "high", "audio": "system", "cursor": true }
}
```

- `{kind}` expands to `screenshot`/`recording`; the rest is `strftime` (validated on write: must expand deterministically; extension is appended by the backend, never part of the pattern).
- `~` and `$HOME`/env expansion apply to directory values; directories are created on first save (`mkdir_with_parents`).
- Corrupt JSON → ignore the file wholesale, use defaults, overwrite on next save (loud log, no crash).

## 2. Settings view

Entry: gear button in the panel footer (icon `capture-tool` group needs NO new glyph — reuse the `info`... no: use a text-labeled ghost button "Settings" to avoid a new icon dependency; the `capture-tool` group stays at 14 variants).

Layout mirrors `settings.html`: group micro-caps (General / Screenshot / Recording), rows with name + dim description left and control right (path chips open no dialogs in v1 — tap-to-edit via inline `Gtk.Entry` on click; toggles for booleans; compact segmented pills reusing the main view's component pattern).

Navigation: settings replaces the mode-switch + views (single `settingsView` box toggled like the existing views). Footer gear becomes Back while in settings. `Escape` hierarchy: settings → back to mode view; mode view → hide window (existing). `Enter` in settings saves (same as leaving the view).

On save: validate → write config → apply to live state (dirs/pattern take effect on next capture; defaults feed the NEXT window open, never stomp current selections).

## 3. Precedence

- Save paths: explicit `--output` > config dirs+pattern > today's hardcoded defaults.
- Initial selections on open: last-used UI state (`capture-ui.json`, Change 1 A5) > settings defaults > hardcoded first-run constants.
- Notifications toggle `false` → backend skips ALL `Notify` emission (screenshot + recording + failure paths), silently.

## 4. Backend

- Load config at command start (cheap JSON read, `try/except` → defaults). No backend restart/reload semantics — every invocation reads fresh.
- Screenshot: default output path = `<screenshot_dir>/<pattern kind=screenshot>.<fmt>` unless `--output` given; `--cursor` adds the grim cursor flag (verify `grim --help` on-machine; if grim lacks cursor support the flag is accepted-but-documented and the spec records the outcome explicitly).
- Recording: default output path likewise under `<recording_dir>`; `--cursor` maps to the recorder's cursor flag (`gsr -cursor yes/no`; wf-recorder: document outcome on-machine).
- Backend readout for the UI: `capture-tool` exposes the detected backend name (existing `choose_backend()`) so the settings row shows `Automatic (<name>)`. Display-only.
- Tests mirror the existing CLI suite (config load fallbacks, precedence, pattern expansion, cursor flag presence per backend, notification gating).
