## Why

Selecting WebM in the recording view produces **no file at all**, while the launcher's own return value says the recording started:

```json
{"audio": "none", "backend": "gpu-screen-recorder", "duration": 3.0,
 "format": "webm", "output_path": ".../recording_...webm", "state": "recording"}
```

Owner-reported from live use of the provisioned build. Reproduced end to end on this machine.

## Root cause

`_build_recording_command` passes the container to gsr's `-c` and never passes a codec:

```python
command.extend([
    "-c", args.format if not gif else "mp4",   # container
    ...                                          # no -k
])
```

gsr's `-k` defaults to **auto → h264**, but its auto path is extension-driven, and for `.webm` it selects **VP8**:

```
gsr info: using vp8 encoder because a codec was not specified and the file extension is .webm
gsr error: your gpu does not support 'vp8' video codec.
```

WebM's only valid codecs are VP8 and VP9. This machine's captured display is `eDP-1`, owned by the **Intel UHD Alder Lake-P GT1**, whose media engine has no VP8 encoder. Measured on this host:

| codec | container | result |
|---|---|---|
| h264 | mp4 | works |
| **vp8** | webm | **fails — encoder absent** |
| **vp9** | webm | **works** (2.8 MB produced) |

The RTX 3060 does not help here. gsr encodes on the GPU that owns the captured display — verified from its own log, `the monitor "eDP-1" is connected to /dev/dri/card1, capturing and encoding on that gpu` — and every NVIDIA connector (`DP-3`, `eDP-2`, `HDMI-A-1`) is disconnected. `-encoder` accepts only `gpu|cpu`, so there is no way to redirect encoding to the idle dGPU.

**This is pre-existing, not a regression.** `bin/capture-tool` is byte-identical between `master` and the refactor branch, and the deployed pre-refactor CLI produces no WebM either. WebM has never worked on this host. (Same class of bug as `GSR_QUALITY_MAP`: a preset assumed to pass through that the backend actually rejects.)

## What Changes

- **`-k vp9` is passed for the `webm` container** on the `gpu-screen-recorder` branch. MP4 is untouched (h264 auto is correct and works), GIF is untouched (it records to an mp4 intermediate), and the `wf-recorder` branch is untouched (its `-c` is a file argument, not a container/codec pair).
- A regression test pinning the codec per container, in the style of the existing `test_gsr_quality_presets_map_to_valid_gsr_flags`.

## Non-goals

- Not probing the encoder's real capabilities and auto-selecting the best available codec. That would need `vainfo` output parsing and a hardware matrix; VP9 is a WebM-legal codec on every GPU gsr supports, so naming it unconditionally is correct and testable.
- Not changing what happens on a machine where VP8 *is* available. `-k vp9` is valid everywhere; it costs nothing and removes a hardware-dependent failure mode.
- Not touching the GUI. `--format webm` was always emitted correctly.

## Impact

- `src/gui-tools/capture-tool/bin/capture-tool` — one conditional in `_build_recording_command`.
- Tests — one new case in `TestCommandConstruction`.
- **This is an intentional behaviour change** and is deliberately kept out of `refactor-capture-tool-hexagonal`, whose spec requires that refactor to change no observable behaviour.