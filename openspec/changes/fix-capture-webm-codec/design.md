# Design: fix-capture-webm-codec

## The gsr flag vocabulary

From `gpu-screen-recorder --help` on this host (v6.1.3), three flags matter and they are
easy to conflate:

```
[-c <container_format>]                      # container: mp4, mkv, webm
[-k h264|hevc|av1|vp8|vp9|hevc_hdr|...]      # codec
[-encoder gpu|cpu]                           # hardware vs software, NOT a device
```

`-c webm` is therefore **correct and not the bug**. The bug is the absent `-k`.

`-k` defaults to `auto → h264` (man page). "Auto" is extension-driven: a `.webm`
output resolves to **vp8**, which is what the tool hit. H.264 cannot be muxed into
WebM and VP8 is not universally available, so relying on the guess is wrong on its
own terms — even on a GPU with VP8 it silently differs from the mp4 path.

`GSR_QUALITY_MAP` is the direct precedent: the tool already learned that a
user-facing preset must be translated into gsr's vocabulary rather than passed
through, because "an unmapped preset once broke recording." The codec is the same
class of assumption, one layer over.

## The change

```python
        command.extend([
            "-c", args.format if not gif else "mp4",
            "-f", str(args.fps),
            "-q", GSR_QUALITY_MAP.get(args.quality, "high"),
            "-fallback-cpu-encoding", "yes",
            ...
        ])
        # gsr's `-k` defaults to auto -> h264, but its auto path is
        # extension-driven and resolves `.webm` to VP8. WebM carries only VP8/VP9,
        # and VP8 is absent from several GPUs (verified: this host's captured
        # display is the Intel UHD, which has no VP8 encoder), so the guess turns
        # a WebM request into a silent no-file failure. VP9 is WebM-legal
        # everywhere gsr runs, so name it rather than infer it.
        if args.format == "webm":
            command.extend(["-k", "vp9"])
```

Placement matters: appended after the main block so the `-c`/`-f`/`-q` group stays
contiguous and readable, and so the conditional sits next to the rationale.

### Why unconditional, not capability-probed

Probing would mean shelling `vainfo`, parsing VA profile lists, and maintaining a
hardware matrix — for a decision that has exactly one safe answer. VP9 is a valid
WebM codec on every GPU gsr supports, so naming it unconditionally is both simpler
and removes a hardware-dependent failure mode rather than relocating it.

The counter-argument (a strong GPU could do VP8 faster) does not apply: the only
observable difference is encode performance, and correctness beats a theoretical
speed edge on a format the tool otherwise cannot produce at all.

### Scope boundaries

| path | touched | why |
|---|---|---|
| gsr + `mp4` | no | h264 auto is correct and verified working |
| gsr + `gif` | no | records an mp4 intermediate; `args.format` is already overridden to `mp4` for `-c`, so `args.format == "webm"` is False |
| gsr + `webm` | **yes** | the fix |
| wf-recorder, any format | no | `-f` there is an output *file*, not a container flag; wf chooses its own encoder |

The `gif` case is worth stating explicitly because `gif` and `webm` are siblings in
the format vocabulary: the guard keys off `args.format`, which is `"gif"` for the
GIF path, so the `-c mp4` override is untouched.

## Verification

- Unit: a new case in `TestCommandConstruction` pinning `-k vp9` for webm, and
  asserting mp4/gif/wf are unchanged.
- Live: `capture-tool start --format webm` must produce a file `ffprobe` reports as
  `matroska,webm` with a `vp9` video stream.
- Regression: the full capture suite stays green.

## Risk

Low and bounded. One conditional on one backend branch. The failure mode if the
`-k` value were ever wrong would be loud — gsr exits non-zero with an explicit
codec error — rather than the current silent no-file.