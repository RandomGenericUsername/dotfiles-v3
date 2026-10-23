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

---

## 6. Merging this branch into master (runbook)

Status at handoff: **NOT merged.** A dry-run merge (`git merge --no-commit
--no-ff codex/audio-panel-redesign` in the main worktree) reported exactly three
conflicts and was aborted cleanly:

    Makefile
    dotfiles/config/ags/app.tsx
    dotfiles/config/ags/audio/AudioPopup.tsx

`.github/workflows/gates.yml`, `audio/state.ts` and
`provisioning/tests/unit/test_verify_role.py` AUTO-MERGED. The auto-merge of
`state.ts` is the quiet risk: master edited the 1600-line monolith and so did
this branch, and the tooling combined them without review. `AudioPopup.tsx`
still imports four bindings from it (`close`, `popupVisible`, `audioIconX`,
`levelVariant`), so a wrong auto-merge breaks the panel subtly. Inspect it
before trusting it.

Because master had moved ~20 commits ahead, the merge is NOT a fast-forward.

### Steps

    # 0. preconditions
    cd ~/Development/dotfiles-v3-audio-panel && git status --porcelain   # clean
    make audio-panel-gates                                             # green
    git push -u origin codex/audio-panel-redesign                      # needs SSH: see §7

    # 1. merge in the MAIN worktree (master lives there)
    cd ~/Development/dotfiles-v3
    git status --porcelain                       # clean; other agents paused
    git fetch origin
    git merge --no-ff codex/audio-panel-redesign

    # 2. resolve the three conflicts
    #    app.tsx        keep BOTH: master's Battery/Bluetooth popups AND this
    #                   branch's `const audio = audioPanelBinding()` +
    #                   AudioPopup(primary, audio)
    #    Makefile       take master's structure as the base; re-append the audio
    #                   targets; rejoin GATES/.PHONY; keep ags-typecheck in the
    #                   gates-ci filter-out list
    #    AudioPopup.tsx this branch's redesign should win, but DIFF against
    #                   master first -- master may have changed it for a reason
    #                   that must not be dropped

    # 3. INSPECT THE AUTO-MERGE before trusting it
    git diff --stat HEAD -- dotfiles/config/ags/audio/state.ts
    #    then verify what AudioPopup imports still exists and behaves:
    #      close, popupVisible, audioIconX, levelVariant

    # 4. verify
    make audio-panel-gates
    make gates-ci                                # the set CI actually runs

    # 5. commit the merge, then push master
    git commit
    git push origin master

### Do not skip

- Do NOT resolve `AudioPopup.tsx` with `--theirs` without a diff.
- Do NOT merge while another agent has uncommitted work on master.
- Deploy and LOOK at the panel after merging; `make audio-panel-gates` is
  static and the merge touches the file it reads most.

## 7. Push (SSH)

`git push` failed in the session that wrote this with:

    git@github.com: Permission denied (publickey)
    ssh-add: Could not open a connection to your authentication agent

The key exists (`~/.ssh/personal.pub`) but no agent was running. Fix:

    eval "$(ssh-agent -s)"
    ssh-add ~/.ssh/personal
    ssh -T git@github.com
