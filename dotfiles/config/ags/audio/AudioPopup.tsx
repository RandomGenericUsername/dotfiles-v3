import { Astal, Gtk, Gdk } from "ags/gtk4"
import { Accessor, createBinding, createComputed, createEffect, For } from "ags"
import { registry } from "../lib/icon-registry"
import { NavHeader, PanelCard } from "../settings-panel/primitives"
import {
  activeSection,
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
  effectiveSinkName,
  levelVariant,
  nodeLabel,
  outputDevices,
  playbackStreams,
  popupVisible,
  recordingStreams,
  refreshStreamTargets,
  routeStreamTo,
  setDefaultSpeaker,
  showOutputDevices,
  viewEpoch,
} from "./state"

/**
 * The audio popup (add-pipewire-audio-control).
 *
 * A second Astal.Window in the always-on bar instance, follower-anchored UNDER
 * the output bar indicator. Sections are generated from the live WirePlumber
 * graph — never hard-coded application names (doc §11/§26):
 *
 *   Output       — default speaker + level, `Change ›` opens the device subview
 *   Applications — one row per playback stream, each with mute, level, routing
 *   Input        — default microphone + level
 *   Recording    — one row per recording stream, header carries the live dot
 *
 * Data comes from `wp.nodes` filtered by media-class (see audio/state.ts for
 * why; this binding does not compile the speakers/streams collections).
 *
 * Empty sections collapse entirely (decision 3A). The device list is an
 * in-place subview with a back arrow (decision 1B), mirroring the settings
 * panel.
 */

type Node = {
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

/**
 * Application/device icon from the node's own `icon` (icon-theme name, e.g.
 * "google-chrome", "audio-headset-bluetooth"). Falls back to a registry SVG
 * when the theme lacks the name — so a missing app icon degrades to a
 * speaker glyph, never a broken image.
 */
function NodeIcon({
  iconName,
  fallback,
  size = 20,
}: {
  iconName: Accessor<string | null | undefined>
  fallback: Accessor<string | null>
  size?: number
}) {
  function hasThemeIcon(name: string): boolean {
    try {
      const display = Gdk.Display.get_default()
      const theme = display ? Gtk.IconTheme.get_for_display(display) : null
      return theme ? theme.has_icon(name) : false
    } catch {
      return false
    }
  }
  return (
    <image
      pixel_size={size}
      class="widget-icon"
      $={(self) => {
        createEffect(() => {
          const name = iconName() ?? ""
          if (name && hasThemeIcon(name)) self.set_from_icon_name(name)
          else self.set_from_file(fallback() ?? "")
        })
      }}
    />
  )
}

/** The level slider + percentage line, identical across every row type. */
function LevelLine({
  volume,
  onChange,
}: {
  volume: Accessor<number>
  onChange: (percent: number) => void
}) {
  const percent = createComputed(() => Math.round(clampVolume(volume()) * 100))
  return (
    <box class="audio-level-line" spacing={9}>
      <slider
        class="settings-level-slider"
        hexpand
        min={0}
        max={100}
        step={1}
        value={percent}
        drawValue={false}
        onNotifyValue={(self: { get_value: () => number }) =>
          onChange(self.get_value())
        }
      />
      <label class="audio-percent" label={percent((p) => `${p}%`)} />
    </box>
  )
}

/** Mute toggle glyph (bare, no pill). `iconWhenOn` lets the mic use its own art. */
function MuteGlyph({
  muteRaw,
  onToggle,
  tooltip,
  size = 20,
  iconWhenOn,
}: {
  muteRaw: Accessor<boolean>
  onToggle: () => void
  tooltip: string
  size?: number
  iconWhenOn?: Accessor<string | null>
}) {
  const muted = createComputed(() => muteRaw() === true)
  return (
    <button class="audio-mute" tooltipText={tooltip} onClicked={onToggle} canFocus={false}>
      <image
        pixel_size={size}
        $={(self) => {
          createEffect(() => {
            const path = muted()
              ? iconWhenOn
                ? systemIcon("microphone", "mic-off")
                : systemIcon("volume", "muted")
              : (iconWhenOn ? iconWhenOn() : systemIcon("volume", "low"))
            self.set_from_file(path ?? "")
          })
        }}
      />
    </button>
  )
}

/** Trailing routing select: move this stream to another output device.
 *  The label is the stream's EFFECTIVE sink (explicit target → link-resolved
 *  sink → default sink name) — never the word "Default". */
function RoutingSelect({ stream }: { stream: unknown }) {
  const target = createComputed(() => effectiveSinkName(stream))

  function openMenu(anchor: Gtk.Widget) {
    const menu = new Gtk.Popover()
    menu.set_parent(anchor)
    const list = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, spacing: 2 })
    for (const device of outputDevices() ?? []) {
      const row = new Gtk.Button({ css_classes: ["audio-route-item"] })
      row.set_child(new Gtk.Label({ label: nodeLabel(device, "Output"), xalign: 0 }))
      row.connect("clicked", () => {
        routeStreamTo(stream, device)
        menu.popdown()
      })
      list.append(row)
    }
    menu.set_child(list)
    menu.popup()
  }

  return (
    <button
      class="audio-routing"
      tooltipText="Route this stream to an output device"
      canFocus={false}
      onClicked={(self: Gtk.Button) => openMenu(self)}
    >
      <box spacing={4}>
        <label label={target} />
        <label class="audio-routing-chevron" label={"\u203A"} />
      </box>
    </button>
  )
}

/** One playback stream (an application). Leading app icon (theme icon-name
 *  with registry fallback), then name, mute toggle, and routing select. */
function StreamRow({ stream }: { stream: unknown }) {
  const node = nodeOf(stream)
  const volume: Accessor<number> = createBinding(stream, "volume")
  const muteRaw: Accessor<boolean> = createBinding(stream, "mute")
  const muted = createComputed(() => muteRaw() === true)
  const level = createComputed(() => clampVolume(volume()))
  const title = nodeName(stream, "Application")
  const appIcon = createComputed(() => node?.icon ?? null)
  const appIconFallback = createComputed<string | null>(() =>
    systemIcon("volume", muted() ? "muted" : "low"),
  )

  return (
    <box class="audio-row" orientation={1} spacing={6}>
      <box class="audio-row-head" spacing={9}>
        <NodeIcon iconName={appIcon} fallback={appIconFallback} />
        <box class="audio-row-meta" orientation={1} hexpand>
          <label class="audio-row-title" xalign={0} label={title} />
        </box>
        <MuteGlyph
          muteRaw={muteRaw}
          tooltip={`Mute ${title}`}
          size={17}
          onToggle={() => {
            if (node) node.mute = !node.mute
          }}
        />
        <RoutingSelect stream={stream} />
      </box>
      <LevelLine
        volume={level}
        onChange={(percent) => {
          if (node) node.volume = percent / 100
        }}
      />
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
  const node = createComputed(() => nodeOf(endpoint()))
  const level = createComputed(() => clampVolume(volume()))
  const muted = createComputed(() => muteRaw() === true)
  const glyphVariant = createComputed(() => levelVariant(muted(), level()))
  const micIcon = createComputed<string | null>(() =>
    systemIcon("microphone", muted() ? "mic-off" : "mic-on"),
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
                    : systemIcon("volume", glyphVariant())
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
      </box>
      <LevelLine
        volume={level}
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
      <For each={outputDevices}>
        {(device) => {
          const node = nodeOf(device)
          return (
            <button
              class="audio-device"
              canFocus={false}
              onClicked={() => {
                setDefaultSpeaker(device)
                back()
              }}
            >
              <box spacing={9}>
                <image
                  pixel_size={17}
                  $={(self) => self.set_from_file(systemIcon("volume", "low") ?? "")}
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

/** One recording stream row — same shape as a playback row, mic glyph. */
function RecorderRow({ stream }: { stream: unknown }) {
  const node = nodeOf(stream)
  const volume: Accessor<number> = createBinding(stream, "volume")
  const muteRaw: Accessor<boolean> = createBinding(stream, "mute")
  const level = createComputed(() => clampVolume(volume()))
  const title = nodeName(stream, "Recorder")
  const micOn = createComputed<string | null>(() =>
    systemIcon("microphone", "mic-on"),
  )

  return (
    <box class="audio-row" orientation={1} spacing={6}>
      <box class="audio-row-head" spacing={9}>
        <MuteGlyph
          muteRaw={muteRaw}
          iconWhenOn={micOn}
          tooltip={`Mute ${title}`}
          onToggle={() => {
            if (node) node.mute = !node.mute
          }}
        />
        <box class="audio-row-meta" orientation={1} hexpand>
          <label class="audio-row-title" xalign={0} label={title} />
          <label class="audio-row-sub" xalign={0} label="Using microphone" />
        </box>
      </box>
      <LevelLine
        volume={level}
        onChange={(percent) => {
          if (node) node.volume = percent / 100
        }}
      />
    </box>
  )
}

/** Applications section — generated from playback streams; collapses when empty. */
function ApplicationsCard() {
  return (
    <box visible={createComputed(() => (playbackStreams()?.length ?? 0) > 0)}>
      <PanelCard title="Applications">
        <For each={playbackStreams}>{(stream) => <StreamRow stream={stream} />}</For>
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
        <For each={recordingStreams}>
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

  // Re-snapshot link-resolved stream targets whenever streams appear or
  // disappear while the popup is open (routing itself is covered by open()
  // and routeStreamTo()'s own refresh).
  createEffect(() => {
    const count = (playbackStreams()?.length ?? 0) + (recordingStreams()?.length ?? 0)
    if (popupVisible() && count >= 0) void refreshStreamTargets()
  })

  const mainVisible = createComputed(() => activeSection() === "main")
  const devicesVisible = createComputed(() => activeSection() === "output-devices")

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
          </box>
        </scrolledwindow>
      </box>
    </window>
  )
}
