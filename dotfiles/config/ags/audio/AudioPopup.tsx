import { Astal, Gtk, Gdk } from "ags/gtk4"
import GLib from "gi://GLib?version=2.0"
import { Accessor, createBinding, createComputed, createEffect, createState, For, onCleanup } from "ags"
import { registry } from "../lib/icon-registry"
import { NavHeader, PanelCard } from "../settings-panel/primitives"
import {
  nextPlayer,
  playPausePlayer,
  previousPlayer,
  resyncMpris,
  seekPlayer,
  type MprisPlayer,
} from "../services/mpris-service"
import { formatClock, interpolatePosition } from "../services/mpris-core"
import {
  activeSection,
  applicationRows,
  appRowKey,
  audioIconX,
  back,
  clampVolume,
  close,
  defaultMicrophone,
  defaultMicrophoneMute,
  defaultMicrophoneVolume,
  defaultSpeaker,
  defaultSpeakerMute,
  defaultSpeakerVolume,
  displayMuteForApp,
  displayVolumeForApp,
  effectiveSinkNameForApp,
  hasLiveStreamForApp,
  inputDevices,
  levelVariant,
  liveStreamForApp,
  masterPlayer,
  nodeLabel,
  outputDevices,
  playbackStreams,
  playerForApp,
  popupVisible,
  recordingStreams,
  refreshStreamTargets,
  routeAppTo,
  setAppVolume,
  setDefaultMicrophone,
  setDefaultSpeaker,
  showInputDevices,
  showOutputDevices,
  streamAppIconPath,
  streamAppIconPathForIdentity,
  streamAppName,
  streamMediaName,
  toggleAppMute,
  useEndpointEpoch,
  viewEpoch,
  type AppRow,
} from "./state"

/**
 * The audio popup (add-pipewire-audio-control).
 *
 * A second Astal.Window in the always-on bar instance, follower-anchored UNDER
 * the output bar indicator. Sections are generated from the live WirePlumber
 * graph — never hard-coded application names (doc §11/§26):
 *
 *   Output       — default speaker + level, `Change ›` opens the device subview
 *   Applications — one row per playback stream, each with mute, level, routing,
 *                  a brand app icon and the application/media subtitle
 *   Input        — default microphone + level
 *   Recording    — one row per recording stream, header carries the live dot
 *
 * Data comes from the `wp.audio.*` collections plus a graph snapshot in
 * audio/state.ts (link-resolved routing + per-stream app identity); the view is
 * a thin reader over those accessors and never shells out itself.
 *
 * Empty sections collapse entirely (decision 3A). The device list is an
 * in-place subview with a back arrow (decision 1B), mirroring the settings
 * panel.
 */

type Node = {
  id?: number
  name?: string | null
  description?: string | null
  icon?: string | null
  volume?: number
  mute?: boolean
  "media-class"?: number
  target_endpoint?: unknown
}

function nodeOf(value: unknown): Node | null {
  return (value as Node) ?? null
}

function systemIcon(group: string, variant: string): string | null {
  return registry.resolve(group, variant)
}

function nodeName(value: unknown, fallback: string): string {
  return nodeLabel(nodeOf(value), fallback)
}

// ── Row building blocks ────────────────────────────────────────────────────

/** Secondary line for a stream row (doc §25): the media name when the backend
 *  exposes one (e.g. "YouTube" under Chrome), else the PipeWire application
 *  name when it differs from the primary label. Empty means "no subtitle", and
 *  the row collapses it. */
function streamSubtitle(stream: unknown): string {
  const title = nodeName(stream, "")
  const media = streamMediaName(stream)
  // D6: PipeWire commonly reports the literal media name "Playback" when the
  // stream exposes no real track title; it is not a subtitle and must not
  // render as one (the row then falls through to the app name, or no subtitle).
  if (media && media.toLowerCase() !== "playback" && media !== title) return media
  const app = streamAppName(stream)
  if (app && app !== title) return app
  return ""
}

/** The level slider + percentage line, identical across every row type.
 *
 *  Writes are bracketed to a genuine USER interaction, exactly like the
 *  transport seek slider. `onNotifyValue` also fires when the binding pushes a
 *  value *into* the scale (initial render, a sibling stream's update rippling
 *  through the shared `nodes` binding, a `For` re-render), so writing from it
 *  unconditionally created a feedback loop: with two streams on different
 *  outputs, moving one slider echoed into the other (visible flicker, with the
 *  playback unchanged). The scale's own drag/click gestures are the only
 *  reliable user signal on this GTK4 build (its internal gesture group claims
 *  the pointer sequence), so we bracket the interaction and commit once on
 *  release/click. */
function LevelLine({
  volume,
  onChange,
  disabled = false,
  muted = false,
}: {
  volume: Accessor<number>
  onChange: (percent: number) => void
  /** A stream-less row has no node to set: render the line inert and dimmed
   *  instead of swapping in a different component. Keeping ONE widget shape
   *  per row avoids the container/child churn that tripped GTK's box assertions
   *  (a conditional sibling box inside a `For` row).
   *
   *  WARNING: this MUST stay `Accessor<boolean> | boolean` and be unwrapped
   *  below. A bare `boolean` type with an accessor passed in is ALWAYS truthy
   *  (a function object), which permanently disabled every volume line with
   *  `—` — and neither `ags bundle` (esbuild strips types unchecked) nor the
   *  symbol checker catch a type-level lie. */
  disabled?: Accessor<boolean> | boolean
  /** Muted state: dims the slider fill (value retained — mute never destroys
   *  the level) without disabling interaction. Same accessor discipline as
   *  `disabled`. */
  muted?: Accessor<boolean> | boolean
}) {
  const percent = createComputed(() => Math.round(clampVolume(volume()) * 100))
  const isDisabled: Accessor<boolean> = createComputed(() =>
    typeof disabled === "function"
      ? (disabled as Accessor<boolean>)()
      : disabled,
  )
  const isMuted: Accessor<boolean> = createComputed(() =>
    typeof muted === "function" ? (muted as Accessor<boolean>)() : muted,
  )
  let interacting = false

  function commit(self: Gtk.Scale) {
    if (!interacting) return
    interacting = false
    onChange(self.get_value())
  }

  function wireGestures(self: Gtk.Scale) {
    const controllers = self.observe_controllers()
    for (let i = 0; i < controllers.get_n_items(); i++) {
      const controller = controllers.get_item(i) as unknown as {
        constructor: { $gtype?: { name?: string } }
        connect: (signal: string, cb: () => void) => number
      } | null
      const name = controller?.constructor?.$gtype?.name
      if (name === "GtkGestureDrag") {
        controller!.connect("drag-begin", () => {
          interacting = true
        })
        controller!.connect("drag-end", () => commit(self))
      } else if (name === "GtkGestureClick") {
        controller!.connect("pressed", () => {
          interacting = true
        })
        controller!.connect("released", () => commit(self))
      }
    }
  }

  const lineClass = createComputed(() =>
    isDisabled() ? "audio-level-line" : isMuted() ? "audio-level-line muted" : "audio-level-line",
  )
  return (
    <box class={lineClass} spacing={9}>
      <slider
        class="settings-level-slider"
        hexpand
        sensitive={isDisabled((d) => !d)}
        min={0}
        max={100}
        step={1}
        value={createComputed(() => (isDisabled() ? 0 : percent()))}
        drawValue={false}
        $={(self: Gtk.Scale) => wireGestures(self)}
      />
      <label
        class="audio-percent"
        label={createComputed(() => (isDisabled() ? "—" : `${percent()}%`))}
      />
    </box>
  )
}

/** Per-app MPRIS transport line (D2–D5, D9): `⏮ ▶/⏸ ⏭ · seek · time` under
 *  the volume level line. Rendered only where a row links to a player
 *  (`playerForStream`, or a stream-less row's own player). `seekUs` is a DISPLAY
 *  value: it follows the authoritative `positionUs` at every MPRIS sync point
 *  and is interpolated locally between syncs while the popup is open and the
 *  player is Playing (I1 — a tick may interpolate a display value, never
 *  re-read authoritative state). */
function TransportLine({ player }: { player: Accessor<MprisPlayer | null> }) {
  const playing = createComputed(() => player()?.status === "Playing")
  const canSeek = createComputed(() => player()?.canSeek === true)
  const canGoPrevious = createComputed(() => player()?.canGoPrevious === true)
  const canGoNext = createComputed(() => player()?.canGoNext === true)
  const lengthUs = createComputed(() => player()?.metadata.lengthUs ?? 0)

  //: The slider works on a NORMALISED 0..1000 integer range, never raw µs.
  //: Raw µs values (up to INT64-ish) plus a `max` that recomputed from the
  //: track length churned the Gtk.Scale's adjustment while its row was being
  //: reused, and seeking then tripped GTK's box/unrealize assertions and killed
  //: the bar. A fixed 0..1000 range has no dynamic `max` and no huge values;
  //: microseconds are converted only at the boundaries.
  const SEEK_STEPS = 1000
  const [seekStep, setSeekStep] = createState(0)
  //: True between press/drag-begin and release/drag-end. Suppresses both the
  //: interpolation tick and the authoritative sync so the thumb tracks the
  //: pointer rather than the bus while the user is dragging.
  let interacting = false

  const usToStep = (us: number): number => {
    const total = lengthUs()
    if (total <= 0) return 0
    return Math.max(0, Math.min(SEEK_STEPS, Math.round((us / total) * SEEK_STEPS)))
  }
  const stepToUs = (step: number): number => {
    const total = lengthUs()
    if (total <= 0) return 0
    return Math.round((step / SEEK_STEPS) * total)
  }

  // Authoritative sync: reset the display base ONLY when the bus truth actually
  // moved (position or track). The player object is replaced on every MPRIS
  // rebuild, so syncing on identity alone made the thumb jump between the
  // divergent positions two interfaces of one app report (tidal resetting
  // 2:24 → 0:01 after an unrelated seek commit).
  let lastSyncedUs = -1
  let lastSyncedTrack = ""
  createEffect(() => {
    const p = player()
    if (interacting) return
    if (!p) {
      lastSyncedUs = -1
      lastSyncedTrack = ""
      setSeekStep(0)
      return
    }
    const track = p.metadata.title ?? ""
    if (p.positionUs !== lastSyncedUs || track !== lastSyncedTrack) {
      lastSyncedUs = p.positionUs
      lastSyncedTrack = track
      setSeekStep(usToStep(p.positionUs))
    }
  })

  // Display interpolation between bus syncs — the recording-widget pattern: one
  // 1s tick registered once, its body guarded to popup-open + Playing (I1).
  GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1000, () => {
    const p = player()
    if (!interacting && popupVisible() && p && p.status === "Playing") {
      setSeekStep(
        usToStep(
          interpolatePosition(
            p.positionUs,
            p.positionSyncedAtMs,
            true,
            GLib.get_monotonic_time() / 1000,
          ),
        ),
      )
    }
    return true
  })

  // D9: combined `elapsed / duration`; elapsed-only when the length is unknown.
  const timeText = createComputed(() => {
    const total = lengthUs()
    const elapsedUs = stepToUs(seekStep())
    const elapsed = formatClock(elapsedUs) || "0:00"
    return total > 0 ? `${elapsed} / ${formatClock(total)}` : elapsed
  })

  function commit(self: Gtk.Scale) {
    interacting = false
    const p = player()
    if (p && p.canSeek) seekPlayer(p, stepToUs(Math.round(self.get_value())))
  }

  // The Gtk.Scale's OWN drag/click gestures are the only reliable release hook:
  // its internal gesture group claims the pointer sequence, which implicitly
  // denies any gesture we could add to the widget ourselves. `observe_controllers`
  // exposes those gestures, so we bracket the interaction and commit once on
  // release — never from `onNotifyValue`, which fires on every drag update (D4).
  function wireSeekGestures(self: Gtk.Scale) {
    const controllers = self.observe_controllers()
    for (let i = 0; i < controllers.get_n_items(); i++) {
      const controller = controllers.get_item(i) as unknown as {
        constructor: { $gtype?: { name?: string } }
        connect: (signal: string, cb: () => void) => number
      } | null
      const name = controller?.constructor?.$gtype?.name
      if (name === "GtkGestureDrag") {
        controller!.connect("drag-begin", () => {
          interacting = true
        })
        controller!.connect("drag-end", () => commit(self))
      } else if (name === "GtkGestureClick") {
        controller!.connect("pressed", () => {
          interacting = true
        })
        controller!.connect("released", () => commit(self))
      }
    }
  }

  return (
    <box
      class={createComputed(() => (playing() ? "audio-transport" : "audio-transport paused"))}
      spacing={6}
      visible={createComputed(() => player() !== null)}
    >
      <button
        visible={canGoPrevious}
        tooltipText="Previous"
        canFocus={false}
        onClicked={() => {
          const p = player()
          if (p) previousPlayer(p)
        }}
      >
        <image
          pixel_size={15}
          $={(self: Gtk.Image) =>
            self.set_from_file(systemIcon("media-transport", "previous") ?? "")
          }
        />
      </button>
      <button
        tooltipText={playing((value) => (value ? "Pause" : "Play"))}
        canFocus={false}
        onClicked={() => {
          const p = player()
          if (p) playPausePlayer(p)
        }}
      >
        <image
          pixel_size={17}
          $={(self: Gtk.Image) => {
            createEffect(() =>
              self.set_from_file(
                systemIcon("media-transport", playing() ? "pause" : "play") ?? "",
              ),
            )
          }}
        />
      </button>
      <button
        visible={canGoNext}
        tooltipText="Next"
        canFocus={false}
        onClicked={() => {
          const p = player()
          if (p) nextPlayer(p)
        }}
      >
        <image
          pixel_size={15}
          $={(self: Gtk.Image) =>
            self.set_from_file(systemIcon("media-transport", "next") ?? "")
          }
        />
      </button>
      <slider
        class="settings-level-slider"
        hexpand
        min={0}
        max={SEEK_STEPS}
        step={1}
        value={seekStep}
        drawValue={false}
        visible={canSeek}
        onNotifyValue={(self: { get_value: () => number }) =>
          setSeekStep(Math.round(self.get_value()))
        }
        $={(self: Gtk.Scale) => wireSeekGestures(self)}
      />
      <label class="audio-time" label={timeText} />
    </box>
  )
}

/** Output-card master button (D1): toggles the most recently active player.
 *  Hidden when there is no player; the glyph is `pause` while that player is
 *  Playing, else `play`. Tooltip names the targeted player. */
function MasterButton() {
  const player = createComputed(() => masterPlayer())
  const playing = createComputed(() => player()?.status === "Playing")
  return (
    <button
      class="audio-master"
      canFocus={false}
      visible={createComputed(() => player() !== null)}
      tooltipText={createComputed(() => {
        const p = player()
        return p ? `Play/Pause — ${p.identity} (most recent)` : ""
      })}
      onClicked={() => {
        const p = player()
        if (p) playPausePlayer(p)
      }}
    >
      <image
        pixel_size={15}
        $={(self: Gtk.Image) => {
          createEffect(() =>
            self.set_from_file(
              systemIcon("media-transport", playing() ? "pause" : "play") ?? "",
            ),
          )
        }}
      />
    </button>
  )
}

/**
 * Mute toggle glyph (bare, no pill). `iconWhenOn` lets the mic use its own
 * art. `level` (0..1, live) makes the unmuted glyph track volume through the
 * same five thresholds as everywhere else (`muted/lowest/low/medium/max`);
 * callers that omit it keep the legacy static `low` glyph.
 */
function MuteGlyph({
  muteRaw,
  onToggle,
  tooltip,
  size = 20,
  iconWhenOn,
  level,
}: {
  muteRaw: Accessor<boolean>
  onToggle: () => void
  tooltip: string
  size?: number
  iconWhenOn?: Accessor<string | null>
  level?: Accessor<number>
}) {
  const muted = createComputed(() => muteRaw() === true)
  const path = createComputed<string | null>(() => {
    if (muted()) {
      return iconWhenOn
        ? systemIcon("microphone", "system-mic-off")
        : systemIcon("volume", "system-muted")
    }
    if (iconWhenOn) return iconWhenOn()
    if (!level) return systemIcon("volume", "system-low")
    return systemIcon("volume", "system-" + levelVariant(false, clampVolume(level())))
  })
  return (
    <button class="audio-mute" tooltipText={tooltip} onClicked={onToggle} canFocus={false}>
      <image
        pixel_size={size}
        $={(self) => {
          createEffect(() => {
            self.set_from_file(path() ?? "")
          })
        }}
      />
    </button>
  )
}

/** Trailing routing select: move this app's stream to another output device.
 *  The label is the stream's EFFECTIVE sink (explicit target → link-resolved
 *  sink → default sink name) — never the word "Default". Hidden while the app
 *  has no live stream (re-link gap): there is no node to route. */
function RoutingSelect({ app }: { app: string }) {
  const target = createComputed(() => effectiveSinkNameForApp(app))
  const hasStream = createComputed(() => hasLiveStreamForApp(app))

  function openMenu(anchor: Gtk.Widget) {
    if (!hasLiveStreamForApp(app)) return
    const menu = new Gtk.Popover()
    menu.set_parent(anchor)
    const list = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, spacing: 2 })
    for (const device of outputDevices() ?? []) {
      const row = new Gtk.Button({ css_classes: ["audio-route-item"] })
      row.set_child(new Gtk.Label({ label: nodeLabel(device, "Output"), xalign: 0 }))
      row.connect("clicked", () => {
        routeAppTo(app, device)
        menu.popdown()
      })
      list.append(row)
    }
    menu.set_child(list)
    menu.popup()
  }

  return (
    <box visible={hasStream}>
      <button
        class="audio-routing"
        tooltipText={target}
        canFocus={false}
        onClicked={(self: Gtk.Button) => openMenu(self)}
      >
        <box spacing={4}>
          <label
            label={target}
            ellipsize={3}
            maxWidthChars={14}
            xalign={0}
          />
          <label class="audio-routing-chevron" label={"\u203A"} />
        </box>
      </button>
    </box>
  )
}

/** One application row. Leading brand app icon (literal-color `app-icons`
 *  asset), then name with the application subtitle (Chrome / YouTube, per doc
 *  §25), mute toggle, routing select, volume line, and transport line.
 *
 *  The row is keyed by canonical APP (`AppRow.app`), never by node id or bus
 *  name — both churn (YouTube re-links recreate streams under new ids on seek;
 *  an app's MPRIS interfaces come and go). Every piece of live data is resolved
 *  at READ time from the app key (`liveStreamForApp` / `playerForApp`), so a
 *  reused row never holds a stale node or player object.
 *
 *  When the app momentarily has no live stream (re-link gap), the volume line
 *  shows the last-known level and is disabled, while the transport stays live —
 *  per the owner decision, the row persists so the app can be resumed. */
function StreamRow({ row }: { row: AppRow }) {
  const app = row.app

  const stream = createComputed(() => liveStreamForApp(app))
  const player: Accessor<MprisPlayer | null> = createComputed(() => playerForApp(app))

  //: Volume/mute read through the live node with last-known fallback, so a
  //: slider drag writes to the current node object and the line holds its value
  //: across transient stream gaps instead of flashing `—`. The shared epoch
  //: hook adds live updates (see state.ts): without it the percentage and mute
  //: glyph froze at first render.
  const nodeEpoch = useEndpointEpoch(stream)
  const volume = createComputed(() => {
    nodeEpoch()
    return clampVolume(displayVolumeForApp(app))
  })
  const muteRaw = createComputed(() => {
    nodeEpoch()
    return displayMuteForApp(app)
  })
  const muted = muteRaw

  const title = createComputed(() => {
    const s = stream()
    if (s) return nodeName(s, "Application")
    const p = player()
    return p && p.identity !== "" ? p.identity : "Application"
  })
  const subtitle = createComputed(() => {
    const s = stream()
    if (s) return streamSubtitle(s)
    return player()?.metadata.title ?? ""
  })
  const appIcon = createComputed<string | null>(() => {
    const s = stream()
    const brand = s
      ? streamAppIconPath(s)
      : streamAppIconPathForIdentity(player()?.identity ?? "")
    if (brand) return brand
    return systemIcon("volume", muted() ? "system-muted" : "system-low")
  })

  return (
    <box class="audio-row" orientation={1} spacing={6}>
      <box class="audio-row-head" spacing={9}>
        <image
          pixel_size={20}
          class="widget-icon audio-app-icon"
          $={(self) => {
            createEffect(() => self.set_from_file(appIcon() ?? ""))
          }}
        />
        <box class="audio-row-meta" orientation={1} hexpand>
          <box spacing={6}>
            <label class="audio-row-title" xalign={0} label={title} />
            <label class="audio-badge" visible={muted} label="Muted" valign={Gtk.Align.CENTER} />
          </box>
          <label
            class="audio-row-sub"
            xalign={0}
            visible={createComputed(() => subtitle() !== "")}
            label={subtitle}
          />
        </box>
        <MuteGlyph
          muteRaw={muteRaw}
          tooltip={title((t: string) => `Mute ${t}`)}
          size={17}
          level={volume}
          onToggle={() => toggleAppMute(app)}
        />
        <RoutingSelect app={app} />
      </box>
      <LevelLine
        volume={volume}
        disabled={createComputed(() => stream() === null)}
        muted={muted}
        onChange={(percent) => setAppVolume(app, percent / 100)}
      />
      <TransportLine player={player} />
    </box>
  )
}


/** The default output / input card. */
function DeviceCard({
  kind,
  title,
  endpoint,
  volume,
  muteRaw,
}: {
  kind: "output" | "input"
  title: string
  endpoint: Accessor<unknown>
  volume: Accessor<number>
  muteRaw: Accessor<boolean>
}) {
  const epoch = useEndpointEpoch(endpoint)
  const node = createComputed(() => nodeOf(endpoint()))
  //: Read LIVE GObject props through the epoch (OutputIndicator pattern) —
  //: the passed volume/muteRaw accessors memoize on list membership only and
  //: never see notify::volume/notify::mute on the resolved node.
  const level = createComputed(() => {
    epoch()
    return clampVolume(nodeOf(endpoint())?.volume ?? 0)
  })
  const muted = createComputed(() => {
    epoch()
    return nodeOf(endpoint())?.mute === true
  })
  const glyphVariant = createComputed(() => levelVariant(muted(), level()))
  const micIcon = createComputed<string | null>(() =>
    systemIcon("microphone", muted() ? "system-mic-off" : "system-mic-on"),
  )
  // Subtitle: the active route ("Headphones", "Analog Output") if present,
  // else the parent device description when it differs from the title.
  // Endpoints only carry name+description, so without this the card shows a
  // bare name with no context (the mock's second line).
  const subtitle = createComputed(() => {
    const n = node() as unknown as {
      route?: { description?: string } | null
      device?: { description?: string } | null
    } | null
    const routeDesc = n?.route?.description
    if (routeDesc) return routeDesc
    const title = nodeName(endpoint(), "")
    const devDesc = n?.device?.description
    if (devDesc && devDesc !== title) return devDesc
    return ""
  })

  function toggleMute() {
    const n = node()
    if (n) n.mute = !n.mute
  }

  return (
    <PanelCard title={title}>
      <box class="audio-row-head" spacing={9}>
        <button
          class="audio-mute"
          tooltipText={muted((m) => (m ? `Unmute ${kind}` : `Mute ${kind}`))}
          onClicked={toggleMute}
          canFocus={false}
        >
          <image
            pixel_size={20}
            $={(self) => {
              createEffect(() => {
                const path =
                  kind === "input"
                    ? micIcon()
                    : systemIcon("volume", "system-" + glyphVariant())
                self.set_from_file(path ?? "")
              })
            }}
          />
        </button>
        <box class="audio-row-meta" orientation={1} hexpand>
          <box spacing={6}>
            <label
              class="audio-row-title"
              xalign={0}
              label={createComputed(() => nodeName(endpoint(), `No ${kind} device`))}
            />
            <label class="audio-badge" visible={muted} label="Muted" valign={Gtk.Align.CENTER} />
          </box>
          <label
            class="audio-row-sub"
            xalign={0}
            visible={createComputed(() => subtitle() !== "")}
            label={subtitle}
          />
        </box>
        {/* D1: master play/pause sits between the name/meta block and `Change ›`,
            and controls the most recently active player. Output card only. */}
        {kind === "output" ? <MasterButton /> : null}
        {kind === "output" ? (
          <button
            class="audio-routing"
            tooltipText="Choose output device"
            canFocus={false}
            onClicked={showOutputDevices}
          >
            <box spacing={4}>
              <label label="Change" />
              <label class="audio-routing-chevron" label={"\u203A"} />
            </box>
          </button>
        ) : null}
        {kind === "input" ? (
          <button
            class="audio-routing"
            tooltipText="Choose input device"
            canFocus={false}
            onClicked={showInputDevices}
          >
            <box spacing={4}>
              <label label="Change" />
              <label class="audio-routing-chevron" label={"\u203A"} />
            </box>
          </button>
        ) : null}
      </box>
      <LevelLine
        volume={level}
        muted={muted}
        onChange={(percent) => {
          const n = node()
          if (n) n.volume = percent / 100
        }}
      />
    </PanelCard>
  )
}

/** Output device subview (decision 1B): list sinks, pick the default. */
function OutputDevicesView() {
  return (
    <box orientation={1} spacing={8}>
      <NavHeader title="Output devices" onBack={back} />
      {/* Stable key: `byClass` rebuilds its array on every `wp.nodes` notify,
          so reference identity would recreate the rows (see ApplicationsCard). */}
      <For each={outputDevices} id={(device) => `sink:${nodeOf(device)?.id ?? "?"}`}>
        {(device) => {
          const node = nodeOf(device)
          // D7: the current default sink (resolved via `default_speaker.id`)
          // carries the ✓ and the active-row fill. `is_default` is read-only on
          // this AstalWp build, so identity-by-id is the reliable check.
          const active = createComputed(() => {
            const def = defaultSpeaker()
            return (
              def !== null && node !== null && node.id !== undefined && def.id === node.id
            )
          })
          return (
            <button
              class={createComputed(() =>
                active() ? "audio-device active" : "audio-device",
              )}
              canFocus={false}
              onClicked={() => {
                setDefaultSpeaker(device)
                back()
              }}
            >
              <box spacing={9}>
                <label
                  class="audio-check"
                  label={createComputed(() => (active() ? "✓" : ""))}
                />
                <image
                  pixel_size={17}
                  $={(self) => self.set_from_file(systemIcon("volume", "system-low") ?? "")}
                />
                <label
                  class="audio-row-title"
                  xalign={0}
                  hexpand
                  label={nodeName(device, "Output")}
                />
              </box>
            </button>
          )
        }}
      </For>
    </box>
  )
}

/** Input device subview: list sources, pick the default microphone. Mirrors
 *  OutputDevicesView exactly (same in-place navigation, same ✓ + active-row
 *  contract); the only differences are the source collection, the mic glyph,
 *  and the `wpctl set-default` target. */
function InputDevicesView() {
  return (
    <box orientation={1} spacing={8}>
      <NavHeader title="Input devices" onBack={back} />
      {/* Stable key, same reason as everywhere else `byClass` feeds a `For`. */}
      <For each={inputDevices} id={(device) => `src:${nodeOf(device)?.id ?? "?"}`}>
        {(device) => {
          const node = nodeOf(device)
          // The current default source (resolved via `default_microphone.id`)
          // carries the ✓ and the active-row fill, like D7 for sinks.
          const active = createComputed(() => {
            const def = defaultMicrophone()
            return (
              def !== null && node !== null && node.id !== undefined && def.id === node.id
            )
          })
          return (
            <button
              class={createComputed(() =>
                active() ? "audio-device active" : "audio-device",
              )}
              canFocus={false}
              onClicked={() => {
                setDefaultMicrophone(device)
                back()
              }}
            >
              <box spacing={9}>
                <label
                  class="audio-check"
                  label={createComputed(() => (active() ? "✓" : ""))}
                />
                <image
                  pixel_size={17}
                  $={(self) => self.set_from_file(systemIcon("microphone", "system-mic-on") ?? "")}
                />
                <label
                  class="audio-row-title"
                  xalign={0}
                  hexpand
                  label={nodeName(device, "Input")}
                />
              </box>
            </button>
          )
        }}
      </For>
    </box>
  )
}

/** One recording stream row — brand app icon (same identity resolution as a
 *  playback row), mic mute toggle, and the app name as the subtitle. */
function RecorderRow({ stream }: { stream: unknown }) {
  const node = nodeOf(stream)
  const volume: Accessor<number> = createBinding(stream, "volume")
  const muteRaw: Accessor<boolean> = createBinding(stream, "mute")
  const level = createComputed(() => clampVolume(volume()))
  const title = nodeName(stream, "Recorder")
  const micOn = createComputed<string | null>(() =>
    systemIcon("microphone", "system-mic-on"),
  )
  const appIcon = createComputed<string | null>(() => {
    const brand = streamAppIconPath(stream)
    if (brand) return brand
    return systemIcon("microphone", "system-mic-on")
  })

  return (
    <box class="audio-row" orientation={1} spacing={6}>
      <box class="audio-row-head" spacing={9}>
        <image
          pixel_size={20}
          class="widget-icon audio-app-icon"
          $={(self) => {
            createEffect(() => self.set_from_file(appIcon() ?? ""))
          }}
        />
        <box class="audio-row-meta" orientation={1} hexpand>
          <label class="audio-row-title" xalign={0} label={title} />
          <label class="audio-row-sub" xalign={0} label="Using microphone" />
        </box>
        <MuteGlyph
          muteRaw={muteRaw}
          iconWhenOn={micOn}
          tooltip={`Mute ${title}`}
          onToggle={() => {
            if (node) node.mute = !node.mute
          }}
        />
      </box>
      <LevelLine
        volume={level}
        muted={muteRaw}
        onChange={(percent) => {
          if (node) node.volume = percent / 100
        }}
      />
    </box>
  )
}

/** Applications section — generated from playback streams; collapses when empty. */
function ApplicationsCard() {
  //: `For`'s default id is the ITEM REFERENCE, and every `applicationRows()`
  //: evaluation yields fresh references. Without a stable id, writing a
  //: slider's volume made the list re-evaluate, and EVERY row was disposed and
  //: recreated mid-gesture — whose unrealize tripped a GTK assertion and killed
  //: the bar (`gtk_widget_real_unrealize: assertion failed (!priv->mapped)`).
  //: `appRowKey` keys by canonical APP, which never churns (node ids do on
  //: every YouTube re-link; bus names do across MPRIS rebuilds).
  return (
    <box visible={createComputed(() => (applicationRows()?.length ?? 0) > 0)}>
      <PanelCard title="Applications">
        {/* One row per canonical app (state.ts): the row persists across node
            re-links and interface flips, and its content rebinds. */}
        <For each={applicationRows} id={appRowKey}>
          {(row) => <StreamRow row={row} />}
        </For>
      </PanelCard>
    </box>
  )
}

/** Recording section — generated from recording streams; collapses when empty. */
function RecordingCard() {
  return (
    <box visible={createComputed(() => (recordingStreams()?.length ?? 0) > 0)}>
      <PanelCard title="Recording">
        <box class="audio-card-head" spacing={6}>
          <box class="audio-live-dot" valign={Gtk.Align.CENTER} />
          <label class="audio-row-sub" label="Recording" />
        </box>
        {/* Stable key for the same reason as Applications: the list rebuilds on
            every `wp.nodes` notify and reference identity is not stable. */}
        <For each={recordingStreams} id={(stream) => `rec:${nodeOf(stream)?.id ?? "?"}`}>
          {(stream) => <RecorderRow stream={stream} />}
        </For>
      </PanelCard>
    </box>
  )
}

// ── The popup window ───────────────────────────────────────────────────────

/**
 * Full-screen click-outside catcher, created BEFORE the popup so the popup
 * stacks above it. Reuses the settings-panel catcher contract (hit-testable
 * 1%-opacity surface, close on release); the audio-dismiss path is unified in
 * `app.tsx`'s `popup-close` request, which the global Escape bind calls.
 */
export function AudioCatcher(gdkmonitor: Gdk.Monitor) {
  const { TOP, BOTTOM, LEFT, RIGHT } = Astal.WindowAnchor
  return (
    <window
      name="audio-catcher"
      class="settings-catcher"
      gdkmonitor={gdkmonitor}
      anchor={TOP | BOTTOM | LEFT | RIGHT}
      exclusivity={Astal.Exclusivity.IGNORE}
      layer={Astal.Layer.OVERLAY}
      keymode={Astal.Keymode.NONE}
      visible={popupVisible}
      $={(self) => {
        const click = new Gtk.GestureClick({ button: Gdk.BUTTON_PRIMARY })
        click.connect("released", () => close())
        self.add_controller(click)
      }}
    >
      <box class="settings-catcher-fill" hexpand vexpand />
    </window>
  )
}

/**
 * The audio popup. Follower-anchored under the bar; `exclusivity: IGNORE` so it
 * does not reserve an exclusive zone (the settings panel learned that NORMAL
 * would offset the surface below the bar and then double the margin).
 * Keyboard mode is NONE (house standard) so the bar keeps click activation;
 * Escape is handled globally via `ags request popup-close`.
 */
export function AudioPopup(gdkmonitor: Gdk.Monitor) {
  const { TOP, LEFT } = Astal.WindowAnchor
  let scroll: Gtk.ScrolledWindow | null = null

  createEffect(() => {
    viewEpoch()
    popupVisible()
    if (scroll) scroll.get_vadjustment().set_value(0)
  })

  // Re-snapshot the graph (links + per-stream identity) whenever the graph's
  // membership changes while the popup is open: a stream appears/disappears or
  // a sink does (e.g. a Bluetooth sink joining/leaving). Routing writes are
  // covered by open() and routeStreamTo()'s own one-shot refresh — this is
  // event-driven, never a timer.
  createEffect(() => {
    const streams = (playbackStreams()?.length ?? 0) + (recordingStreams()?.length ?? 0)
    const sinks = outputDevices()?.length ?? 0
    if (popupVisible() && (streams >= 0 || sinks >= 0)) void refreshStreamTargets()
  })

  // One-shot MPRIS hydration when the popup opens (I1: a user-action read, not
  // a timer) alongside the graph snapshot above, so transport positions and
  // capability flags are fresh the moment the popup is shown.
  createEffect(() => {
    if (popupVisible()) resyncMpris()
  })

  const mainVisible = createComputed(() => activeSection() === "main")
  const devicesVisible = createComputed(() => activeSection() === "output-devices")
  const inputDevicesVisible = createComputed(() => activeSection() === "input-devices")

  // Follower anchor beneath the invoking bar icon (same pattern as the
  // settings panel / wifi popup): left margin = icon centre − half the popup
  // width, clamped to the monitor. Falls back to the right edge when the icon
  // position is unknown (e.g. opened programmatically).
  const POPUP_WIDTH = 356
  const monitorWidth = gdkmonitor.get_geometry().width
  const marginLeft = createComputed(() => {
    const rightMost = monitorWidth - POPUP_WIDTH - 8
    const centre = audioIconX()
    if (centre == null) return rightMost
    const left = Math.round(centre - POPUP_WIDTH / 2)
    return Math.min(Math.max(left, 8), rightMost)
  })

  return (
    <window
      name="audio-popup"
      class="audio-popup"
      gdkmonitor={gdkmonitor}
      anchor={TOP | LEFT}
      exclusivity={Astal.Exclusivity.IGNORE}
      layer={Astal.Layer.OVERLAY}
      keymode={Astal.Keymode.NONE}
      marginTop={52}
      marginLeft={marginLeft}
      visible={popupVisible}
    >
      <box class="audio-surface" orientation={1} widthRequest={356}>
        <scrolledwindow
          class="audio-scroll"
          heightRequest={420}
          hscrollbarPolicy={Gtk.PolicyType.NEVER}
          vscrollbarPolicy={Gtk.PolicyType.AUTOMATIC}
          $={(self) => {
            scroll = self
          }}
        >
          <box orientation={1} spacing={9}>
            <box orientation={1} spacing={9} visible={mainVisible}>
              <DeviceCard
                kind="output"
                title="Output"
                endpoint={defaultSpeaker}
                volume={defaultSpeakerVolume}
                muteRaw={defaultSpeakerMute}
              />
              <ApplicationsCard />
              <DeviceCard
                kind="input"
                title="Input"
                endpoint={defaultMicrophone}
                volume={defaultMicrophoneVolume}
                muteRaw={defaultMicrophoneMute}
              />
              <RecordingCard />
            </box>
            <box orientation={1} spacing={9} visible={devicesVisible}>
              <OutputDevicesView />
            </box>
            <box orientation={1} spacing={9} visible={inputDevicesVisible}>
              <InputDevicesView />
            </box>
          </box>
        </scrolledwindow>
      </box>
    </window>
  )
}
