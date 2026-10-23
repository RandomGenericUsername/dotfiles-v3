## Context

`DeviceCard` (`AudioPopup.tsx:646`) receives `volume`/`muteRaw` accessors from
`state.ts:118-129`. Those computeds only re-run on `wp.nodes` membership; they
never see `notify::volume`/`notify::mute` on the resolved node. The bar
(`bar/widgets/audio.tsx:69-81,123-127`) and `StreamRow`
(`AudioPopup.tsx:572-580`) already fixed the same trap with
`useEndpointEpoch` + direct GObject reads. `DeviceCard` imports
`useEndpointEpoch` but never calls it.

## Goals / Non-Goals

**Goals**

- Input/Output card glyphs, badges, and level dim follow live endpoint
  mute/volume with zero latency vs the bar.
- All existing click targets keep toggling exactly their current node.
- Recording rows stay per-stream only (user-locked).

**Non-Goals**

- See proposal. Forbidden surface list is in tasks.md §F and is absolute.

## Decisions

### D1. Pattern: epoch + direct GObject read (locked)

Copy `OutputIndicator`. Inside `DeviceCard`:

```ts
const epoch = useEndpointEpoch(endpoint)
const level = createComputed(() => {
  epoch()
  return clampVolume(nodeOf(endpoint())?.volume ?? 0)
})
const muted = createComputed(() => {
  epoch()
  return nodeOf(endpoint())?.mute === true
})
```

Downstream (`glyphVariant`, `micIcon`, badge, `LevelLine`, `toggleMute`)
unchanged. Keep `volume`/`muteRaw` params on the signature so call sites
`:1079-1093` do not move (prefix unused params only if lint requires).

Rejected: reading `defaultSpeakerVolume()` inside epoch (T11 — inner computed
stays stale); polling `wpctl`/`pw-dump`; rewriting shared accessors.

### D2. Semantics map (user-confirmed, do not reinterpret)

| Surface | Follows | Click |
|---|---|---|
| Bar `MicIndicator` | default mic mute | open popup only |
| Bar `OutputIndicator` | default speaker mute+level | open / pavucontrol / scroll |
| Panel Input card | default mic mute | toggle default mic |
| Panel Output card | default speaker mute+level | toggle default speaker |
| Panel Recording rows | that stream's mute ONLY | toggle that stream |
| Panel Applications rows | that app's stream | toggle that app |

Recording rows MUST NOT OR with default-mic mute. Chrome rows showing
`mic-on` while the source is muted is correct.

### D3. Scope is one function

Only `DeviceCard` body changes. `RecorderRow` is audit-only: leave
`createBinding(stream, …)` unless manual verify proves same-node mute freeze
(and if so, add epoch on that stream — still no default-mic OR).

### D4. Anti-drift harness

Executor must satisfy tasks.md §F grep-forbidden list and §V verify script
before claiming done. Spec scenarios in
`specs/audio-popup-icon-liveness/spec.md` are the acceptance contract.
