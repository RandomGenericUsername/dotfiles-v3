import { Gtk } from "ags/gtk4"
import { createComputed, createEffect } from "ags"
import { execAsync } from "ags/process"
import { iconByStateKey, resolveIcon } from "ags-platform/adapters/icon"
import { applyIconSource } from "../../kit/widget"
import type { DescriptorSpec, RichWidgetSpec } from "../../kit/widget"
import { overlays } from "../../kit/overlay"
import {
  projectBarIndicators,
  volumeStateKey,
  microphoneStateKey,
  type BarIndicatorState,
} from "../../audio/presentation/bar-indicators"
import { clampVolume } from "../../audio/presentation/levels"
import type { AudioPanelBinding } from "../../audio/AudioPopup"

/**
 * Audio bar indicators (add-pipewire-audio-control; migrated to the composition
 * binding by finish-audio-bar-migration; moved onto the shapes by this change).
 *
 * Two bare SVG glyphs (no glyph font, no pill background, no percentage label —
 * the dotfiles bar convention), resolved through IconRegistry:
 *
 *   OutputIndicator — level-aware `volume` group, a `DescriptorSpec`.
 *     Left-click  → toggle the audio popup under this icon.
 *     Right-click → launch pavucontrol (the doc's conventional GUI).
 *     Scroll      → adjust the preferred output volume.
 *
 *   MicIndicator — `microphone` group (mic-on / mic-off), visible ONLY while a
 *     recording stream is active, carrying the green live dot. It is a
 *     `RichWidgetSpec` because the live-dot badge is content the descriptor
 *     vocabulary (icon + label) cannot express; doc 101 §5 lists it as a
 *     descriptor, but preserving the badge wins.
 *     Left-click  → open the popup (the Input section lives in the main view).
 *
 * BOTH are thin renderers of `projectBarIndicators(binding.model())`: the state
 * comes from the same composition root the panel uses, so the bar glyph and the
 * panel it opens can never disagree. The widget owns no AstalWp access and no
 * threshold table — those live in the domain adapter and the pure projection.
 * The shared shell owns the root, the tooltip, the anchor record and the
 * gestures.
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

export function createAudioOutputWidget(
  binding: AudioPanelBinding,
): DescriptorSpec<BarIndicatorState> {
  const indicators = createComputed(() => projectBarIndicators(binding.model()))

  return {
    id: "audio-output",
    read: () => indicators(),
    class: "audio-widget",
    tooltip: () => "Audio — click to open, right-click for pavucontrol, scroll to adjust",
    icon: outputIcon,
    // Left click opens the popup under this icon; the coordinator closes the
    // other overlays first and stores the pointer x.
    primary: (_s, anchorX) => overlays.toggle("audio", anchorX),
    secondary: () => {
      execAsync(["pavucontrol"]).catch((e) => console.error("pavucontrol:", e))
    },
    scroll: (_s, dy) => {
      // Dispatch the SAME selected-output action the panel and Settings use.
      const model = binding.model()
      const id = model.preferredOutputId
      if (id === null) return
      const current = clampVolume(model.preferredOutput?.volume.level ?? 0)
      const next = clampVolume(current + (dy < 0 ? 0.05 : -0.05))
      binding.actions.setOutputVolume(id, next * 100)
    },
  }
}

export function createAudioMicWidget(
  binding: AudioPanelBinding,
  showLiveDotRing = true,
): RichWidgetSpec<BarIndicatorState> {
  const indicators = createComputed(() => projectBarIndicators(binding.model()))

  return {
    id: "audio-mic",
    read: () => indicators(),
    class: "audio-widget mic-widget",
    visible: (s) => s.mic.live,
    tooltip: () => "Microphone — recording in progress",
    content: () => (
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
          valign={Gtk.Align.START}
          halign={Gtk.Align.END}
        />
      </box>
    ),
    // The Input section lives in the main view, so the mic opens (never toggles)
    // the popup; the coordinator closes the other overlays and stores the anchor.
    primary: (_s, anchorX) => overlays.open("audio", anchorX),
  }
}
