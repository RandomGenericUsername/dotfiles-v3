# Tasks

## 1. Plan (commit 1)

- [x] 1.1 Author the change: `proposal.md`, this `tasks.md`, and
  `specs/ags-event-client/spec.md` with ADDED Requirements + Scenarios citing
  AD-4/AD-5 and doc 101 §4.2/§13 step 4.
  Verify: `openspec validate one-event-client --type change` → valid.
  - `openspec validate one-event-client --type change` →
    `Change 'one-event-client' is valid`.

## 2. The platform seam (AD-5, AD-4)

- [ ] 2.1 Move the pure state machine to `platform/event-client.ts`: contract
  literals, `asUint`/`isNewer`/`parseTopicState`, the injected
  `EventBusTransport`, and `DomainEventBusCore` with subscribe-before-read
  hydration, `(epoch, seq)` dedup, `JobsCleared(epoch)` reset, and `(0, 0)` =
  "no state yet". No `gi://`, no `ags`.
  Verify: `grep -nE "^import .*(gi://|\"ags\")" dotfiles/config/ags/platform/event-client.ts` → no matches.
- [ ] 2.2 Expose `EventSource` (subscribe/onRestart return unsubscribe handles)
  and `EventHub` (`select<T>(topic): ReadAccessor<M[T] | null>` built on an
  injected reactive runtime; first-class `control(jobId, action)`).
  Verify: `grep -n "subscribe(topic: string, handler: TopicHandler): () => void\|select<T extends keyof EventMap>\|interface EventHub" dotfiles/config/ags/platform/event-client.ts`.
- [ ] 2.3 Delete the moved `lib/event-bus-core.ts`.
  Verify: `test ! -e dotfiles/config/ags/lib/event-bus-core.ts` → exit 0.

## 3. The bar consumes the single client (no behaviour change)

- [ ] 3.1 Repoint `lib/event-bus.ts` at `../platform/event-client` and construct
  the one `domainEvents` client with the injected `agsRuntime`.
  Verify: `grep -n "platform/event-client\|agsRuntime" dotfiles/config/ags/lib/event-bus.ts`.
- [ ] 3.2 Keep `bar/widgets/recording.tsx` on `subscribe`/`onRestart`/`control`
  (no `select` migration) so the rendered indicator is unchanged.
  Verify: `grep -n "domainEvents.subscribe\|domainEvents.onRestart\|domainEvents.control" dotfiles/config/ags/bar/widgets/recording.tsx`.

## 4. Tests prove the mandatory contract (pure, no GTK)

- [ ] 4.1 Add `tests/ts/event-client.test.ts` with a scripted fake transport:
  subscribe-before-read hydration order; `(epoch, seq)` dedup (equal/lower
  dropped, epoch bump wins); unsubscribe; and a restart reset (`JobsCleared`
  resets the `select` accessor to `null` and re-hydrates).
  Verify: `make ags-test` → `fail 0` and the new suite passes.
- [ ] 4.2 Register `../platform/event-client.ts` in
  `tests/tsconfig.tests.json`'s explicit purity list.
  Verify: `make ags-test` → `OK: 0 type errors in the ags pure-module unit tests`.
- [ ] 4.3 Repoint the executed contract gate
  (`src/gui-tools/icon-color-mapping-editor/tests/event-contract-drift.mjs`) at
  the new module path.
  Verify: `node src/gui-tools/icon-color-mapping-editor/tests/event-contract-drift.mjs` → `event-contract drift + bar hydration agree`.

## 5. Deploy registration (hard constraint)

- [ ] 5.1 Register `platform/event-client.ts` in
  `compositor_configs_skeleton_files` and drop the moved `lib/event-bus-core.ts`;
  mirror both in the verify role.
  Verify: `make deploy-coverage` → `PASS`.
- [ ] 5.2 Update the two provisioning structural tests that pin the skeleton
  list (`test_compositor_configs_role.py`, `test_verify_role.py`).
  Verify: `uv run --directory src/provisioning pytest tests/unit/test_compositor_configs_role.py tests/unit/test_verify_role.py` → pass.

## 6. Verify

- [ ] 6.1 All gates green: `make ags-test` (fail 0, 0 type errors),
  `make ags-typecheck` (PASS), `make bar-typecheck` (OK), `make gates-ci`
  (exit 0), `make deploy-coverage` (PASS).
- [ ] 6.2 The change validates and the tree is clean.
  Verify: `openspec validate one-event-client --type change` → valid;
  `git status --porcelain` → empty after the implementation commit.
