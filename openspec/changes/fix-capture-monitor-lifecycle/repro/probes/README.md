# Probes

One-shot measurement scripts. Each is copied over `capture-tool/app.tsx` and run
with `ags run -d <tool>`; each writes a log under `/tmp/opencode/`. They are
probes, not tests — they print facts and exit.

| probe | answers | log |
|---|---|---|
| `gtk4-api-probe.tsx` | Which signals `Gdk.Display` actually has (there is no `monitor-added`/`monitor-removed`); what `get_monitors()` returns and whether it is stable; whether GTK4 can name the focused monitor at all (it cannot). | `/tmp/opencode/probe-gtk4-api.log` |
| `launcher-interception-probe.tsx` | Whether `get_window`'s resolved window ever moves; whether `App.toggle_window` is interceptable (no — AGS binds it in its constructor); whether `App.get_window` is (yes — it is called through `this` at call time). **Needs an external `ags toggle capture-window -i capture-probe-launch` while it runs.** | `/tmp/opencode/probe-launcher.log` |
| `real-hotplug-probe.tsx` | Whether the real topology adapter's subscription actually fires on real hotplug. **Run `hyprctl output create headless` / `hyprctl output remove HEADLESS-N` while it runs.** | `/tmp/opencode/probe-real-hotplug.log` |
| `connector-timing-probe.tsx` | Whether a newly appeared monitor's `connector` is populated at the instant `items-changed` fires. It is **not** — it lands ~200 ms later via `notify::connector`, which is why `domain/monitor-registry.ts#isIdentified` refuses to address a monitor until it can. **Run `hyprctl output create headless` while it runs.** | `/tmp/opencode/probe-connector-timing.log` |

## A note on `launcher-interception-probe.tsx`

It deliberately installs overrides on **both** `App.prototype.toggle_window` and
`app.toggle_window`, then expects three external `ags toggle` calls to log **zero**
hits while still toggling a window. That asymmetry is the whole point: it is the
measured proof that the D-Bus path holds a bound copy of the prototype method and
that `toggle_window` is therefore not a seam, while the `get_window` override in
the same run *is* reached.