import { createState } from "ags"

/**
 * UI-local audio state (extracted from the legacy `audio/state.ts`).
 *
 * These are SURFACE concerns — whether the popup is open, and where its follower
 * anchor sits — not audio-graph state. This module depends only on `ags`
 * (createState), so importing it never drags in AstalWp, Gio, MPRIS, or a live
 * session bus, and the pure test suite can load it.
 *
 * The audio GRAPH is observed through the composition binding
 * (`audio/composition.ts` → `AudioPanelBinding.model`); nothing here reads or
 * re-reads it. The legacy `open()` used to call `invalidateDefaultEndpoint()` /
 * `refreshStreamTargets()` to force a re-read — that is the runtime's job now,
 * because the session is event-fed; the re-read is deliberately not carried over.
 *
 * `activeSection`, `viewEpoch`, `showOutputDevices`, `showInputDevices`, `back`
 * and the `AudioSection` type lived beside these in the legacy module but had no
 * consumer after the panel redesign (the popup navigates with its own views), so
 * they are deleted with the module rather than moved here.
 */

const [popupVisible, setPopupVisible] = createState(false)

//: Follower anchor: surface x-centre of the bar indicator that opened the popup
//: (recorded by a motion controller on the buttons, same pattern as the settings
//: panel's iconCenterX).
const [audioIconX, setAudioIconX] = createState<number | null>(null)

export { popupVisible, audioIconX, setAudioIconX }

/** Open the popup. */
export function open(): void {
  setPopupVisible(true)
}

/** Close the popup. */
export function close(): void {
  setPopupVisible(false)
}

/** Toggle the popup. */
export function toggle(): void {
  if (popupVisible()) close()
  else open()
}
