## Design

### 1. Spec vs implementation: the device-level control

Owner decision 2026-10-07, taken after living with the panel: the preferred-output
**selector** stays, the device-level **volume/mute** line goes. The selector
governs a real system behaviour — WirePlumber's `follow-default-target` moves
streams following the default whenever the default changes — and removing it
only hid that behaviour while it kept happening. The volume line read as a
second, competing control beside each app's own level.

Sink gain remains reachable from the Settings panel, which keeps one
implementation of that use case rather than two that can drift.

The spec delta therefore removes the device-level requirement and states that
app-scoped levels are the only levels the panel writes. `Unknown` route intent
and invariants I1–I3 are untouched: they were never about the level control.

### 2. The play/pause icon

Constraint from the owner: **new entries through the whole pipeline, used in one
place.** The existing `media-transport` group is not modified, so
`previous`/`next`, the bar and every other surface are unaffected by construction
rather than by care.

A new group (`media-transport-panel`) gets its own templates and its own
registry variants. The panel's main transport button — and only that call site —
reads from it.

The round container is styling, not art: the mock's filled circle comes from
`.audio-transport .audio-icon-button:nth-child(2)` in `audio-panel.css`, using
`@color_*` tokens. The mock's own note requires runtime tokens, never the mock's
illustrative literals.

This is the failure mode `audio-icons.test.mjs` already exists to catch: an icon
name the code requests that does not exist resolves to nothing and the widget
silently keeps its previous glyph. Extend that gate to the new group.

### 3. The mock and the UX spines

The mock is the owner-approved reference, and `DESIGN.md`/`EXPERIENCE.md` were
edited **after** Sally's focused review — `validation/README.md` says so
outright. Reconciling them is a design act, not a formatting one, so it needs a
reviewer's eye: the token recipe (`@color_*`), the removed device-level control,
and whatever else the implemented panel settled differently.

Until this lands, master's spec and mock describe a panel that does not exist.
That is the reason this change exists rather than a footnote.

## Risks

- **The icon pipeline has several surfaces.** Templates, `icons.json`,
  generation, provisioning manifests AND the tests that pin them. The 6.4 gap in
  this redesign (`946f56d4`) was exactly an unregistered file, and an
  unregistered icon template ships a missing glyph or vanishes on a fresh
  provision. Every surface is a task below, with its gate.
- **`make icons-json-drift` must stay green.** The registry and the generated
  output are checked against each other.
