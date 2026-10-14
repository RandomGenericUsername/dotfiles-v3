import { Gtk, Gdk } from "ags/gtk4"
import { createComputed, createEffect } from "ags"
import { execAsync } from "ags/process"
import { iconByStateKey, resolveIcon } from "../../kit/icon"
import { applyIconSource } from "../../kit/widget"
import {
  projectBarIndicators,
  volumeStateKey,
  microphoneStateKey,
  type BarIndicatorState,
} from "../../audio/presentation/bar-indicators"
import { clampVolume } from "../../audio/presentation/levels"
import { open, setAudioIconX, toggle } from "../../audio/ui-state"
import type { AudioPanelBinding } from "../../audio/AudioPopup"

/**
 * Audio bar indicators (add-pipewire-audio-control; migrated to the composition
 * binding by finish-audio-bar-migration).
 *
 * Two bare SVG glyphs (no glyph font, no pill background, no percentage
 * label — the dotfiles bar convention), resolved through IconRegistry:
 *
 *   OutputIndicator — level-aware `volume` group. Always visible.
 *     Left-click  → toggle the audio popup under this icon.
 *     Right-click → launch pavucontrol (the doc's conventional GUI).
 *     Scroll      → adjust the preferred output volume.
 *
 *   MicIndicator — `microphone` group (mic-on / mic-off). Visible ONLY while
 *     a recording stream is active, carrying the green live dot.
 *     Left-click  → open the popup (the Input section lives in the main view).
 *
 * BOTH are thin renderers of `projectBarIndicators(binding.model())`: the state
 * comes from the same composition root the panel uses, so the bar glyph and the
 * panel it opens can never disagree. The widget owns no AstalWp access and no
 * threshold table — those live in the domain adapter and the pure projection.
 *
 * Follower anchoring mirrors the settings panel: a motion controller records
 * the pointer x (surface coords == monitor coords) without claiming clicks,
 * and the click stores it so the popup can anchor beneath the icon.
 */

/**
 * The bar's two icons, as state-key refs (spine AD-7). Code emits the state key
 * (`volume-medium`, `microphone-mic-off`); the manifest's `bar_mappings.states`
 * maps it to a variant and the registry maps the variant to art. A key with no
 * table entry blanks rather than throwing.
 */
const outputIcon = iconByStateKey("volume", (s: BarIndicatorState) =>
  volumeStateKey(s.output.muted, s.output.level),
)
const micIcon = iconByStateKey("microphone", (s: BarIndicatorState) =>
  microphoneStateKey(s.mic.variant),
)

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

export function OutputIndicator({ binding }: { binding: AudioPanelBinding }) {
  const indicators = createComputed(() => projectBarIndicators(binding.model()))

  return (
    <button
      class="widget audio-widget"
      tooltipText="Audio — click to open, right-click for pavucontrol, scroll to adjust"
      onClicked={() => {
        recordIconX()
        toggle()
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
          // Dispatch the SAME selected-output action the panel and Settings use.
          const model = binding.model()
          const id = model.preferredOutputId
          if (id === null) return true
          const current = clampVolume(model.preferredOutput?.volume.level ?? 0)
          const next = clampVolume(current + (dy < 0 ? 0.05 : -0.05))
          binding.actions.setOutputVolume(id, next * 100)
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
            applyIconSource(self, resolveIcon(outputIcon, indicators()))
          })
        }}
      />
    </button>
  )
}

export function MicIndicator(
  { binding, showLiveDotRing = true }: { binding: AudioPanelBinding; showLiveDotRing?: boolean },
) {
  const indicators = createComputed(() => projectBarIndicators(binding.model()))
  const live = createComputed(() => indicators().mic.live)

  return (
    <button
      class="widget audio-widget mic-widget"
      visible={live}
      tooltipText="Microphone — recording in progress"
      onClicked={() => {
        recordIconX()
        open()
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
              applyIconSource(self, resolveIcon(micIcon, indicators()))
            })
          }}
        />
        <box
          class={showLiveDotRing ? "audio-live-dot bar-live-dot-ring" : "audio-live-dot"}
          visible={live}
          valign={Gtk.Align.START}
          halign={Gtk.Align.END}
        />
      </box>
    </button>
  )
}
