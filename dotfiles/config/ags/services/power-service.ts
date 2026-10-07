import Gio from "gi://Gio"
import GLib from "gi://GLib"
import { createComputed, createState } from "ags"
// TYPE-ONLY import, deliberately. The service owns the D-Bus proxy and the
// state; the profile SHAPE is a pure presentation type, so this file names it
// without pulling the view layer into the service at runtime.
import type { PowerProfile } from "../components/battery/presentation"

/**
 * power-options (portable defacto) service.
 *
 * The daemon is `io.github.thealexdev23.power_daemon`, object
 * `/io/github/thealexdev23/power_daemon/control`, interface
 * `io.github.thealexdev23.power_daemon.control`.
 *
 * WHY THIS FILE EXISTS AT ALL. All of this used to live at module scope inside
 * `bar/widgets/battery.tsx`, built at WIDGET CONSTRUCTION time and never
 * disposed: the D-Bus proxy was created once per construction of the widget
 * module and the `/etc/power-options` directory monitor was installed for the
 * life of the process with no teardown path. A status-bar widget is not the
 * owner of a daemon subscription — it is a VIEW of one. Moving the proxy and
 * the monitor here makes the bar widget a consumer of a service, matching how
 * `services/wifi-service.ts` owns the NetworkManager side and
 * `components/wifi/state.ts` only holds view state.
 *
 * THE PROFILE LIST COMES FROM THE DAEMON, NOT A HARDCODED ARRAY. The panel
 * needs the profiles the daemon actually offers, each with its stable
 * `base_profile` tier, so `GetProfilesInfo` is the read. It returns a single
 * JSON string:
 *
 *     { "active_profile": <index>,
 *       "profiles": [ { "profile_name": <string>, "base_profile": <string> }, … ] }
 *
 * `active_profile` is an INDEX into `profiles[]` — unambiguous and
 * rename-proof, unlike matching a name. Reading both in one call means the
 * list and the selection can never be a payload apart.
 *
 * Profile selection is stored through `UpdateConfig(profile_override)` rather
 * than an "activate this profile" method, which is why the write path is
 * read-modify-write of the daemon's whole config document. That is the daemon's
 * own API; we are not choosing a worse one.
 *
 * EXTERNAL CHANGES ARE WATCHED, NOT POLLED. The active profile and the profile
 * list are re-read when `/etc/power-options/config.toml` changes, because that
 * file is how every OTHER frontend (power-options-gtk included) records a
 * change — including `CreateProfile` / `RemoveProfile` / `UpdateProfileName`.
 */

/** The daemon's bus name, object path and control interface. */
const BUS_NAME = "io.github.thealexdev23.power_daemon"
const OBJECT_PATH = "/io/github/thealexdev23/power_daemon/control"
const CONTROL_IFACE = "io.github.thealexdev23.power_daemon.control"

/** The daemon's config directory, watched for changes made by other frontends. */
const CONFIG_DIR = "/etc/power-options"
const CONFIG_FILE = "config.toml"

/**
 * The profiles the daemon offers, in the daemon's own order. Empty until the
 * first `GetProfilesInfo` reply; the panel renders its declared modes
 * regardless and marks nothing selected until then.
 */
const [powerProfiles, setPowerProfiles] = createState<readonly PowerProfile[]>([])

export { powerProfiles }

/**
 * The index into `powerProfiles` the daemon reports as active, or `-1` before
 * the first reply. An index rather than a name: the name is the user's and is
 * editable, while the index is exactly what the daemon said.
 */
const [activeProfileIndex, setActiveProfileIndex] = createState<number>(-1)

export { activeProfileIndex }

/**
 * The active profile's `profile_name`, or `null` before the daemon answers.
 *
 * Derived from the two states above rather than stored separately, so the name
 * and the index can never disagree. Kept as an accessor because the bar
 * widget's tooltip prints it (`82% — Performance++`); `null` drops that
 * segment rather than printing a boot default that looks like a real reading.
 */
export const activeProfile = createComputed<string | null>(() => {
  const profiles = powerProfiles()
  const index = activeProfileIndex()
  return index >= 0 && index < profiles.length ? profiles[index].name : null
})

/** Whether the daemon has answered with a usable profile list. Gates sensitivity. */
const [powerReady, setPowerReady] = createState(false)

export { powerReady }

let poProxy: Gio.DBusProxy | null = null
let poConfigMonitor: Gio.FileMonitor | null = null

/**
 * Unpack a single-string D-Bus reply.
 *
 * `recursiveUnpack` is the modern accessor and `unpack` the older one; which
 * one GJS exposes has moved around between GLib versions, so both are tried
 * rather than betting on one and rendering nothing.
 */
function unpackString(ret: unknown): string | null {
  const reply = ret as {
    recursiveUnpack?: () => unknown[]
    unpack?: () => unknown[]
  } | null
  if (!reply) return null
  for (const unpack of [reply.recursiveUnpack, reply.unpack]) {
    if (typeof unpack !== "function") continue
    try {
      const value = unpack.call(reply)?.[0]
      if (typeof value === "string" && value !== "") return value
    } catch {
      /* try the next accessor */
    }
  }
  return null
}

interface RawProfilesInfo {
  active_profile?: unknown
  profiles?: unknown
}

/**
 * Parse `GetProfilesInfo`'s JSON into the shape the panel consumes.
 *
 * Defensive on purpose: this crosses a process boundary, carries fields the
 * panel does not model, and is produced by a daemon that can be upgraded
 * independently. A malformed document returns `null` (the caller keeps the
 * last good read) rather than half-populating the rail. A missing
 * `profile_name` becomes `""` and a missing `base_profile` becomes `""`,
 * which resolves to the labelled fallback rather than crashing.
 */
export function parseProfilesInfo(
  raw: string,
): { activeIndex: number; profiles: PowerProfile[] } | null {
  let data: RawProfilesInfo
  try {
    data = JSON.parse(raw) as RawProfilesInfo
  } catch {
    return null
  }
  if (data === null || typeof data !== "object" || !Array.isArray(data.profiles)) {
    return null
  }
  const profiles: PowerProfile[] = []
  for (const entry of data.profiles) {
    if (entry === null || typeof entry !== "object") continue
    const record = entry as Record<string, unknown>
    profiles.push({
      name: typeof record.profile_name === "string" ? record.profile_name : "",
      tier: typeof record.base_profile === "string" ? record.base_profile : "",
    })
  }
  const rawIndex = data.active_profile
  const activeIndex =
    typeof rawIndex === "number" && Number.isInteger(rawIndex) ? rawIndex : -1
  return { activeIndex, profiles }
}

/**
 * Re-read the daemon's profile list and active index in one call.
 *
 * On success the two states are set together, so the list and the selection
 * are always the same snapshot. On failure the last good read is kept (a
 * transient D-Bus hiccup must not blank a working panel) and `powerReady`
 * stays where it was; it only becomes true on a usable reply.
 */
function refreshPowerProfiles(): void {
  const proxy = poProxy
  if (!proxy) return
  proxy.call(
    "GetProfilesInfo",
    null,
    Gio.DBusCallFlags.NONE,
    -1,
    null,
    (p, res) => {
      try {
        // `p` is the source object of the callback and is typed nullable; the
        // closure captured `proxy` for the call itself, so the guard is only
        // about the REPLY receiver going away (proxy disposed mid-flight).
        if (!p) return
        const raw = unpackString(p.call_finish(res))
        if (raw === null) return
        const parsed = parseProfilesInfo(raw)
        if (parsed === null) return
        setPowerProfiles(parsed.profiles)
        setActiveProfileIndex(parsed.activeIndex)
        setPowerReady(true)
      } catch {
        /* daemon restarting or profile momentarily unreadable — keep last good */
      }
    },
  )
}

function updateProfileFromConfig(name: string): void {
  const proxy = poProxy
  if (!proxy) return
  proxy.call(
    "GetConfig",
    null,
    Gio.DBusCallFlags.NONE,
    -1,
    null,
    (p, res) => {
      let raw: string | null = null
      try {
        if (!p) return
        raw = unpackString(p.call_finish(res))
      } catch (e) {
        console.error("power-service: config read failed:", e)
        return
      }
      if (raw === null) return
      let config: Record<string, unknown>
      try {
        config = JSON.parse(raw) as Record<string, unknown>
      } catch (e) {
        console.error("power-service: config is not JSON:", e)
        return
      }
      config.profile_override = name
      try {
        proxy.call(
          "UpdateConfig",
          new GLib.Variant("(s)", [JSON.stringify(config)]),
          Gio.DBusCallFlags.NONE,
          -1,
          null,
          (up, updateResult) => {
            try {
              if (!up) return
              up.call_finish(updateResult)
              // Re-read from the daemon rather than optimistically moving the
              // selection: the panel follows `active_profile`, not a local
              // guess, so the accent only moves once the daemon agrees.
              refreshPowerProfiles()
            } catch (e) {
              console.error("power-service: config update failed:", e)
            }
          },
        )
      } catch (e) {
        console.error("power-service: UpdateConfig call failed:", e)
      }
    },
  )
}

function watchPowerOptionsConfig(): void {
  if (poConfigMonitor !== null) return
  try {
    const directory = Gio.File.new_for_path(CONFIG_DIR)
    poConfigMonitor = directory.monitor_directory(
      Gio.FileMonitorFlags.WATCH_MOVES,
      null,
    )
    poConfigMonitor.connect("changed", (_monitor, file, otherFile) => {
      const changed =
        file?.get_basename?.() === CONFIG_FILE ||
        otherFile?.get_basename?.() === CONFIG_FILE
      if (!changed) return
      // Editors and the daemon write the document as a sequence of operations;
      // a short debounce means we read a settled file instead of a half-written
      // one, and the read is a single call so a dropped event self-corrects on
      // the next change rather than leaving the panel permanently wrong.
      GLib.timeout_add(GLib.PRIORITY_DEFAULT, 100, () => {
        refreshPowerProfiles()
        return GLib.SOURCE_REMOVE
      })
    })
  } catch (err) {
    console.error("power-service: config monitor failed:", err)
  }
}

/**
 * Select a power profile by its `profile_name`.
 *
 * The name is what `profile_override` stores; it is user-editable, which is
 * exactly why the panel resolves a click to a name only at the last moment
 * rather than keying anything off it.
 *
 * No-ops when the proxy is absent rather than queueing: without the daemon
 * there is nothing to write to, and remembering a selection the daemon never
 * received would show a selection the system is not actually in.
 */
export function setPowerProfile(name: string): void {
  if (!poProxy) return
  updateProfileFromConfig(name)
}

// ── Bootstrap ────────────────────────────────────────────────────────────

Gio.DBusProxy.new_for_bus(
  Gio.BusType.SYSTEM,
  Gio.DBusProxyFlags.NONE,
  null,
  BUS_NAME,
  OBJECT_PATH,
  CONTROL_IFACE,
  null,
  (_source, result) => {
    try {
      poProxy = Gio.DBusProxy.new_for_bus_finish(result)
      refreshPowerProfiles()
      watchPowerOptionsConfig()
    } catch (err) {
      // No daemon (desktop without power-options). The panel stays usable: the
      // declared mode cells render insensitive, nothing is highlighted, and
      // `powerReady` stays false so they cannot silently do nothing.
      console.error("power-service: proxy failed:", err)
      setPowerReady(false)
    }
  },
)
