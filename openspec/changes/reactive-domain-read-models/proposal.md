# reactive-domain-read-models

## Why

The bar re-architecture's deepest lesson (doc 100 §5.3, doc 101 §13 step 2) is
that a widget is only as reactive as the adapter behind its read model. The
descriptor prototype already learned this for **network**: reading the Astal
device through `createBinding(network, "wifi")` fires on hotplug but not on the
device's own `strength`/`state`/`enabled` changes, so the glyph froze.
`domains/network/read-model.ts` fixes that by owning the subscription and
republishing a plain reading.

That fix exists for **one** domain. The other three still read their runtime
directly:

- **battery** binds AstalBattery inside the widget (`bar/widgets/battery.tsx`);
- **bluetooth** reads the service's module-scope accessors inside the widget
  (`bar/widgets/bluetooth.tsx` reads `bluetoothPowered`);
- **audio** projects the composition root's binding inside the widget
  (`bar/widgets/audio.tsx` projects `binding.model()`).

Spine **AD-2** (injected context, no module globals) requires app-level domain
services to be injectable and closed over at registration, never carried in
`BarContext`; **AD-3** (code owns meaning; the state key is the boundary)
requires each domain to publish an inert reading that a pure mapping turns into
a state key. Today only network satisfies both.

Evidence: `domains/network/read-model.ts:71` (`createNetworkReadModel`, the
seed); `bar/widgets/battery.tsx:35-40` (`Battery.get_default()` + `createBinding`);
`bar/widgets/bluetooth.tsx:4,37` (`bluetoothPowered()` read inline);
`bar/widgets/audio.tsx:5,63` (`projectBarIndicators(binding.model())` inline).
Verify: `grep -n "createNetworkReadModel" dotfiles/config/ags/domains/network/read-model.ts; grep -n "Battery.get_default\|createBinding(device" dotfiles/config/ags/bar/widgets/battery.tsx; grep -n "bluetoothPowered" dotfiles/config/ags/bar/widgets/bluetooth.tsx; grep -n "binding.model()" dotfiles/config/ags/bar/widgets/audio.tsx`.

## What Changes

### One injectable reactive port (AD-2)

- New pure module `domains/reactive.ts`: the `ReadAccessor<T>` /
  `Setter<T>` / `ReactiveRuntime` ports. A read model takes its reactive
  primitive as a parameter instead of importing `ags` at module scope, which is
  what makes it drivable by a fake in `make ags-test` (no desktop stack).
- New adapter `domains/astal.ts`: `agsRuntime`, the gnim/AGS binding of that
  port (`createState`). This is the only place a read model's reactivity comes
  from the framework.

### Four read models: pure core + injectable Astal adapter

Each domain gets a **pure** `read-model.ts` (structural service interface,
`snapshot`, and `create<Domain>ReadModel(service, runtime): ReadAccessor`) and
an **adapter** `astal.ts` (imports `gi://Astal*`, closes over the injected
service and `agsRuntime`, and returns the reactive accessor):

- `domains/network/` — moves the seed off its `gi://`/`ags` imports; the widget
  keeps its existing consumer and now imports the Astal adapter.
- `domains/battery/` — AstalBattery → a reactive `BatteryReading`.
- `domains/bluetooth/` — the existing `services/bluetooth-service.ts` accessors
  → a reactive `BluetoothReading`.
- `domains/audio/` — the existing hexagon's `AudioPanelViewModel` → a reactive
  `AudioReading` (the bar-indicator projection). The hexagon is **not**
  rewritten; the read model wraps `audio/composition.ts`'s binding.

### Tests (fake device, no live Astal)

- New pure unit tests under `tests/ts/` drive each read model with a **fake
  device/source** and a **fake runtime**, proving it is injectable and reactive:
  an initial snapshot is published, and a device/source change republishes.

## Out of scope

- **No widget migration.** The hand-rolled widgets are not rewritten onto the
  read models — that is REQ-008. This change extracts the read models and wires
  the one existing consumer (`bar/widgets/network-descriptor.tsx`).
- **No audio-hexagon rewrite.** The hexagon's domain/ports/adapters are reused
  as-is; the read model is a new consumption surface, not a replacement.
- **No bluetooth-service rewrite.** Its D-Bus/BlueZ logic is untouched; only its
  public accessors are wrapped.
- **No platform extraction and no `BarContext` change.** `BarContext` is not
  extended with these services (AD-2); the platform move is AD-20.

## Impact

- New: `domains/reactive.ts`, `domains/astal.ts`,
  `domains/{network,battery,bluetooth,audio}/{read-model.ts,astal.ts}`,
  `tests/ts/{network,battery,bluetooth,audio}-read-model.test.ts`,
  `tests/ts/fixtures/reactive-fixture.ts`.
- Edited: `domains/network/read-model.ts` (now pure),
  `bar/widgets/network-descriptor.tsx` (imports the Astal adapter),
  `tests/tsconfig.tests.json` (the new pure modules join the purity list).
- No behavior change on a provisioned host: the network descriptor resolves the
  same reading through the same subscription.
