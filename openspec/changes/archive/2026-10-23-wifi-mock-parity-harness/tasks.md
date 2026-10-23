# Tasks: Wi-Fi mock↔code parity harness

- [x] 1. Write `scripts/wifi-mock-parity.py` per `design.md` (stdlib only).
- [ ] 2. Run it against the current tree; triage every failure as either
  scaffolding (allowlist with a one-line reason) or a real gap (file as a
  note on the owning change 1–9 — do NOT fix code here).
- [ ] 3. Negative tests: remove one anchor id → red; remove one shipped
  selector from a scratch copy → red with state+token named. Restore after.
- [ ] 4. Gate green: script exits 0; commit script + this change.
- [ ] 5. Document the gate in each of changes 1–9 verification sections
  (already written — confirm wording matches the final script CLI).

Verification: `python3 scripts/wifi-mock-parity.py` → exit 0. Human step:
open `wifi-popup-mockup.html` next to this tasks file and confirm every
anchor listed in `design.md` renders.
