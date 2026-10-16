# btop-theme-studio — prototype

Working proof-of-concept behind `../proposal.md`, `../design.md`, and `../specs/`.
Not production code — it de-risks the change and is the reference behavior for the
`btop-live-preview` engine.

## Run the studio (mock + live helper)

```sh
# from this directory
uv run --with pyte python3 studio_server.py 8799
# then open http://localhost:8799/   (mock.html is served at /)
```

The page has two tabs: **Components** (the labelled schematic, instant) and
**Live** (the real btop binary on a pty, ~0.8 s per edit).

## Regenerate the mock from its template

```sh
python3 make_v8.py      # _v5_template.html + key_widgets.json -> btop-theme-studio-v8.html
cp btop-theme-studio-v8.html ../mock.html
```

## Regenerate the key -> widget map (and check drift)

```sh
python3 key_widgets.py btop_draw.v1.4.7.cpp btop_theme.cpp key_widgets.json
python3 key_widgets.py btop_draw.v1.4.7.cpp btop_theme.cpp key_widgets.json --verify
```

## Files

| file | role |
|---|---|
| `_v5_template.html` | the editor template (schematic + picker + gradient editor + save target) |
| `make_v8.py` | builds the served studio (`_v5_template.html` + config + key→widget map) |
| `build_v6.py` | builds the components-only variant |
| `key_widgets.py` / `key_widgets.json` | generator + generated key→module artifact |
| `btop_live.py` | live preview engine (pty + warm process + `SIGUSR2` delta, `pyte`) |
| `studio_server.py` | serves the studio and the `/state`, `/edit` endpoints |
| `capture_btop.py` | one-shot real-btop frame capture |
| `live_editor.html` | earlier minimal live-only page |
| `btop_draw.v1.4.7.cpp`, `btop_theme.cpp` | vendored btop sources (Apache-2.0) used by the generator |
