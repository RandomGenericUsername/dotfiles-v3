# repoint-runtime-to-generated-contract

## Why

The event contract is now canonical in the `contracts` repo (spine **AD-6**) with generated bindings (`generated/contract.py`, `contract.ts`, `events.schema.json`) and a symmetric gate. The Python runtime still **hand-embeds** the wire tables and per-topic validation schemas, which drift — the `wallpaper.state` `stage`/`reload_failures` keys were already missing from the contract while the runtime's embedded schema carried them.

Evidence: `contracts` `dbdc5b8` (`generated/contract.py`, `generated/events.schema.json`); spine AD-6; runtime `src/runtime/src/runtime/adapters/dbus_event_bus.py` (`METHODS`/`SIGNALS`), `adapters/emit_validation.py` (`TOPIC_SCHEMAS`), `domain/hub.py` (`KNOWN_TOPICS`).
Verify: `grep -n "org.dotfiles.Events1" src/runtime/src/runtime/adapters/dbus_event_bus.py` → the hand-embedded literal.

## What Changes

- **Vendor** the generated `contract.py` + `contract.ts` into dotfiles-v3 at a pinned `contracts` commit.
- **Repoint** the Python runtime to the vendored bindings: wire tables (`dbus_event_bus`), bus name (`bus_name_owner`), topic allowlist (`hub`), validation schemas (`emit_validation`), and `bar_subscriber`.
- **Add the cross-repo drift gate** the contracts gate left as `TODO(REQ-004)`: assert the vendored copies match `contracts/generated/`.
- **Remove** the dead `speedtest.finished` literal in hypr-pano (re-scoped from REQ-005).

## Non-goals

- **Not** repointing the app-local TS readers (bar, hypr-pano, icme, wallpaper-selector, notifications): those are replaced by the platform's one event client (AD-5) — deferred to the platform migration.
- **Not** the platform extraction (AD-20).

## Impact

- `src/runtime/src/runtime/{adapters,domain,ports}/**`, the vendored bindings, provisioning file pins + their unit tests.
- `src/gui-tools/hypr-pano/lib/event-bus-core.ts` (dead literal).
- `Makefile` / CI (the cross-repo gate).
