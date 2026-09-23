import { Gtk, Gdk } from "ags/gtk4"
import { Accessor, createComputed, createEffect } from "ags"
import { execAsync } from "ags/process"
import { registry } from "../../lib/icon-registry"
import {
  clampVolume,
  defaultMicrophone,
  defaultSpeaker,
  levelVariant,
  micInUse,
  nodeOf,
  nudgeDefaultOutputVolume,
  open,
  setAudioIconX,
  toggle,
  useEndpointEpoch,
} from "../../audio/state"

/**
 * Audio bar indicators (add-pipewire-audio-control).
 *
 * Two bare SVG glyphs (no glyph font, no pill background, no percentage
 * label — the dotfiles bar convention), resolved through IconRegistry:
 *
 *   OutputIndicator — level-aware `volume` group. Always visible.
 *     Left-click  → open the audio popup under this icon.
 *     Right-click → launch pavucontrol (the doc's conventional GUI).
 *     Scroll      → adjust default output volume.
 *
 *   MicIndicator — `microphone` group (mic-on / mic-off). Visible ONLY while
 *     a recording stream is active, carrying the green live dot.
 *     Left-click  → open the popup (the Input section lives in the main view).
 *
 * Both are in the runtime icon-contrast guard BAR_GROUPS, so on a light
 * wallpaper their foreground token is retargeted before ITR renders.
 *
 * Follower anchoring mirrors the settings panel: a motion controller records
 * the pointer x (surface coords == monitor coords) without claiming clicks,
 * and the click stores it so the popup can anchor beneath the icon.
 */

function glyph(group: string, variant: string): string {
  return registry.resolve(group, variant) ?? ""
}

// Last pointer x over either audio indicator; re-recorded on every hover.
let lastIconX: number | null = null

function trackIconX(self: Gtk.Widget) {
  const motion = new Gtk.EventControllerMotion()
  motion.connect("motion", () => {
    const event = motion.get_current_event()
    if (!event) return
    // Gdk.Event.get_position() -> [ok, x, y] in gjs.
    const pos = event.get_position() as unknown
    if (Array.isArray(pos) && pos.length >= 3) {
      const x = Number(pos[1])
      if (Number.isFinite(x) && x > 0) lastIconX = x
    }
  })
  self.add_controller(motion)
}

function recordIconX() {
  if (lastIconX !== null) setAudioIconX(lastIconX)
}

export function OutputIndicator() {
  const spkEpoch = useEndpointEpoch(defaultSpeaker)
  //: Read the LIVE node props directly — NOT through defaultSpeakerVolume() /
  //: defaultSpeakerMute(), which memoize independently on list membership and
  //: stay stale even when this epoch invalidates us (measured: node 0.85 while
  //: the accessor still said 0.75). GObject property reads are always live.
  const muted = createComputed(() => {
    spkEpoch()
    return nodeOf(defaultSpeaker())?.mute === true
  })
  const level = createComputed(() => {
    spkEpoch()
    return clampVolume(nodeOf(defaultSpeaker())?.volume ?? 0)
  })
  const variant = createComputed(() => levelVariant(muted(), level()))

  return (
    <button
      class="widget audio-widget"
      tooltipText="Audio — click to open, right-click for pavucontrol, scroll to adjust"
      onClicked={() => {
        recordIconX()
        toggle("main")
      }}
      $={(self) => {
        trackIconX(self)
        const secondary = new Gtk.GestureClick({ button: Gdk.BUTTON_SECONDARY })
        secondary.connect("pressed", () =>
          execAsync(["pavucontrol"]).catch((e) => console.error("pavucontrol:", e)),
        )
        self.add_controller(secondary)

        const scroll = new Gtk.EventControllerScroll()
        scroll.set_flags(Gtk.EventControllerScrollFlags.VERTICAL)
        scroll.connect("scroll", (_c, _dx, dy) => {
          nudgeDefaultOutputVolume(dy < 0 ? 0.05 : -0.05)
          return true
        })
        self.add_controller(scroll)
      }}
    >
      <image
        pixel_size={28}
        class="widget-icon"
        $={(self) => {
          createEffect(() => {
            self.set_from_file(glyph("volume", variant()))
          })
        }}
      />
    </button>
  )
}

export function MicIndicator() {
  const micEpoch = useEndpointEpoch(defaultMicrophone)
  const variant = createComputed(() => {
    micEpoch()
    return nodeOf(defaultMicrophone())?.mute === true ? "mic-off" : "mic-on"
  })
  const live: Accessor<boolean> = createComputed(() => micInUse() === true)

  return (
    <button
      class="widget audio-widget mic-widget"
      visible={live}
      tooltipText="Microphone — recording in progress"
      onClicked={() => {
        recordIconX()
        open("main")
      }}
      $={(self) => {
        trackIconX(self)
      }}
    >
      <box class="audio-mic-wrap">
        <image
          pixel_size={28}
          class="widget-icon"
          $={(self) => {
            createEffect(() => {
              self.set_from_file(glyph("microphone", variant()))
            })
          }}
        />
        <box
          class="audio-live-dot"
          visible={live}
          valign={Gtk.Align.START}
          halign={Gtk.Align.END}
        />
      </box>
    </button>
  )
}
