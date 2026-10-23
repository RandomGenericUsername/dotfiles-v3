# Proposal: Wi-Fi mock↔code parity harness

## Why

The Wi-Fi redesign already drifted once: mock states existed that the TSX/CSS
never implemented (speed-test chevron, details table, signal-reactive tile).
Every change below cites mock anchors, but citations rot without enforcement.
This change delivers a mechanical gate so drift fails loudly instead of
reaching the owner's screen.

## What Changes

- New `scripts/wifi-mock-parity.py`: extracts `class="…"` tokens from each
  anchored mock state in `wifi-popup-mockup.html`
  (`state-1-connected`, `state-2-stc-expanded`, `state-2b-running`,
  `state-3-off`, `state-4-panel-tile`, `state-5-connecting`,
  `state-6-need-auth`, `bar-testing-card`) and asserts every token exists in
  `dotfiles/config/ags/style.css` or its mapped TSX file(s).
- Mock-only scaffolding classes (page chrome, demo JS hooks) live in an
  explicit allowlist inside the script — anything not allowlisted must exist
  in shipped code.
- A per-state→TSX map inside the script documents which component implements
  which mock state (serves as the living contract table).

## Non-goals

- No visual changes, no TSX/CSS changes (those belong to changes 1–9).
- No Ansible wiring (manual gate + documented in each change's tasks; promote
  to a provision gate only as a follow-up).
- Reverse check (code classes ⊆ mock) is intentionally out — one direction
  keeps the gate shippable.

## Mock anchors

Meta-change: covers all anchors listed above. No mock edits required
(the anchor index block at the top of the file is its input).
