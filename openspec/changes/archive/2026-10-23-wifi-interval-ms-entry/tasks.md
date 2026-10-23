# Tasks: interval as ms entry + config migration

- [x] 1. Confirm the floor with the owner (assumed: 1000 ms, `0` = Off); record the answer here.
  CONFIRMED 2026-09-26: owner approved proceeding with 1000 ms (`MIN_INTERVAL_MS`), `0`/empty = Off.
- [x] 2. Implement entry + hint + caption + chips in `WifiContent.tsx` + CSS.
- [x] 3. Migrate `SpeedTestConfig` → `interval_ms`, scheduler math, `loadConfig` legacy upgrade, skeleton JSON.
- [ ] 4. Provision + restart AGS; exercise: junk→revert, 500→1000, chip→exact, legacy-file→migrated.
- [ ] 5. Parity gate green; screenshot vs `state-2-stc-expanded` (entry showing `900000` + `15 min`).

Verification: scheduler uses the committed value, never the draft
(change entry text without committing → no reschedule); auto-run switch
and Run button untouched by this change.
