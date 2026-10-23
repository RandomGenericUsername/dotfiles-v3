# Design: collapsible Speed Test Settings section

## Implementation (`WifiContent.tsx`)

- `const [stcExpanded, setStcExpanded] = createState(false)` next to
  `otherExpanded`.
- Chevron row (mirror the Other Networks button exactly: same classes,
  `▸`/`▾` label swap):
  `Speed Test Settings…` + arrow, `onClicked={() => setStcExpanded(!stcExpanded())}`.
- Gate the existing `settings-speedtest-config` box:
  `visible={createComputed(() => wifiEnabled() && !wifiPromptVisible() && stcExpanded())}`.
- Keep the box's position in the layout (between Other Networks and the
  Wi-Fi Settings footer) so expand/collapse doesn't reorder siblings.

## Contract table

| Mock element | Code owner |
|---|---|
| Collapsed chevron (`state-1-connected`) | new chevron row, `settings-chevron-row` reuse |
| Expanded section (`state-2-stc-expanded`) | gated `settings-speedtest-config` box |

## Verification

- Parity gate → 0. Live: collapsed by default; click expands in place;
  state survives list refreshes (state lives outside the scan effect).
