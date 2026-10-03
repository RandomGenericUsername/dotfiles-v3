import { Astal, Gtk, Gdk } from "ags/gtk4"
import { Accessor, For, createComputed, createEffect, createState } from "ags"
import { registry } from "../lib/icon-registry"
import { close, popupVisible, audioIconX } from "./state"
import type { AudioPanelViewModel, AudioAppRowView } from "./presentation/audio-panel-view-model"

type RouteChoice = { kind: "follow-preferred" } | { kind: "explicit"; endpointId: string }
type TransportAction = "play-pause" | "previous" | "next"

/** Commands are injected by the application composition root; the GTK view owns no audio policy. */
export interface AudioPanelActions {
  selectPreferredOutput(endpointId: string): void
  setOutputVolume(endpointId: string, percent: number): void
  toggleOutputMute(endpointId: string): void
  setAppRoute(appId: string, route: RouteChoice): void
  setAppVolume(appId: string, percent: number): void
  toggleAppMute(appId: string): void
  playerAction(playerId: string, action: TransportAction): void
  seek(playerId: string, positionUs: number): void
  selectInput(endpointId: string): void
  setInputVolume(endpointId: string, percent: number): void
  toggleInputMute(endpointId: string): void
}

export interface AudioPanelBinding {
  model: Accessor<AudioPanelViewModel>
  actions: AudioPanelActions
}

type VolumeState = { level: number; muted: boolean; mixedLevel?: boolean; mixedMuted?: boolean }

const clampPercent = (value: number) => Math.max(0, Math.min(100, Math.round(value)))
const asPercent = (level: number) => clampPercent(level * 100)
const icon = (group: string, variant: string) => registry.resolve(group, variant) ?? ""

function formatClock(us: number | null | undefined): string {
  if (us == null || !Number.isFinite(us) || us < 0) return "0:00"
  const seconds = Math.floor(us / 1_000_000)
  const minutes = Math.floor(seconds / 60)
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`
}

function setImageOnce(image: Gtk.Image, path: string): void {
  const holder = image as Gtk.Image & { __audioImagePath?: string }
  if (!path || holder.__audioImagePath === path) return
  holder.__audioImagePath = path
  image.set_from_file(path)
}

function accessibleLabel(widget: Gtk.Widget, label: string): void {
  const accessible = widget as Gtk.Widget & {
    update_property?: (properties: Gtk.AccessibleProperty[], values: unknown[]) => void
  }
  accessible.update_property?.([Gtk.AccessibleProperty.LABEL], [label])
}

function IconButton({
  name,
  tooltip,
  imagePath,
  onClicked,
  active = false,
  visible = true,
  disabled = false,
  className = "audio-icon-button",
}: {
  name: string | Accessor<string>
  tooltip: string | Accessor<string>
  imagePath: string | Accessor<string>
  onClicked: () => void
  active?: boolean | Accessor<boolean>
  visible?: boolean | Accessor<boolean>
  disabled?: boolean | Accessor<boolean>
  className?: string
}) {
  const label = createComputed(() => typeof name === "function" ? name() : name)
  const hint = createComputed(() => typeof tooltip === "function" ? tooltip() : tooltip)
  const path = createComputed(() => typeof imagePath === "function" ? imagePath() : imagePath)
  const isActive = createComputed(() => typeof active === "function" ? active() : active)
  const isVisible = createComputed(() => typeof visible === "function" ? visible() : visible)
  const isDisabled = createComputed(() => typeof disabled === "function" ? disabled() : disabled)
  return (
    <button
      class={createComputed(() => `${className}${isActive() ? " active" : ""}`)}
      visible={isVisible}
      sensitive={createComputed(() => !isDisabled())}
      tooltipText={hint}
      onClicked={onClicked}
      canFocus
      hasTooltip
      $={(self: Gtk.Button) => createEffect(() => accessibleLabel(self, label()))}
    >
      <image
        pixel_size={18}
        $={(self: Gtk.Image) => createEffect(() => setImageOnce(self, path()))}
      />
    </button>
  )
}

/** A fixed-shape slider. Values are written only after a real pointer/key interaction is committed. */
function LevelControl({
  label,
  volume,
  disabled = false,
  onChange,
}: {
  label: Accessor<string>
  volume: Accessor<VolumeState>
  disabled?: Accessor<boolean>
  onChange: (percent: number) => void
}) {
  let interacting = false
  const percent = createComputed(() => asPercent(volume().level))
  const isDisabled = createComputed(() => disabled?.() ?? false)

  function wireGestures(scale: Gtk.Scale) {
    const controllers = scale.observe_controllers()
    for (let i = 0; i < controllers.get_n_items(); i++) {
      const controller = controllers.get_item(i) as unknown as {
        constructor?: { $gtype?: { name?: string } }
        connect?: (signal: string, callback: () => void) => number
      } | null
      if (controller?.constructor?.$gtype?.name === "GtkGestureDrag") {
        controller.connect?.("drag-begin", () => { interacting = true })
        controller.connect?.("drag-end", () => {
          if (!interacting) return
          interacting = false
          onChange(scale.get_value())
        })
      } else if (controller?.constructor?.$gtype?.name === "GtkGestureClick") {
        controller.connect?.("pressed", () => { interacting = true })
        controller.connect?.("released", () => {
          if (!interacting) return
          interacting = false
          onChange(scale.get_value())
        })
      }
    }
    const keys = new Gtk.EventControllerKey()
    keys.connect("key-pressed", () => { interacting = true; return false })
    keys.connect("key-released", () => {
      if (!interacting) return
      interacting = false
      onChange(scale.get_value())
    })
    scale.add_controller(keys)
  }

  return (
    <box class="audio-level-line" spacing={8}>
      <slider
        class="settings-level-slider audio-level-slider"
        hexpand
        min={0}
        max={100}
        step={1}
        value={percent}
        drawValue={false}
        sensitive={createComputed(() => !isDisabled())}
        tooltipText={label}
        $={(self: Gtk.Scale) => {
          createEffect(() => accessibleLabel(self, `${label()} ${percent()} percent`))
          wireGestures(self)
        }}
      />
      <label class="audio-percent" label={createComputed(() => isDisabled() ? "—" : `${percent()}%`)} />
    </box>
  )
}

function openChoicePopover(
  anchor: Gtk.Widget,
  title: string,
  options: { label: string; selected: boolean; activate: () => void }[],
) {
  const popover = new Gtk.Popover({ autohide: true })
  popover.set_parent(anchor)
  const list = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, spacing: 3 })
  const heading = new Gtk.Label({ label: title, xalign: 0 })
  heading.add_css_class("audio-menu-heading")
  list.append(heading)
  for (const option of options) {
    const button = new Gtk.Button({
      css_classes: ["audio-menu-option", ...(option.selected ? ["selected"] : [])],
      focusable: true,
      tooltip_text: option.label,
    })
    const row = new Gtk.Box({ spacing: 8 })
    const mark = new Gtk.Label({ label: option.selected ? "✓" : "", xalign: 0 })
    mark.add_css_class("audio-option-mark")
    const label = new Gtk.Label({ label: option.label, xalign: 0, hexpand: true, ellipsize: Gtk.EllipsizeMode.END })
    row.append(mark)
    row.append(label)
    button.set_child(row)
    accessibleLabel(button, `${option.label}${option.selected ? ", selected" : ""}`)
    button.connect("clicked", () => {
      option.activate()
      popover.popdown()
    })
    list.append(button)
  }
  popover.set_child(list)
  popover.connect("closed", () => {
    popover.unparent()
    anchor.grab_focus()
  })
  popover.popup()
}

function DeviceSelector({
  title,
  value,
  devices,
  onSelect,
  iconName,
}: {
  title: string
  value: Accessor<string>
  devices: Accessor<readonly { id: string; name: string; available: boolean }[]>
  onSelect: (id: string) => void
  iconName: string
}) {
  return (
    <button
      class="audio-device-select"
      hexpand
      tooltipText={value}
      onClicked={(self: Gtk.Button) => {
        const currentId = value()
        openChoicePopover(self, title, devices().filter((device) => device.available).map((device) => ({
          label: device.name,
          selected: device.id === currentId,
          activate: () => onSelect(device.id),
        })))
      }}
      $={(self: Gtk.Button) => createEffect(() => accessibleLabel(self, `${title}: ${value()}`))}
    >
      <box spacing={10} hexpand>
        <image pixel_size={18} $={(self: Gtk.Image) => setImageOnce(self, icon(iconName, "system-low"))} />
        <label class="audio-device-select-name" xalign={0} hexpand ellipsize={Gtk.EllipsizeMode.END} label={value} />
        <label class="audio-device-chevron" label="▾" />
      </box>
    </button>
  )
}

function PreferredOutput({ binding }: { binding: AudioPanelBinding }) {
  const currentOutput = createComputed(() => {
    const model = binding.model()
    return model.outputs.find((output) => output.id === model.preferredOutputId) ?? null
  })
  const value = createComputed(() => currentOutput()?.name ?? "No output available")
  const volume = createComputed<VolumeState>(() => currentOutput()?.volume ?? { level: 0, muted: false })
  const outputs = createComputed(() => binding.model().outputs)
  const endpointId = createComputed(() => binding.model().preferredOutputId ?? "")
  return (
    <box class="audio-section" orientation={Gtk.Orientation.VERTICAL}>
      <box class="audio-section-heading">
        <label class="audio-section-title" label="Preferred output" />
        <label class="audio-section-hint" label="Default destination" />
      </box>
      <DeviceSelector
        title="Preferred output"
        value={value}
        devices={outputs}
        iconName="volume"
        onSelect={(id) => binding.actions.selectPreferredOutput(id)}
      />
      <box class="audio-output-caption">
        <label class="audio-scope-label" label={createComputed(() => `Output level · affects all audio routed to ${value()}`)} />
      </box>
      <box class="audio-control-line" spacing={8}>
        <IconButton
          name={createComputed(() => `${value()} output ${volume().muted ? "muted" : "unmuted"}`)}
          tooltip={createComputed(() => `${volume().muted ? "Unmute" : "Mute"} ${value()}`)}
          imagePath={createComputed(() => icon("volume", volume().muted ? "system-muted" : `system-${volume().level === 0 ? "muted" : volume().level < 0.34 ? "low" : volume().level < 0.67 ? "medium" : "high"}`))}
          onClicked={() => binding.actions.toggleOutputMute(endpointId())}
        />
        <LevelControl
          label={createComputed(() => `${value()} output level`)}
          volume={volume}
          disabled={createComputed(() => !currentOutput()?.available)}
          onChange={(percent) => binding.actions.setOutputVolume(endpointId(), percent)}
        />
      </box>
    </box>
  )
}

function rowVolume(row: AudioAppRowView): VolumeState {
  return row.volume
}

function routeMenuLabel(row: AudioAppRowView): string {
  return row.routeLabel || "Route unknown"
}

function AppRow({ row, binding }: { row: Accessor<AudioAppRowView>; binding: AudioPanelBinding }) {
  const appName = createComputed(() => row().appName)
  const title = createComputed(() => row().title || appName())
  const artist = createComputed(() => [row().artist, row().album].filter(Boolean).join(" · "))
  const volume = createComputed(() => ({
    ...rowVolume(row()), mixedLevel: row().mixedLevel, mixedMuted: row().mixedMuted,
  }))
  const streamLive = createComputed(() => row().hasCurrentStream)
  const currentPlayer = createComputed(() => row().hasCurrentPlayer && row().playerId ? row().playerId : null)
  const outputs = createComputed(() => binding.model().outputs)
  const preferred = createComputed(() => binding.model().outputs.find((output) => output.id === binding.model().preferredOutputId)?.name ?? "Unavailable")

  function routeOptions(anchor: Gtk.Widget) {
    const current = row()
  const choices: { label: string; selected: boolean; activate: () => void }[] = [
      {
        label: `Follow preferred · ${preferred()}`,
        selected: current.routeIntent?.kind === "follow-preferred",
        activate: () => binding.actions.setAppRoute(current.appId, { kind: "follow-preferred" }),
      },
      ...outputs().filter((output) => output.available).map((output) => ({
        label: `${output.name} · Override`,
        selected: current.routeIntent?.kind === "explicit" && current.routeIntent.endpointId === output.id,
        activate: () => binding.actions.setAppRoute(current.appId, { kind: "explicit", endpointId: output.id }),
      })),
    ]
    openChoicePopover(anchor, `${current.appName} output route`, choices)
  }

  const artworkPath = createComputed(() => row().artworkPath || "")
  const appIconPath = createComputed(() => icon("app-icons", row().iconName || "application-x-executable"))
  const mutePath = createComputed(() => {
    const state = volume()
    if (state.muted) return icon("volume", "system-muted")
    const level = state.level
    return icon("volume", `system-${level === 0 ? "muted" : level < 0.34 ? "low" : level < 0.67 ? "medium" : "high"}`)
  })

  const [seekValue, setSeekValue] = createState(0)
  let seeking = false
  const seekDuration = createComputed(() => row().durationUs ?? 0)
  const seekPosition = createComputed(() => row().positionUs ?? 0)
  const canSeek = createComputed(() => row().canSeek && seekDuration() > 0 && currentPlayer() !== null)
  createEffect(() => {
    if (!seeking) {
      const duration = seekDuration()
      setSeekValue(duration > 0 ? Math.max(0, Math.min(1000, seekPosition() / duration * 1000)) : 0)
    }
  })

  function commitSeek(scale: Gtk.Scale) {
    if (!seeking) return
    seeking = false
    const playerId = currentPlayer()
    if (playerId && canSeek()) binding.actions.seek(playerId, Math.round(scale.get_value() / 1000 * seekDuration()))
  }

  function wireSeek(scale: Gtk.Scale) {
    const controllers = scale.observe_controllers()
    for (let i = 0; i < controllers.get_n_items(); i++) {
      const controller = controllers.get_item(i) as unknown as {
        constructor?: { $gtype?: { name?: string } }
        connect?: (signal: string, callback: () => void) => number
      } | null
      if (controller?.constructor?.$gtype?.name === "GtkGestureDrag") {
        controller.connect?.("drag-begin", () => { seeking = true })
        controller.connect?.("drag-end", () => commitSeek(scale))
      } else if (controller?.constructor?.$gtype?.name === "GtkGestureClick") {
        controller.connect?.("pressed", () => { seeking = true })
        controller.connect?.("released", () => commitSeek(scale))
      }
    }
    const keys = new Gtk.EventControllerKey()
    keys.connect("key-pressed", () => { seeking = true; return false })
    keys.connect("key-released", () => commitSeek(scale))
    scale.add_controller(keys)
  }

  return (
    <box class="audio-app-row" orientation={Gtk.Orientation.VERTICAL} spacing={7}
      $={(self: Gtk.Widget) => createEffect(() => accessibleLabel(self, `${appName()}${row().title ? `, ${row().title}` : ""}${artist() ? `, ${artist()}` : ""}`))}>
      <box class="audio-app-head" spacing={9}>
        <box class="audio-artwork" valign={Gtk.Align.START}>
          <image class="audio-art-image" pixel_size={43} $={(self: Gtk.Image) => createEffect(() => setImageOnce(self, artworkPath() || appIconPath()))} />
          <label class="audio-art-fallback" label={createComputed(() => row().appName.slice(0, 1).toUpperCase())} visible={createComputed(() => !artworkPath() && !appIconPath())} />
        </box>
        <box class="audio-app-meta" orientation={Gtk.Orientation.VERTICAL} spacing={1} hexpand>
          <label class="audio-app-name" xalign={0} ellipsize={Gtk.EllipsizeMode.END} maxWidthChars={24} tooltipText={appName} label={appName} />
          <label class="audio-media-title" xalign={0} ellipsize={Gtk.EllipsizeMode.END} maxWidthChars={30} tooltipText={title} label={title} />
          <label class="audio-media-artist" xalign={0} ellipsize={Gtk.EllipsizeMode.END} maxWidthChars={30} tooltipText={artist} label={createComputed(() => artist() || "Media details unavailable")} />
        </box>
        <button
          class="audio-route-selector"
          tooltipText={createComputed(() => routeMenuLabel(row()))}
          onClicked={(self: Gtk.Button) => routeOptions(self)}
          $={(self: Gtk.Button) => createEffect(() => accessibleLabel(self, `${appName()} output route: ${routeMenuLabel(row())}`))}
        >
          <box spacing={4}>
            <label class="audio-route-label" maxWidthChars={15} ellipsize={Gtk.EllipsizeMode.END} label={createComputed(() => routeMenuLabel(row()))} />
            <label class="audio-device-chevron" label="▾" />
          </box>
        </button>
      </box>
      <box class="audio-app-controls" orientation={Gtk.Orientation.VERTICAL} spacing={6}>
        <box class="audio-transport" spacing={5} visible={createComputed(() => currentPlayer() !== null)}>
          <IconButton name={createComputed(() => `Previous in ${appName()}`)} tooltip={createComputed(() => `Previous · ${appName()}`)} imagePath={icon("media-transport", "previous")} visible={createComputed(() => row().capabilities.canGoPrevious)} onClicked={() => { const id = currentPlayer(); if (id && row().capabilities.canGoPrevious) binding.actions.playerAction(id, "previous") }} />
          <IconButton name={createComputed(() => `${row().playback === "playing" ? "Pause" : "Play"} ${appName()}`)} tooltip={createComputed(() => `${row().playback === "playing" ? "Pause" : "Play"} · ${appName()}`)} imagePath={createComputed(() => icon("media-transport", row().playback === "playing" ? "pause" : "play"))} visible={createComputed(() => row().capabilities.canPlayPause)} onClicked={() => { const id = currentPlayer(); if (id && row().capabilities.canPlayPause) binding.actions.playerAction(id, "play-pause") }} active={createComputed(() => row().playback === "playing")} />
          <IconButton name={createComputed(() => `Next in ${appName()}`)} tooltip={createComputed(() => `Next · ${appName()}`)} imagePath={icon("media-transport", "next")} visible={createComputed(() => row().capabilities.canGoNext)} onClicked={() => { const id = currentPlayer(); if (id && row().capabilities.canGoNext) binding.actions.playerAction(id, "next") }} />
          <slider
            class="settings-level-slider audio-seek-slider"
            hexpand
            min={0}
            max={1000}
            step={1}
            value={seekValue}
            visible={canSeek}
            sensitive={canSeek}
            drawValue={false}
            tooltipText={createComputed(() => `${title()} position ${formatClock(seekPosition())} of ${formatClock(seekDuration())}`)}
            onNotifyValue={(self: Gtk.Scale) => setSeekValue(Math.round(self.get_value()))}
            $={(self: Gtk.Scale) => {
              createEffect(() => accessibleLabel(self, `${title()} playback position in ${appName()}, ${formatClock(seekPosition())} of ${formatClock(seekDuration())}`))
              wireSeek(self)
            }}
          />
          <label class="audio-time" label={createComputed(() => `${formatClock(seekPosition())} / ${formatClock(seekDuration())}`)} visible={canSeek} />
        </box>
        <box class="audio-app-volume" spacing={8}>
          <IconButton
            name={createComputed(() => `${appName()} stream volume ${volume().muted ? "muted" : volume().mixedMuted ? "mixed mute" : "unmuted"}`)}
            tooltip={createComputed(() => `${volume().muted ? "Unmute" : "Mute"} ${appName()}`)}
            imagePath={mutePath()}
            onClicked={() => binding.actions.toggleAppMute(row().appId)}
            active={createComputed(() => volume().muted || volume().mixedMuted === true)}
            disabled={createComputed(() => !streamLive())}
            className="audio-icon-button audio-app-mute"
          />
          <LevelControl
            label={createComputed(() => `${appName()} stream volume`)}
            volume={volume}
            disabled={createComputed(() => !streamLive())}
            onChange={(percent) => binding.actions.setAppVolume(row().appId, percent)}
          />
          <label class="audio-mixed-value" label="Mixed" visible={createComputed(() => volume().mixedLevel === true)} />
        </box>
      </box>
    </box>
  )
}

function PlayingSection({ binding }: { binding: AudioPanelBinding }) {
  const rows = createComputed(() => binding.model().rows)
  return (
    <box class="audio-section audio-playing-section" orientation={Gtk.Orientation.VERTICAL}>
      <box class="audio-section-heading">
        <label class="audio-section-title" label="Playing" />
        <label class="audio-section-hint" label={createComputed(() => `${rows().length} ${rows().length === 1 ? "app" : "apps"}`)} />
      </box>
      <box class="audio-app-list" orientation={Gtk.Orientation.VERTICAL} spacing={0}>
        <For each={rows} id={(row) => row.id}>
          {(item) => {
            const id = item.id
            const row = createComputed(() => binding.model().rows.find((candidate) => candidate.id === id) ?? item)
            return <AppRow row={row} binding={binding} />
          }}
        </For>
        <label class="audio-empty-state" label="No apps playing" visible={createComputed(() => rows().length === 0)} />
      </box>
    </box>
  )
}

function InputSection({ binding }: { binding: AudioPanelBinding }) {
  const model = createComputed(() => binding.model())
  const input = createComputed(() => {
    const state = model()
    return state.inputs.find((device) => device.id === state.preferredInputId) ?? null
  })
  const name = createComputed(() => input()?.name ?? "No input available")
  const volume = createComputed<VolumeState>(() => input()?.volume ?? { level: 0, muted: false })
  const devices = createComputed(() => model().inputs)
  const id = createComputed(() => model().preferredInputId ?? "")
  return (
    <box class="audio-section" orientation={Gtk.Orientation.VERTICAL}>
      <box class="audio-section-heading">
        <label class="audio-section-title" label="Input" />
        <label class="audio-section-hint" label="Preferred microphone" />
      </box>
      <DeviceSelector title="Input device" value={name} devices={devices} iconName="microphone" onSelect={(endpoint) => binding.actions.selectInput(endpoint)} />
      <box class="audio-control-line" spacing={8}>
        <IconButton
          name={createComputed(() => `${name()} microphone ${volume().muted ? "muted" : "unmuted"}`)}
          tooltip={createComputed(() => `${volume().muted ? "Unmute" : "Mute"} ${name()}`)}
          imagePath={createComputed(() => icon("microphone", volume().muted ? "system-mic-off" : "system-mic-on"))}
          onClicked={() => binding.actions.toggleInputMute()}
          disabled={createComputed(() => !input()?.available)}
        />
        <LevelControl label={createComputed(() => `${name()} input level`)} volume={volume} disabled={createComputed(() => !input()?.available)} onChange={(percent) => binding.actions.setInputVolume(id(), percent)} />
      </box>
    </box>
  )
}

function MicrophoneActivity({ binding }: { binding: AudioPanelBinding }) {
  const consumers = createComputed(() => binding.model().inputConsumers)
  return (
    <box class="audio-section audio-microphone-section" orientation={Gtk.Orientation.VERTICAL}>
      <box class="audio-section-heading">
        <label class="audio-section-title" label="Microphone activity" />
        <label class="audio-section-hint" label={createComputed(() => consumers().length ? `${consumers().length} active` : "Live input use")} />
      </box>
      <For each={consumers} id={(consumer) => consumer.id}>
        {(consumer) => (
          <box class="audio-consumer-row" spacing={9}>
            <image pixel_size={19} class="audio-consumer-icon" $={(self: Gtk.Image) => setImageOnce(self, icon("app-icons", consumer.iconName || "application-x-executable"))} />
            <label class="audio-consumer-name" xalign={0} hexpand label={consumer.appName} />
            <box class="audio-live-dot" />
            <label class="audio-live-label" label="Using microphone" />
          </box>
        )}
      </For>
      <label class="audio-empty-state" label="No microphone consumers detected" visible={createComputed(() => consumers().length === 0)} />
    </box>
  )
}

/** Compact presentation surface. Actions and the read model are supplied by the composition root. */
export function AudioPanelContent({ binding }: { binding: AudioPanelBinding }) {
  return (
    <box class="audio-panel-content" orientation={Gtk.Orientation.VERTICAL} spacing={9}>
      <box class="audio-panel-heading">
        <label class="audio-panel-title" label="Audio" />
        <label class="audio-panel-caption" label="Output · apps · input" />
      </box>
      <PreferredOutput binding={binding} />
      <PlayingSection binding={binding} />
      <InputSection binding={binding} />
      <MicrophoneActivity binding={binding} />
    </box>
  )
}

/** Full-screen click-outside catcher remains owned by the existing popup lifecycle. */
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
      $={(self: Gtk.Window) => {
        const click = new Gtk.GestureClick({ button: Gdk.BUTTON_PRIMARY })
        click.connect("released", () => close())
        self.add_controller(click)
      }}
    >
      <box class="settings-catcher-fill" hexpand vexpand />
    </window>
  )
}

/** Popup shell. Runtime composition will provide the binding when the new application boundary is wired. */
export function AudioPopup(gdkmonitor: Gdk.Monitor, binding?: AudioPanelBinding) {
  const { TOP, LEFT } = Astal.WindowAnchor
  const geometry = gdkmonitor.get_geometry()
  const width = Math.max(280, Math.min(408, geometry.width - 16))
  const maxHeight = Math.max(220, Math.min(680, geometry.height - 64))
  const monitorWidth = geometry.width
  const marginLeft = createComputed(() => {
    const rightMost = monitorWidth - width - 8
    const center = audioIconX()
    return center == null ? rightMost : Math.min(Math.max(Math.round(center - width / 2), 8), rightMost)
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
      <box class="audio-surface" orientation={Gtk.Orientation.VERTICAL} widthRequest={width}>
        <scrolledwindow
          class="audio-scroll"
          minContentHeight={240}
          maxContentHeight={maxHeight}
          hscrollbarPolicy={Gtk.PolicyType.NEVER}
          vscrollbarPolicy={Gtk.PolicyType.AUTOMATIC}
        >
          {binding ? <AudioPanelContent binding={binding} /> : <label class="audio-empty-state" label="Audio controls are connecting" />}
        </scrolledwindow>
      </box>
    </window>
  )
}
