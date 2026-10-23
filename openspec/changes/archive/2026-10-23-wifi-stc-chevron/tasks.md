# Tasks: collapsible Speed Test Settings section

- [x] 1. Add `stcExpanded` + chevron row; gate the config box visibility.
- [ ] 2. Provision + restart AGS; click chevron open/closed twice; confirm no layout shift of siblings.
- [ ] 3. Parity gate green; screenshot collapsed vs `state-1-connected`, expanded vs `state-2-stc-expanded`.

Verification: with Wi-Fi off, neither chevron nor section renders; with a
password prompt open, the section hides (existing `wifiPromptVisible` gate
preserved).
