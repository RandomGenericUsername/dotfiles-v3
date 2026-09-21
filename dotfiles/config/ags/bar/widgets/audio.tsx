import { Gtk, Gdk } from "ags/gtk4"
import { Accessor, createComputed, createEffect } from "ags"
import { execAsync } from "ags/process"
import { registry } from "../../lib/icon-registry"
import {
  clampVolume,
  defaultMicrophoneMute,
  defaultSpeakerMute,
  defaultSpeakerVolume,
  levelVariant,
  micInUse,
  nudgeDefaultOutputVolume,
  open,
  toggle,
} from "../../audio/state"

/**
 * Audio bar indicators (add-pipewire-audio-control).
 *
 * Two bare SVG glyphs (no glyph font, no pill background — the dotfiles bar
 * convention), resolved through IconRegistry:
 *
 *   OutputIndicator — level-aware `volume` group + live percentage.
 *     Left-click  → open the audio popup under this icon.
 *     Right-click → launch pavucontrol (the doc's conventional GUI).
 *     Scroll      → adjust default output volume.
 *
 *   MicIndicator — `microphone` group (mic-on / mic-off).
 *     Green live dot while any recording stream is active.
 *     Left-click  → open the popup (the Input section lives in the main view).
 *
 * Both are in the runtime icon-contrast guard BAR_GROUPS, so on a light
 * wallpaper their foreground token is retargeted before ITR renders.
 */

function glyph(group: string, variant: string): string {
  return registry.resolve(group, variant) ?? ""
}

export function OutputIndicator() {
  const muted = createComputed(() => defaultSpeakerMute() === true)
  const level = createComputed(() => clampVolume(defaultSpeakerVolume()))
  const variant = createComputed(() => levelVariant(muted(), level()))
  const percent = createComputed(() => Math.round(level() * 100))

  return (
    <button
      class="widget audio-widget"
      tooltipText="Audio — click to open, right-click for pavucontrol, scroll to adjust"
      onClicked={() => toggle("main")}
      $={(self) => {
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
      <box spacing={4}>
        <image
          pixel_size={28}
          class="widget-icon"
          $={(self) => {
            createEffect(() => {
              self.set_from_file(glyph("volume", variant()))
            })
          }}
        />
        <label class="audio-bar-percent" label={percent((p) => `${p}%`)} />
      </box>
    </button>
  )
}

export function MicIndicator() {
  const variant = createComputed(() =>
    defaultMicrophoneMute() === true ? "mic-off" : "mic-on",
  )
  const live: Accessor<boolean> = createComputed(() => micInUse() === true)

  return (
    <button
      class="widget audio-widget mic-widget"
      tooltipText={live((l) =>
        l ? "Microphone — recording in progress" : "Microphone",
      )}
      onClicked={() => open("main")}
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
