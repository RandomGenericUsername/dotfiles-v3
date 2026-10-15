# Tasks

## 1. Scaffold the studio as a launch-on-demand AGS app

- [ ] 1.1 Create `src/gui-tools/btop-theme-studio/` (AGS app: `app.tsx`, `style.css`, `ui/`, `lib/`) and a Makefile; verify the app bundles with `make lint`
- [ ] 1.2 Provision it as its own AGS instance (per-file copy into a dedicated config dir, config-link) and add a launcher bin plus a `SUPER` keybind; verify the keybind opens the window and does not affect the bar (unit test on the provisioning vars + manual launch)
- [ ] 1.3 Ensure the studio is not registered in the bar's `app.tsx` and not autostarted; verify by asserting its absence there in a test

## 2. Generate the key→widget map

- [ ] 2.1 Add the generator `key_widgets.py` that derives key→module from btop source (`btop_theme.cpp` key set; `btop_draw.cpp` attribution incl. `Draw::Graph`/`Meter` gradient args); verify it emits all 48 keys
- [ ] 2.2 Commit the generated artifact and a drift-guard verifier that re-derives and compares; verify the verifier passes on the committed artifact and fails when a module is perturbed (unit test)
- [ ] 2.3 Wire the studio to load the artifact for coverage and "where it shows"; verify a sample key (e.g. `used` → cpu, disks, gpu, mem) matches the artifact in a test

## 3. Component schematic driven by real config

- [ ] 3.1 Parse `shown_boxes` and `presets` from `btop.conf`; verify the parsed preset set matches btop's own `--default-config` output in a test
- [ ] 3.2 Render the labelled schematic (cpu, cpu-detail, gpu, mem, net, disks, proc) with per-element key association; verify selecting a key highlights its components (component test)
- [ ] 3.3 Preset selector re-lays out the box set and names it; verify a preset without `disks` hides that box and the caption lists the shown boxes
- [ ] 3.4 Warn when a selected key paints a module the preset hides; verify the warning text for `available_*` on a disks-less preset
- [ ] 3.5 Preview controls — a load control, fixed fill (0 / 25 / 50 / 100%), and a solid/neutral backdrop toggle; verify each changes the schematic without altering any theme colour (component test)

## 4. Full key editing

- [ ] 4.1 Render the grouped tree of all 48 keys; verify the count is 48 and includes `download_mid`/`upload_mid`
- [ ] 4.2 Palette picker: deduped ramp, `color0`–`color15`, named tokens, and a hex field; verify each sets the selected key (component test)
- [ ] 4.3 Arbitrary colour picker usable regardless of theme kind; verify a colour outside the palette is applied on the generated theme too
- [ ] 4.4 `transparent` (empty value) option; verify the key is written empty and previews as transparent
- [ ] 4.5 Gradient editor (start/mid/end) with "add middle colour" for two-stop gradients; verify `download_mid` becomes set and the three-stop limit is stated
- [ ] 4.6 Edit scope (This key / Same role / All keys) with the blast radius stated; verify "Same role" on `used_start` updates every `*_start` key (component test)
- [ ] 4.7 One-click fixes "Reserve surface for meters" and "Transparent meters"; verify each sets the expected `meter_bg`/used-floor and the preview reflects it

## 5. Diagnosis

- [ ] 5.1 Report meter-contrast defects (`used_start == meter_bg`; `meter_bg` vs background); verify each condition produces its message (unit test)
- [ ] 5.2 Pending edits shown as a diff with nothing written until save, and a revert that discards them; verify the diff is empty after revert (component test)

## 6. Live preview engine

- [ ] 6.1 Run btop on a pty with the candidate theme and reconstruct the frame with a terminal emulator; verify the reconstructed frame matches a known frame (fixture test)
- [ ] 6.2 Warm process + `SIGUSR2` delta capture; verify an edit reflects without restarting btop and renders in under one second on the target host
- [ ] 6.3 Partial-redraw correctness; verify no duplicated/stale rows in a capture after a reload (assert expected token counts)
- [ ] 6.4 Column-accurate rendering with a braille/box-covering monospace font; verify columns stay aligned in a rendered-frame snapshot
- [ ] 6.5 Preview writes only to a throwaway location; verify the installed theme, `current/`, and the repo are unchanged after a preview (test)

## 7. Save targets and provisioning

- [ ] 7.1 Repo | Installed toggle with a read-only resolved destination, reflected in the diff and action; verify each target names its path (component test)
- [ ] 7.2 Provisioning ships authored themes into the spine themes dir and sets the active `color_theme` from a repo setting; verify re-provisioning preserves the selection and `save_config_on_exit = false` (role test)
- [ ] 7.3 Installed target writes to the spine and reloads live; verify the file lands and btop reloads; state the repo-divergence caveat in the UI (component test)
- [ ] 7.4 Active theme selection (★) persisted through the repo-owned setting; verify the chosen theme is what `btop.conf` selects after provisioning (integration test)

## 8. Integration

- [ ] 8.1 End-to-end: create/fork a theme, fix the meter contrast, save to repo, re-provision, and confirm btop shows the fixed theme; verify against the installed theme and the reload path
- [ ] 8.2 Verify the generated theme is offered as a read-only base (fork-only) and that the Installed target warns for it

## Workflow follow-up

- Archive this change (`/openspec-archive` or equivalent) once implementation and the integration checks pass.
