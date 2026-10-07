# Reproduction / measurement harness — fix-capture-monitor-lifecycle

**Not a CI test.** Everything here needs a live AGS session. It is committed so
the claims in `../proposal.md` and `../design.md` are re-runnable rather than
asserted, and so the next person does not have to re-derive that
`Gdk.Display` has no `monitor-added` signal.

## The capability that changes what is verifiable

This host has **one physical monitor** and **no input injection** (no
`ydotool`/`wtype`/`xdotool`). That reads like "hotplug cannot be exercised" —
and the earlier version of this harness assumed so, synthesising the monitor
list. It is wrong:

```sh
hyprctl output create headless     # a genuine second monitor
hyprctl output remove HEADLESS-1  # and it goes away
```

Hyprland creates real virtual outputs and delivers real `wl_output` global /
release events, which GDK turns into real `Gdk.Monitor` ListModel
`items-changed` notifications. So **both** gaps are verifiable end-to-end here,
with real `Astal.Window`s, the real App singleton, the real launcher, and the
real adapters. `real-hotplug.sh` and `launcher-focus.sh` are the end-to-end
proofs; everything else is the fine-grained evidence.

One limitation remains: `hyprctl dispatch focusmonitor` cannot focus a headless
output (it has no input device), so focus is always `eDP-1` in these runs. The
defect is still fully demonstrable, because with the pre-change build the
launcher reaches the *last-added* window while focus is on `eDP-1` — see the
`old` vs `new` transcripts in `../design.md` §2.6.

## Run order

Each script takes a copy of the tool directory and overwrites `app.tsx`, so run
them one at a time and let each clean up after itself (they all `trap` a cleanup
that removes the virtual outputs they create).

```sh
cd <repo>
T=src/gui-tools/capture-tool
R=openspec/changes/fix-capture-monitor-lifecycle/repro

# 0. the two END-TO-END proofs
$R/real-hotplug.sh $T                       # window count tracks monitor count
$R/launcher-focus.sh $T $T/app.tsx new      # panel opens on the FOCUSED monitor
git show HEAD:$T/app.tsx > /tmp/app-OLD.tsx
$R/launcher-focus.sh $T /tmp/app-OLD.tsx old   # ...and does not, before the change

# 1. the harness: 8 scripted steps, synthesised monitor list, real windows
mkdir -p /tmp/opencode/run && cp -r $T /tmp/opencode/run/ags-capture
cp $R/monitor-lifecycle-harness.tsx /tmp/opencode/run/ags-capture/app.tsx
XDG_STATE_HOME=/tmp/opencode/run/state XDG_CONFIG_HOME=/tmp/opencode/run/config \
  ags run -d /tmp/opencode/run/ags-capture      # logs to /tmp/opencode/monitor-lifecycle-harness.log

# 2. the probes, one at a time, each copied over app.tsx
$R/probes/README.md                            # what each one answers
```

## What each file answers

| file | question |
|---|---|
| `real-hotplug.sh` | Does one window exist per monitor through a real add / remove / re-add cycle? |
| `launcher-focus.sh` | Does `ags toggle capture-window` open the **focused** monitor's window? Run it against the pre-change `app.tsx` to see the defect. |
| `monitor-lifecycle-harness.tsx` | The 8-step lifecycle against real `Astal.Window`s, with the monitor **list** synthesised (so both monitors can be present on a one-monitor host). |
| `probes/gtk4-api-probe.tsx` | Which signals does `Gdk.Display` actually have? Can GTK name the focused monitor? |
| `probes/launcher-interception-probe.tsx` | Does `get_window`'s target ever move? Is `toggle_window` interceptable? Is `get_window`? |
| `probes/real-hotplug-probe.tsx` | Does the real adapter's subscription actually fire on real hotplug? |
| `probes/connector-timing-probe.tsx` | Is a new monitor's connector populated when `items-changed` fires? (It is not — this is why `isIdentified` exists.) |
| `pixel-parity.sh` | Visual equivalence, with a control run. **Superseded — see below.** |

## Why `pixel-parity.sh` is superseded

It is kept because the attempt is instructive, but do not trust its verdict.
It screenshots the panel and compares, which is unsound here: the panel is a
translucent layer-shell surface over live desktop content, so a whole-screen
brightness mean is dominated by whatever is behind it. Measured, same script,
same panel: **0.644** for the pre-change build's `eDP-1` against **0.054** for
the post-change build's — a 12× "difference" that is entirely the desktop
content having changed between runs. Even a mean-of-differences drowns in the
browser animating behind the panel.

`launcher-focus.sh` replaced it because `hyprctl layers` reports every layer
surface with its **output** and its **namespace**, and `ClassicWindow` sets
`namespace="capture"` on the panel. "Which monitor is the panel on" is then a
direct read with no dependence on what is behind it — which is why the
end-to-end result below is trustworthy and the pixel numbers are not.

For the record, the visual claim needs no pixel evidence: this change touches
no CSS, no CSS class, no `style.css` selector, and no window shell. Check 6 of
`scripts/capture-hexagonal-gate.py` is the mechanical form of that, and it stays
at **33 used / 28 styled**.

## What this host could not verify

Stated plainly, because these are real gaps in the evidence:

- **Focus on a virtual output.** `hyprctl dispatch focusmonitor HEADLESS-N` is
  a no-op — a headless output has no input device. Every run therefore has
  focus on `eDP-1`. The defect and the fix are both fully demonstrated (old →
  `HEADLESS-17`, new → `eDP-1`, both while focus is `eDP-1`), but the
  complementary direction — focus on the second monitor → panel opens there — is
  argued from the `orderedForFocus` unit tests and the harness's STEP 3/STEP 6
  rather than from a real compositor focus change.
- **Click paths.** No `ydotool`/`wtype`/`xdotool`, so no button was pressed. The
  panel's own interactions are untouched by this change and are covered by the
  existing suites.
- **Real hardware hotplug.** Virtual outputs are real compositor events but not
  real connectors. A physical unplug additionally fires
  `Gdk.Monitor::invalidate`, which a virtual output's removal does not, so the
  dual-hook idempotence is argued from the `items-changed` runs plus the
  unit tests rather than from an unplug.
- **`btop` behind the panel.** `btop` needs a TTY this shell cannot provide, so
  the specific translucency interaction named in the brief was never reproduced.
  It is moot for the reasons above, but it is not something I can claim to have
  checked.