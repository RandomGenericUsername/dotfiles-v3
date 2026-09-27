# Tasks: restyle the power switch to the mock

- [x] 1. Rewrite `.settings-switch` family in `style.css` per `design.md` (track/knob/checked/insensitive).
- [ ] 2. Provision + restart AGS; screenshot popup header ON vs `state-1-connected`, OFF vs `state-3-off`, auto-run row vs `state-2-stc-expanded`.
- [ ] 3. Toggle regression: click ON/OFF from popup + settings view, one NM Set each, no oscillation.
- [ ] 4. Parity gate green.

Verification: `grep -n "settings-switch" style.css` shows complete
track + knob + checked + insensitive rules; zero TSX diff in this change
(`git status` must show only `style.css` + mock if tweaked).
