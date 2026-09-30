# Tasks: wire auto-run + Run button, parse real ookla JSON

- [ ] 1. Diagnose the auto-run snap-back per `design.md`; record the proven layer here.
- [x] 2. Implement the ookla mapping + typed failure + `ranAt`; delete the section's Last-result row.
- [ ] 3. Fix the proven snap-back layer (persist / echo / guard).
- [ ] 4. Provision + restart AGS; live Run test vs manual CLI; auto-run persistence across view close/reopen.
- [ ] 5. Parity gate green; screenshot vs `state-2-stc-expanded`.

Verification: `grep -n "as SpeedTestResult" speedtest-service.ts` returns
nothing (no blind casts remain); CLI failures and missing commands are
surfaced in the speed-test section.
