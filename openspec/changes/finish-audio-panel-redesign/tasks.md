# Tasks

## 0. Anti-drift preamble (read before editing)

- **Files in scope.** `openspec/changes/*`, the audio UX workspace under
  `_bmad-output/planning-artifacts/ux-designs/ux-dotfiles-repo-v3-audio-2026-09-18/`,
  `dotfiles/assets/icon-templates/**`, `dotfiles/config/ags/icons.json`,
  `dotfiles/config/ags/audio/{AudioPopup.tsx,audio-panel.css}`, and the
  provisioning manifests plus their pinning tests. A step that needs another
  file must STOP and report first.
- **Invariant.** The existing `media-transport` group is not modified. If a step
  appears to require it, that step is wrong.
- **Verify by execution.** Each task names its gate. Do not mark a task complete
  from reading the diff.

## 1. Reconcile the spec

- [ ] 1.1 Amend the `ags-audio-panel` capability: remove the device-level output
  level/mute requirement; state that the panel writes app-scoped levels only,
  and that the preferred-output selector remains and governs follow-default
  routing. Add a scenario for "the panel exposes no device-level level control".
  `openspec validate finish-audio-panel-redesign` (or the repo's ad-hoc
  equivalent) and reread the delta against the implemented panel.
- [ ] 1.2 Confirm the `Unknown` route intent, I1–I3, and app-level intent
  requirements still read true against the merged implementation. Record any
  further drift found rather than fixing it silently inside this task.

## 2. Reconcile the mock and the UX spines

- [ ] 2.1 Update `mockups/audio-panel-redesign-concept.html`: drop the
  device-level volume/mute line from the preferred-output section, keep the
  selector and `Follow preferred`. Re-render and eyeball it against the running
  panel; they should now describe the same surface.
- [ ] 2.2 Update `DESIGN.md` / `EXPERIENCE.md` to match, and state plainly that
  they postdate Sally's focused review and were re-reviewed on <date> by
  <who>. Do not leave the "postdates review" caveat in `validation/README.md`
  stale.
- [ ] 2.3 The approved mock and the implemented panel must agree on the
  preferred-output section BEFORE the icons land, so that the icon change is
  judged against a reference that is itself current.

## 3. Add the panel's transport icons

- [ ] 3.1 Add templates as a NEW group:
  `dotfiles/assets/icon-templates/media-transport-panel/default/{play,pause}.svg`,
  from the owner's art (`~/Downloads/{play,pause}.svg`). Do not touch
  `media-transport/`. Verify:
  `git status --porcelain dotfiles/assets/icon-templates/media-transport/` is
  empty.
- [ ] 3.2 Add a `media-transport-panel` group to `dotfiles/config/ags/icons.json`
  with both variants (`name`, `output`, `template`), mirroring the
  `media-transport` shape and its `color_mappings`.
- [ ] 3.3 Generate the rendered icons through the source pipeline. Locate the
  generator first (it is not `icons-json-drift.py`); do not hand-copy outputs.
  Verify: `make icons-json-drift` passes and the new outputs exist.
- [ ] 3.4 Point the panel's main transport button — and only it — at the new
  group: `AudioPopup.tsx`, the play/pause `IconButton` in `AppRow`. Verify:
  `grep -n 'media-transport' dotfiles/config/ags/audio/AudioPopup.tsx` shows the
  new group exactly once and the old one still used for previous/next.
- [ ] 3.5 Add the mock's round filled container in `audio-panel.css`
  (`.audio-transport .audio-icon-button:nth-child(2)`), using `@color_*` tokens.
  Verify the panel renders it and no other transport button gains it.
- [ ] 3.6 Extend `validation/audio-icons.test.mjs` so the new group's names are
  covered by the existing "requested icon must exist" assertion.
- [ ] 3.7 Provisioning: add the new templates AND the generated outputs to
  `compositor_configs/vars/main.yml` and `verify/vars/main.yml`, and update
  `test_compositor_configs_role.py` (exact file list) and `test_verify_role.py`.
  Verify: the compositor role tests pass, and a parse of the manifests shows
  every new source exists and every dest parent is declared.

## 4. Verify

- [ ] 4.1 `make audio-panel-gates` green (unit suites, render, icons,
  seek-stability, mock parity, typecheck).
- [ ] 4.2 `make gates-ci` green.
- [ ] 4.3 Deploy with `./scripts/deploy-audio-panel.sh` and LOOK at the panel:
  the new play/pause with its round container, `previous`/`next` unchanged, the
  bar unchanged, no device-level volume control, preferred-output selector and
  `Follow preferred` intact.
- [ ] 4.4 Confirm on a fresh provision path that the new assets are deployed
  (the manifest entries are the point, not the working tree).
