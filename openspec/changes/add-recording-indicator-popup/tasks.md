# Tasks: add-recording-indicator-popup

Requires `add-capture-ui-restyle` stories 1–2 (the `capture-tool` icon group + bar group re-point) landed.

- [ ] 1. Restyle the inline cluster in `recording.tsx` + bar `style.css` (pulse dot, tabular timer, ghost buttons, paused-amber); keep the hidden-when-idle contract and the existing hub subscription untouched
- [ ] 2. Add the popup card (anchored window/overlay, big timer, action rows, amber paused frame, `Escape`/outside-click/Stop dismissal) sharing the cluster's state signals
- [ ] 3. Verify: `ags` bar renders all three states per `bar-indicator.html` (recording / paused / idle-hidden); popup and cluster agree on state + time across pause/resume/stop transitions; no new subscriptions or timers introduced
