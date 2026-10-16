# btop Theme Studio

A launch-on-demand AGS/GTK4 authoring tool for btop themes (OpenSpec change
`add-btop-theme-studio`). It makes btop's two systemic colour defects visible
(`meter_bg` and `used_start` resolving to the same mid-luminance palette stop)
and lets a user create, fork, tune, preview, and deploy themes.

## Layout

| path | role |
|---|---|
| `app.tsx` | AGS entry point — its own instance, one centered window |
| `ui/StudioWindow.tsx` | the window: schematic, key tree, picker, diagnosis, diff, save targets, live view |
| `lib/` | pure, I/O-free logic (unit-tested with plain `node`) |
| `lib/key_widgets.json` | the canonical generated key→widget map (drift-checked) |
| `lib/key-widgets.generated.ts` | the importable form of the same artifact |
| `tools/key_widgets.py` | the generator + drift-guard verifier |
| `tools/btop_*.cpp` | vendored btop v1.4.7 sources the generator parses (Apache-2.0) |
| `live/btop_live.py` | the live preview engine (real btop on a pty + `pyte`) |
| `tests/` | pure-logic tests (`node`) |
| `live/tests/` | live-engine tests (`uv run --with pyte pytest`) |

## Gates

```sh
make lint        # ags bundle (compile-only)
make test        # pure logic + generated-artifact tests
make verify      # re-derive the key→widget map from source (drift guard)
make test-live   # real btop on a pty (fixture, SIGUSR2, side-effect-free)
```

## Key decisions

- **The key→widget map is generated from btop source** (`btop_theme.cpp` key
  set; `btop_draw.cpp` attribution), committed, and re-derived by a drift guard.
  The studio never hand-traces "where does this key show?".
- **The schematic consumes btop's real config** (`shown_boxes` + `presets`) and
  never invents box geometry.
- **The preview is the real btop binary.** The live engine runs
  `btop --no-tty --force-utf` on a pty, keeps one warm process, reloads it with
  `SIGUSR2` per edit, and reconstructs the frame with `pyte`. It writes only to
  a throwaway temp root.

### Live-view integration (design Open Question)

The shipped AGS app **reuses the pty + terminal-emulator engine**
(`live/btop_live.py`) for the Live view rather than embedding a VTE widget. The
design explicitly permits either (behaviorally identical per the
`btop-live-preview` spec); reusing the engine keeps the one preview
implementation that has fixture, `SIGUSR2`-delta, and side-effect-free tests.
The app's "Refresh live preview" button writes the effective theme to a temp
file and runs the engine against it.

## Vendored sources

`tools/btop_draw.v1.4.7.cpp` and `tools/btop_theme.cpp` are vendored from btop
v1.4.7 (Apache-2.0) solely so the generator is reproducible and drift-checked.
They are not compiled. Refresh them deliberately when pinning a new btop
version, then regenerate the artifact with `make verify` (and `--ts`).
