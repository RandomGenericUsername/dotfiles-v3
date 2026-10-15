import GLib from "gi://GLib?version=2.0"
import { createComputed, createEffect, createState } from "ags"
import { Gtk } from "ags/gtk4"
import { registry } from "../../lib/icon-registry"
import { domainEvents } from "../../lib/event-bus"
import { preferences } from "../../lib/preferences"
import type { BarContext, RichWidgetSpec } from "../../kit/widget"

type RecordingState = "idle" | "recording" | "paused"

function formatElapsed(seconds: number): string {
  const minutes = Math.floor(seconds / 60).toString().padStart(2, "0")
  const remainder = (seconds % 60).toString().padStart(2, "0")
  return `${minutes}:${remainder}`
}

function iconPath(variant: "pause" | "play" | "stop"): string {
  return registry.resolve("capture-tool", variant) ?? ""
}

/**
 * Bar feedback mode, from the capture tool's `bar_compact_controls` setting.
 *
 * compact (`true`) — the bar shows only the dot + elapsed time and the popup
 * carries pause/resume/stop (no timer there: the bar already shows it).
 * full (`false`, default) — the bar carries the buttons itself and no popup
 * opens, so nothing is duplicated.
 *
 * Read through the `Preferences` port (spine AD-12): the adapter owns the config
 * file AND its `FileMonitor`, so the bar is a separate AGS instance from the
 * capture tool without reading the file itself or holding a monitor. A missing
 * or corrupt file degrades to the `false` fallback.
 */

/**
 * The recording indicator, as a `RichWidgetSpec` (spine AD-8; doc 101 §5): a
 * dot + elapsed timer + buttons, so it is the rich shape. The shared shell owns
 * the root box (`rec-cluster`), its paused state class and its visibility; the
 * content is the cluster's children.
 *
 * The factory sets up the state and the hub subscription once per bar (the same
 * lifetime the old component had). It is driven by the hub's `capture.state`
 * domain event (AD-5): no polling. Between pushes the elapsed value is
 * interpolated locally from the recorded sync time — a rendered continuous
 * value, not a state read. `domainEvents.subscribe` hydrates
 * subscribe-before-read, so a bar that starts mid-recording renders immediately;
 * a hub restart resets the indicator before re-hydration. Control actions go
 * through the injected `ctx.hub.control` capability (AD-8); when the hub is
 * absent nothing is published (reduced functionality).
 */
export function createRecordingWidget(): RichWidgetSpec<RecordingState> {
  const [state, setState] = createState<RecordingState>("idle")
  const [elapsed, setElapsed] = createState("00:00")
  // The port owns the config file + monitor (AD-12); the widget only reads.
  const compact = preferences.get("capture-tool", "bar_compact_controls", false)
  let jobId: string | null = null
  let baseElapsed = 0
  let syncedAtMs = Date.now()
  // Gtk.Popover dismissal (Escape / outside-click) is native; Stop and hub
  // restarts pop it down explicitly below.
  let popup: Gtk.Popover | null = null

  // The settings view writes the capture config; the port updates the accessor
  // when the file changes. Leaving compact mode removes the click affordance, so
  // close any popup — the behaviour the old in-widget monitor callback owned.
  createEffect(() => {
    if (!compact()) popup?.popdown()
  })

  function reset(): void {
    jobId = null
    baseElapsed = 0
    syncedAtMs = Date.now()
    setState("idle")
    setElapsed("00:00")
    popup?.popdown()
  }

  domainEvents.subscribe("capture.state", (_topic, payload) => {
    const next = payload.state
    const validState: RecordingState =
      next === "recording" || next === "paused" ? next : "idle"
    baseElapsed = Number(payload.elapsed_seconds) || 0
    syncedAtMs = Date.now()
    jobId = typeof payload.job_id === "string" ? payload.job_id : null
    setState(validState)
    setElapsed(formatElapsed(baseElapsed))
  })

  // A hub restart (new epoch) invalidates the old capture job: clear the
  // stale indicator, then the bus re-hydrates `capture.state` and re-renders
  // it if a capture is still live.
  domainEvents.onRestart(reset)

  GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1000, () => {
    if (state() === "recording") {
      const interpolated = baseElapsed + Math.floor((Date.now() - syncedAtMs) / 1000)
      setElapsed(formatElapsed(interpolated))
    }
    return true
  })

  function send(ctx: BarContext, action: "pause" | "resume" | "stop"): void {
    if (jobId !== null) ctx.hub.control(jobId, action)
    if (action === "stop") popup?.popdown()
  }

  function toggle(ctx: BarContext): void {
    send(ctx, state() === "recording" ? "pause" : "resume")
  }

  // Derived bindings off the single `state` signal — the popup mirrors the
  // cluster with no second subscription and no new timer.
  const dotClass = state((value) => (value === "paused" ? "rec-dot paused" : "rec-dot"))
  const popupClass = state((value) => (value === "paused" ? "rec-popup paused" : "rec-popup"))
  const statusText = state((value) => (value === "paused" ? "Recording paused" : "Recording"))
  const toggleLabel = state((value) => (value === "recording" ? "Pause" : "Resume"))
  const toggleTip = state((value) =>
    value === "recording" ? "Pause recording" : "Resume recording",
  )
  // The port's accessor is the pure `ReadAccessor` (callable with no argument),
  // not gnim's selector-callable `Accessor`; derive the full-mode flag from it.
  const fullMode = createComputed(() => !compact())

  return {
    id: "recording",
    read: () => state(),
    visible: (value) => value !== "idle",
    class: "rec-cluster",
    stateClass: (value) => (value === "paused" ? "paused" : null),
    content: (_value, ctx) => (
      <>
        <button
          class="rec-status"
          // gnim maps a JSX prop's accessor branch as `Accessor<NonNullable<T>>`,
          // which strips `null` even though the property itself (`tooltipText`)
          // is `string | null` and the raw branch accepts null. A reactive tooltip
          // that is legitimately ABSENT in full mode is therefore not expressible
          // as a prop. The GObject setter takes `string | null`, so it is driven
          // directly instead of casting away the null.
          $={(self) => {
            createEffect(() =>
              self.set_tooltip_text(compact() ? "Recording controls" : null),
            )
          }}
          onClicked={() => {
            // Only the compact mode has a popup: in full mode the controls are
            // already in the bar, so opening one would just duplicate them.
            if (compact()) popup?.popup()
          }}
        >
          <box spacing={6}>
            <box class={dotClass} valign={Gtk.Align.CENTER} />
            <label class="rec-timer" label={elapsed} />
          </box>
        </button>
        <button
          visible={fullMode}
          class="rec-btn"
          tooltipText={toggleTip}
          onClicked={() => toggle(ctx)}
        >
          <image
            pixel_size={16}
            $={(self) => {
              createEffect(() => {
                self.set_from_file(iconPath(state() === "recording" ? "pause" : "play"))
              })
            }}
          />
        </button>
        <button
          visible={fullMode}
          class="rec-btn stop"
          tooltipText="Stop recording"
          onClicked={() => send(ctx, "stop")}
        >
          <image pixel_size={16} $={(self) => self.set_from_file(iconPath("stop"))} />
        </button>
        <popover $={(self) => (popup = self)}>
          <box orientation={1} class={popupClass}>
            <box class="rec-popup-row" spacing={8}>
              <box class={dotClass} valign={Gtk.Align.CENTER} />
              <label label={statusText} />
            </box>
            {/* No big timer: the bar already shows the elapsed time in compact
                mode, which is the only mode that opens this popup. */}
            <box class="rec-popup-actions" homogeneous spacing={8}>
              <button class="rec-popup-action" tooltipText={toggleTip} onClicked={() => toggle(ctx)}>
                <box spacing={7}>
                  <image
                    pixel_size={16}
                    $={(self) => {
                      createEffect(() => {
                        self.set_from_file(iconPath(state() === "recording" ? "pause" : "play"))
                      })
                    }}
                  />
                  <label label={toggleLabel} />
                </box>
              </button>
              <button
                class="rec-popup-action danger"
                tooltipText="Stop recording"
                onClicked={() => send(ctx, "stop")}
              >
                <box spacing={7}>
                  <image pixel_size={16} $={(self) => self.set_from_file(iconPath("stop"))} />
                  <label label="Stop" />
                </box>
              </button>
            </box>
          </box>
        </popover>
      </>
    ),
  }
}
