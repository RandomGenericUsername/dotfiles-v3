# Tasks: speed-test run feedback via events + animated bar card

- [x] 1. Record the contract-shaped finished event and shared in-process running-state decision in `design.md`; publish result from `speedtest-service.ts`.
- [x] 2. Implement loader-button swap in `WifiContent.tsx`.
- [x] 3. Drive `.speedtesting` from the shared running accessor and animate the card in `network.tsx` + `style.css`.
- [ ] 4. Provision + restart AGS; live run: loader, pulsing card, clean finish, spam-click immunity.
- [ ] 5. Parity gate green; mid-run screenshots vs `state-2b-running` + `bar-testing-card`.

Verification: hub payload logged once per run (no duplicates); bar card
never appears when idle; icon file resolves identically before/during/after
(prove art untouched via `registry.resolve` log or icon-path diff).
