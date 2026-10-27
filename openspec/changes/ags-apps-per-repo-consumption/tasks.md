# Tasks: Consume AGS apps as independently pinned repos

## 1. Composition data

- [x] 1.1 Add `dotfiles/provisioning/apps.yaml` with all seven entries as `owner: legacy` and the full deployment metadata; verify the file validates against the contracts app-list schema.
- [x] 1.2 Add `dotfiles/provisioning/program-tuple.yaml` with the three program tags; verify the file validates against the contracts tuple schema.
- [x] 1.3 Add the schema-validation fixture (legacy, mixed and all-standalone lists) and verify each fixture produces exactly one owner per app.

## 2. Consumption gates

- [x] 2.1 Extend `deploy-coverage` to read the list/tuple and assert one owner, install dir, config/spine/XDG/bin links, launcher, autostart and bar palette pointer; verify a broken fixture fails and the real data passes.
- [ ] 2.2 Mirror the same assertions in the pinned engine's verify role (provision REQ-008); verify both gates agree on the fixture.
- [ ] 2.3 Add the quiesce → flip → install/start → verify/rollback fixture; verify it reports zero duplicate and zero missing surfaces.

## 3. Documentation and cutover

- [x] 3.1 Update `docs/WORKSPACE.md`, the provisioning shape docs and the app-consumption notes; verify every link/path resolves and the docs name the one-owner rule.
- [x] 3.2 Record the per-app cutover checklist and the prerequisite ticket links; verify the checklist names quiesce, owner flip, installation/start, identity and rollback.
- [ ] 3.3 Add the final closeout task: remove the `ags-apps` pin/role, archive the repo, and verify no legacy/duplicate surface remains.

## 4. Integration

- [x] 4.1 Run `make deploy-coverage` and `make gates-ci`; verify both pass on the real topology and the broken fixtures fail as expected.
- [ ] 4.2 Run a no-op reconcile and a changed-appearance reconcile; verify no consumer refresh/restart on the no-op and the declared mode on the change.
