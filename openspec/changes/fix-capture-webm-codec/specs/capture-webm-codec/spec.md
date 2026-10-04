## ADDED Requirements

### Requirement: The WebM container SHALL name a WebM-legal codec

When the requested output format is `webm` and the backend is `gpu-screen-recorder`,
`_build_recording_command` SHALL pass `-k vp9` in addition to `-c webm`.

Rationale, measured on this host: gsr's `-k` defaults to `auto → h264`, but its auto
path is extension-driven and resolves a `.webm` output to **VP8**. WebM carries only
VP8 and VP9. VP8 is absent from several GPUs — the capture tool encodes on the GPU
that owns the captured display, and this host's captured display (`eDP-1`) belongs to
an Intel UHD whose media engine has no VP8 encoder, while its idle RTX 3060 cannot be
redirected (`-encoder` accepts only `gpu|cpu`).

Without `-k`, a WebM request produces **no file** while the launcher has already
reported `{"state": "recording"}`.

#### Scenario: WebM on gpu-screen-recorder names vp9
- **WHEN** `_build_recording_command("gpu-screen-recorder", target, args(format="webm"), "o.webm")` is called
- **THEN** the command contains `-c webm` AND `-k vp9`

#### Scenario: The combination actually produces a file
- **WHEN** `capture-tool start --format webm --duration 3` runs on a host whose encoder supports VP9
- **THEN** the output path reported in the JSON payload exists, and `ffprobe` reports a `matroska,webm` container with a `vp9` video stream

#### Scenario: MP4 is unchanged
- **WHEN** `_build_recording_command` is called with `format="mp4"`
- **THEN** the command contains `-c mp4` and does **NOT** contain `-k` — gsr's h264 auto is correct there

#### Scenario: GIF is unchanged
- **WHEN** `_build_recording_command` is called with `format="gif"`
- **THEN** the command contains `-c mp4` (the GIF intermediate) and does **NOT** contain `-k`, because the guard keys off `args.format`, not the `-c` override

#### Scenario: wf-recorder is unchanged
- **WHEN** `_build_recording_command("wf-recorder", ...)` is called with `format="webm"`
- **THEN** the command contains no `-k`, because wf-recorder's `-f` is an output file argument rather than a container flag and it selects its own encoder

### Requirement: The codec choice SHALL NOT depend on runtime capability probing

The codec SHALL be named unconditionally rather than selected by querying the host's
available encoders. VP9 is a WebM-legal codec on every GPU gsr supports, so a
capability probe would add a subprocess dependency and a hardware matrix for a
decision that has exactly one safe answer.

#### Scenario: No probing is introduced
- **WHEN** the implementation is reviewed
- **THEN** no `vainfo` subprocess, no VA-profile parsing, and no codec-detection branch appears in `_build_recording_command`