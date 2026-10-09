# Handoff: audio panel — remaining work

Date: 2026-10-09. Branch `codex/audio-panel-redesign` (worktree
`~/Development/dotfiles-v3-audio-panel`). Master merged in; 29 commits ahead;
**not pushed, no upstream**.

Deploy loop for anything below:

    ./scripts/deploy-audio-panel.sh --with-app --yes     # gates, backup, scoped restart

`make audio-panel-gates` runs every audio gate (unit suites, render, icons,
seek-stability, mock parity, typecheck). `make gates` is the repo-wide set.

---

## 1. NEXT TASK — new play/pause icons for the panel only (owner request)

The owner downloaded art to `~/Downloads/play.svg` and `~/Downloads/pause.svg`,
and wants the panel's per-app play/pause button to use them **with the mock's
round filled container** (`mockups/audio-panel-redesign-concept.html`, the
amber circle around the main transport button).

Explicit constraint: **add as NEW entries through the whole pipeline; do not
modify the existing `media-transport` group.** `previous`/`next`, the bar, and
every other surface must keep the icons they have.

Pipeline, in order:

1. **Templates.** `dotfiles/assets/icon-templates/<group>/<variant>/<name>.svg`.
   Add a NEW group, e.g. `media-transport-panel/default/{play,pause}.svg`.
   Copy the owner's SVGs in; do not overwrite
   `icon-templates/media-transport/default/*`.
2. **Registry.** `dotfiles/config/ags/icons.json` — add a
   `media-transport-panel` group with `variants: [{name, output, template}]`,
   mirroring the `media-transport` shape (`color_mappings: COLOR_FOREGROUND:
   foreground`).
3. **Generate.** The rendered icons are produced from the registry, not copied
   by hand. Find the generator (`make icons-json-drift` reads
   `scripts/icons-json-drift.py`; the renderer is elsewhere — locate it before
   promising anything). Regenerate; confirm the new outputs exist.
4. **Use it in ONE place.** `dotfiles/config/ags/audio/AudioPopup.tsx`, the main
   transport button in `AppRow` — today
   `imagePath={createComputed(() => icon("media-transport", row().playback === "playing" ? "pause" : "play"))}`.
   Point only that call at the new group.
5. **Round container.** The mock's filled circle. Currently the main button is
   distinguished only by `.audio-transport .audio-icon-button:nth-child(2) {
   color: @color_06 }` in `audio-panel.css`. Add the filled round treatment
   there (colour from `@color_*` tokens, as the mock note requires).
6. **Provisioning.** Add the new templates AND the generated outputs to
   `src/provisioning/ansible/roles/compositor_configs/vars/main.yml` and
   `verify/vars/main.yml`, and update the pinning tests
   (`test_compositor_configs_role.py`, `test_verify_role.py`). This is the gap
   that has already bitten twice (see 946f56d4) — an unregistered asset ships a
   missing icon or vanishes on a fresh provision.
7. **Verify.** `make icons-json-drift` green; `make audio-panel-gates` green;
   the panel shows the new glyph; `previous`/`next` and the bar are unchanged.

Consider extending `validation/audio-icons.test.mjs` — it already asserts
icon names the code requests exist. A new group is exactly its subject.

---

## 2. Spec / mock reconciliation (owner: do at the end)

Owner decision 2026-10-07: **preferred output stays; the device-level VOLUME
control is removed.** The panel keeps the selector and `Follow preferred`; each
app owns its level.

Not yet reconciled (owner asked to defer to the end):

- `specs/ags-audio-panel/spec.md` still specifies the device-level output
  control that was removed.
- `mockups/audio-panel-redesign-concept.html` still shows it, and predates the
  actual panel in other small ways.
- `DESIGN.md` / `EXPERIENCE.md` drifted **after** Sally's focused review and were
  never re-reviewed. `validation/README.md` admits this.
- `tasks.md` 1.5 and 7.4 remain open (Chrome/Tidal/Firefox metadata; the Firefox
  blink). 7.4 must not be closed on unit evidence.

Do not merge to master before this: master's spec would describe a panel that
does not exist.

## 3. Recorded-but-unverified

- **Explicit-route reassertion on headphone connect** — fixed in 5b404977 and
  the pinning behaviour was confirmed live, but the full sequence (pin two apps,
  follow on a third, connect headphones) was not re-run after every subsequent
  fix.
- **Startup classification** — design.md says a pre-existing stream is
  `Unknown`; the code now treats a startup target that DIFFERS from the current
  preferred as evidence of a pin. Defensible, but not reconciled with the spec
  text.
- **`appIntents` etc. never took effect in e7f12fd2 / bede9a9f** until 8d6e08b7.
  Anything reasoned from those two commits before it should be re-checked.

## 4. Structural debt (optional; behaviour is pinned)

The session carries five per-app maps — `appIntents`, `appVolumes`,
`appLastIntents`, `appEndpoints`, plus `knownApps` — which together are one
concept (an app registry with streams as transient attachments), discovered one
field at a time. Consolidating them is mechanical now that
`validation/audio-seek-stability.test.mjs` pins the behaviour: run it after each
step and it will catch any drift.

## 5. Test/dev tooling added this session

- `scripts/audio-mock-parity.py` — mock↔code drift, bite-tested
- `scripts/ags-typecheck.py` — typecheck; `ags bundle` does not typecheck, and
  this found five real runtime bugs it missed
- `scripts/deploy-audio-panel.sh` — audio-only deploy, cwd-matched restart
- `validation/audio-panel-render.test.mjs`, `audio-icons.test.mjs`,
  `audio-seek-stability.test.mjs`
- `ags request audio-panel-open` / `audio-panel-debug` — opens the panel and
  dumps the projection plus a rolling per-row trace (this is how the
  seek transients were found; keep it, it is cheap and debug-only)
