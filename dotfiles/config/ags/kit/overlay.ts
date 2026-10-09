/**
 * The overlay coordinator — one bar overlay open at a time, centrally.
 *
 * Today every widget drives mutual exclusion itself (the battery widget closes
 * the settings panel and the Wi-Fi popup; the settings panel's `open()` closes
 * three popups; `app.tsx`'s `popup-close` handler enumerates all of them). That
 * is the same policy written in N places, and it is why adding a surface means
 * editing several files. This owns it once.
 *
 * The kit is domain-agnostic: a domain registers its overlay's doors
 * (`isOpen`/`open`/`close`) in `overlays.ts`, and any widget opens it through
 * `overlays.toggle(id, anchorX)` / `overlays.open(id, anchorX)`.
 *
 * Follower anchoring rides along: the widget's primary receives the pointer x
 * the renderer recorded, and passes it here; the overlay's own `open` writes it
 * to its anchor state. The coordinator never knows what an anchor is.
 */
export interface OverlayEntry {
  readonly id: string
  readonly isOpen: () => boolean
  /** Open the overlay; `anchorX` is the bar-icon x-centre, or null. */
  readonly open: (anchorX: number | null) => void
  readonly close: () => void
}

const entries = new Map<string, OverlayEntry>()

function closeOthers(id: string): void {
  for (const [otherId, entry] of entries) {
    if (otherId !== id && entry.isOpen()) entry.close()
  }
}

export const overlays = {
  register(entry: OverlayEntry): void {
    entries.set(entry.id, entry)
  },

  isOpen(id: string): boolean {
    return entries.get(id)?.isOpen() ?? false
  },

  /** Open `id` and close every other open overlay first. */
  open(id: string, anchorX: number | null = null): void {
    const entry = entries.get(id)
    if (!entry) return
    closeOthers(id)
    entry.open(anchorX)
  },

  close(id: string): void {
    entries.get(id)?.close()
  },

  /** Open if closed, close if open. */
  toggle(id: string, anchorX: number | null = null): void {
    if (overlays.isOpen(id)) overlays.close(id)
    else overlays.open(id, anchorX)
  },

  /** Dismiss everything — the single path for Esc / `ags request popup-close`. */
  closeAll(): void {
    for (const entry of entries.values()) {
      if (entry.isOpen()) entry.close()
    }
  },
}
