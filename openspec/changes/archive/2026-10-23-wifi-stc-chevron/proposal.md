# Proposal: collapsible Speed Test Settings section

## Why

The speed-test block is always rendered, occupying space even for users who
never touch it. The mock specifies a collapsed `Speed Test Settings…`
chevron row that expands in place (`state-1-connected` → `state-2-stc-expanded`).

## What Changes

- `components/wifi/WifiContent.tsx`: new `stcExpanded` state (default
  collapsed); replace the always-visible `settings-speedtest-config` box
  with a `Speed Test Settings…` chevron row (reusing the existing
  `settings-chevron-row` pattern from Other Networks) that expands the
  section. Collapsed state shows nothing but the chevron row — zero space
  waste.
- The section content itself is owned by changes 6–7; this change only adds
  the collapse shell (chevron + visibility). Section internals may be
  placeholder-identical to current code.

## Non-goals

- No interval/auto-run/run-button logic changes.
- No CSS beyond the chevron row reuse (already exists).

## Mock anchors

- `state-1-connected` (collapsed chevron row)
- `state-2-stc-expanded` (expanded content)
