# Validation: spec, mock, UX spines, and icon group

Date: 2026-10-09. Change: `finish-audio-panel-redesign`.

## 1.1 — the `ags-audio-panel` delta validates (ad-hoc equivalent)

No `openspec` executable is installed in this environment (`openspec` is not on
PATH; the npm package ships no binary), so the repo's ad-hoc equivalent was run
against the delta and its base (the redesign change's capability, which has not
been promoted to `openspec/specs/`). It asserts:

- the delta has `MODIFIED` and `ADDED` sections;
- a `MODIFIED` requirement is either a name present in the base or documents a
  rename with `*Changed from:*` — the delta's
  `App stream level is the only level the panel sets` renames the base
  `Device output level is separate from app stream level`;
- an `ADDED` requirement does not already exist in the base — the panel's own
  `media-transport-panel` icon group is new;
- every scenario carries `GIVEN`/`WHEN`/`THEN`.

Result: **PASS** (5 scenarios). The delta matches the implemented panel: the
preferred-output section in `AudioPopup.tsx` renders the `DeviceSelector` only,
with no device-level level or mute control (`PreferredOutput`, the block comment
at `AudioPopup.tsx:273`).

## 1.2 — the untouched requirements still read true; drift recorded

`Unknown` route intent, the invariant set (I1–I3, now expressed as the
capability's "event-driven authority" and "hexagonal boundaries" requirements),
and the app-level intent requirements still read true against the merged
implementation. Further drift found and **recorded, not silently fixed**:

- **Owner-decision date.** The block comment in
  `dotfiles/config/ags/audio/AudioPopup.tsx` says the device-level line was
  removed by owner decision **2026-10-04**; the spec, design, proposal and
  handoff all say **2026-10-07**. Left as-is (a comment fix is not part of this
  change).
- **Startup classification.** `redesign-ags-audio-panel/design.md` says a stream
  already present when the adapter starts is `Unknown`; the code treats a
  startup target that *differs* from the current preferred as evidence of a pin
  (see `HANDOFF-audio-panel-followups.md` §3). The finish delta's wording
  ("already active when the adapter starts … SHALL be `Unknown` unless
  authoritative evidence restores its intent") can hold if that observed target
  counts as authoritative evidence — but the two texts are not reconciled.
- **Open redesign tasks.** `redesign-ags-audio-panel/tasks.md` 1.5 (Chrome/
  Tidal/Firefox metadata) and 7.4 (the Firefox blink) remain open; 7.4 must not
  be closed on unit evidence. Out of scope here, recorded.
- **Superseded base text.** The redesign base still carries the old
  `Device output level is separate from app stream level` requirement until this
  change is archived/promoted. Expected; the delta supersedes it.

## Deviations from the literal task text (anti-drift preamble)

Two steps named a file that does not hold the thing they described. Reported
here rather than guessed at:

- **Task 3.2 named `dotfiles/config/ags/icons.json`.** That file is *generated
  output*, checked by `make icons-json-drift` (`icons.json ==
  to_nice_json(icons.yaml)`). Editing it directly would fail the drift gate and
  be reverted at the next provision. The group was added to its source,
  `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml`, and
  `icons.json` regenerated through the pipeline
  (`icons-json-drift.py --update`). Gate green.
- **Task 3.7 named `compositor_configs/vars/main.yml` and
  `test_compositor_configs_role.py` for the new templates and generated
  outputs.** Icon templates deploy via the `assets` role's directory sync
  (`dotfiles/provisioning/assets.yaml`, `icon-templates/`), not a per-file list
  in `compositor_configs`; that role owns `dotfiles/config/**` files and has no
  icon-template surface. The applicable provisioning surfaces were updated
  instead, in `verify/vars/main.yml` and `test_verify_role.py`:
  - `verify_asset_dirs` gains `icon-templates/media-transport-panel` (assert the
    new group's template tree deployed, mirroring the `capture-tool` precedent);
  - `verify_icons_samples` gains `media-transport-panel-play.svg` and
    `media-transport-panel-pause.svg` (prove the group actually rendered);
  - `test_verify_role.py` tracks both exactly (the exact-list assertion and the
    runtime fixture that is "the machine").
  `test_compositor_configs_role.py`'s exact list is unchanged because no file
  under `dotfiles/config/ags/` moved or was added for this change.

## Play/pause template decision (owner instruction)

Owner instruction (2026-10-09): use the supplied SVG whole and replace its
hardcoded colors with `{{COLOR_*}}` placeholders, as every other template does.
Therefore the round container is carried by the art, not re-drawn by CSS:

- `media-transport-panel/default/{play,pause}.svg` keep the circle and glyph,
  with `#D9D9D9` → `{{COLOR_BACKGROUND}}` and `black` → `{{COLOR_FOREGROUND}}`;
- the group maps `COLOR_BACKGROUND: color6` (the GUI-unification primary-action
  token, `@color_06`, the concept mock's round container) and
  `COLOR_FOREGROUND: background` (the dark on-action ink the glyph sits on).

The existing `.audio-transport .audio-icon-button:nth-child(2)` rule stays as
the round-button treatment (`@color_06`, 50% radius) and now coincides with the
art's container, so no second, differently-colored circle appears. This
supersedes design.md §2's "the container is styling, not art" mechanism while
honoring its intent: the container color comes from a runtime token, never a
mock literal.

## CI gates parity follow-up (owner-approved, outside this change's scope)

`make gates-ci` (task 4.2) surfaced a pre-existing `ci-gates-parity` failure,
reproduced on a clean tree. The parity model requires one CI job per `gates-ci`
target, but the workflow had an aggregate `audio-tests` job (which silently
omitted `audio-icons-test` and `audio-seek-stability-test`) and a self-hosted
`ags-typecheck` job the model had no way to express. Fixed rather than silenced:

- `.github/workflows/gates.yml`: the aggregate `audio-tests` job became seven
  per-target jobs (`audio-core-test`, `audio-presentation-test`,
  `pipewire-adapter-test`, `audio-session-runtime-test`,
  `audio-panel-render-test`, `audio-icons-test`, `audio-seek-stability-test`),
  each running its `make` target — matching the header's stated "one job per
  gate" layout and closing the two-gate coverage gap.
- `scripts/ci-gates-parity.py`: a new declared table `CI_SELF_HOSTED_GATES`
  records `ags-typecheck` as a gate excluded from the stock-runner `gates-ci`
  set that still runs on a `[self-hosted, linux]` CI job. The check now accepts
  an excluded gate declared in either `CI_EXCLUDED_GATES` (no job) or
  `CI_SELF_HOSTED_GATES` (has a job), and validates the self-hosted entry for
  staleness and collisions.

`make gates-ci` is green.
