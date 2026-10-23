# Design: Wi-Fi mock↔code parity harness

## Approach

A single dependency-free Python script (`scripts/wifi-mock-parity.py`,
stdlib only: `html.parser` + `re`). No new packages, no build step.

## Script behavior

1. Parse `wifi-popup-mockup.html`, split by the stable anchor ids:
   `state-1-connected`, `state-2-stc-expanded`, `state-2b-running`,
   `state-3-off`, `state-4-panel-tile`, `state-5-connecting`,
   `state-6-need-auth`, `bar-testing-card`. Fail if any anchor is missing
   (anchors are load-bearing for every later change).
2. Collect `class="…"` tokens per state (including classes added by the
   mock's demo `<script>`, e.g. `running` on the run button).
3. For each token, assert presence in `dotfiles/config/ags/style.css`
   (as a selector) or in one of the state's mapped TSX files (as a
   `class=` literal), per the map below. Tokens in the scaffolding
   allowlist skip the check.
4. Exit non-zero listing every uncovered token with its state.

## State→TSX map (also embedded in the script)

| Mock state | TSX owner(s) |
|---|---|
| `state-1-connected` | `components/wifi/WifiContent.tsx` (details, rows), `components/wifi/WifiPopup.tsx` (header) |
| `state-2-stc-expanded` | `components/wifi/WifiContent.tsx` (speed-test section) |
| `state-2b-running` | `components/wifi/WifiContent.tsx` (run button), `bar/widgets/network.tsx` (card class) |
| `state-3-off` | `components/wifi/WifiContent.tsx` (empty state) |
| `state-4-panel-tile` | `settings-panel/controls/wifi.tsx` |
| `state-5-connecting` | `components/wifi/WifiContent.tsx` (`WifiRow` busy branch) |
| `state-6-need-auth` | `components/wifi/WifiContent.tsx` (`WifiPasswordPrompt`) |
| `bar-testing-card` | `bar/widgets/network.tsx`, `style.css` |

## Scaffolding allowlist (initial; mock-only, never shipped)

Page chrome (`anchor-index`, `bottom-bar`, `state-label`, `mock-popup`,
`mock-header`, …), demo hooks (`ms-entry`, `ms-hint`, `chip`, `eye-btn`,
`pwd-wrap`, `bar-demo`, `bar-icon`, `bar-caption`, …). Demo-interactive
classes that WILL ship (`running`, spinner usage) stay checked.

## Verification

- `python3 scripts/wifi-mock-parity.py` exits 0 on the current tree
  (after allowlisting; any genuinely missing class is a bug filed against
  its owning change, not silenced here).
- Delete a shipped class from `style.css` → script fails naming state+token.
- Remove an anchor id from the mock → script fails loudly.
