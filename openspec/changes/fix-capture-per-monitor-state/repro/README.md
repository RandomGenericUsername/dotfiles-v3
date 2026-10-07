# Reproduction harness — two windows, one state file

Evidence for `fix-capture-per-monitor-state`, kept verbatim. **Not** a CI test: it
needs a live AGS session, so committing it under `tests/` would be a lie. It is here so
the claim in `proposal.md` is re-runnable rather than asserted.

## What it does

`app.tsx` builds one `ClassicWindow` per monitor. This host has one monitor
(`hyprctl monitors` lists only `eDP-1`), so the two-window instance is constructed
programmatically instead: the harness builds two `Astal.Window`s against the **real**
`glibUiStateStore` and the real `ClassicWindow` (only the `launcher` and
`backendProbe` ports are stubbed, so the state file on disk is genuinely written by the
adapter under test). It then scripts the sequence and prints what each save wrote.

| file | tree it reproduces |
|---|---|
| `two-window-harness.tsx` | the FIXED tree — one `createUiState()`, passed to both windows |
| `two-window-harness-PREFIX.tsx` | the PRE-FIX tree — `ClassicWindow(monitor, ports)`, each window allocating its own state |

## Run it

```sh
mkdir -p /tmp/opencode/repro && cd /tmp/opencode/repro
cp -r <repo>/src/gui-tools/capture-tool ags-capture
cp <repo>/dotfiles/.../ags-capture/icons.json ags-capture/     # or ~/.config/ags-capture/icons.json
cp <this dir>/two-window-harness.tsx ags-capture/app.tsx        # or ...-PREFIX.tsx
mkdir -p state
XDG_STATE_HOME=$PWD/state XDG_CONFIG_HOME=$PWD/config ags run -d $PWD/ags-capture
```

## Expected

Pre-fix, the persisted `target` flips with whichever window captures, and each capture
discards the other window's explicit choice:

```
STEP 3: A picks Screen, captures  -> file target: "screen"
STEP 5: B picks Window, captures  -> file target: "window"   (A's "screen" destroyed)
STEP 7: A captures                -> argv  --target screen  (B's "window" destroyed)
```

Post-fix, step 7 emits `--target window` — the shared state's current value — and the
file does not move.
