import { createComputed } from "ags"
import { activeView, panelVisible } from "../state"
import { WifiContent } from "../../components/wifi/WifiContent"

/**
 * The Wi-Fi subview BODY only.
 *
 * The header (back arrow, title, power switch) used to be rendered here, which
 * put it INSIDE the panel's scrolled window — so it scrolled away with the
 * content, unlike the tray popup where the header is a sibling of the
 * scrolledwindow and stays pinned. It now lives in SubviewHeader, rendered as
 * a sibling of the scrolled window. See SubviewHeader.tsx.
 */
export function WifiView() {
  return (
    /* No `spacing`: the pinned header above supplies the separation, and this
       box is the first thing inside the scrolled viewport, so extra air here
       would only pad the top of the scroll area. */
    <box orientation={1}>
      <WifiContent
        visible={createComputed(
          () => panelVisible() && activeView() === "wifi",
        )}
      />
    </box>
  )
}
