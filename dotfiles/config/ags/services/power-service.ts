import Gio from "gi://Gio"
import GLib from "gi://GLib"
import { createState } from "ags"
// TYPE-ONLY import, deliberately. It was a value import, and the only value it
// pulled was `POWER_PROFILE_ORDER`, for an exported `isProfileAvailable()`
// predicate that nothing called — the panel renders all five rows from the
// order itself and gates their sensitivity on `powerReady`. That dead predicate
// was the sole reason this service imported `components/**` at runtime: a
// service reaching up into the view layer for a list the view already owns is
// an inverted dependency, and one more consumer of it would have cemented it.
import type { PowerProfileId } from "../components/battery/presentation"

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
 * Profile selection is stored through `UpdateConfig(profile_override)` rather
 * than an "activate this profile" method, which is why the write path is
 * read-modify-write of the daemon's whole config document. That is the daemon's
 * own API; we are not choosing a worse one.
 *
 * EXTERNAL CHANGES ARE WATCHED, NOT POLLED. The active profile is re-read when
 * `/etc/power-options/config.toml` changes, because that file is how every
 * OTHER frontend (power-options-gtk included) records a change. Polling
 * `GetActiveProfileName` on a timer would burn wakeups to learn about an event
 * we can be told about.
 */

/** The daemon's bus name, object path and control interface. */
const BUS_NAME = "io.github.thealexdev23.power_daemon"
const OBJECT_PATH = "/io/github/thealexdev23/power_daemon/control"
const CONTROL_IFACE = "io.github.thealexdev23.power_daemon.control"

/** The daemon's config directory, watched for changes made by other frontends. */
const CONFIG_DIR = "/etc/power-options"
const CONFIG_FILE = "config.toml"

/**
 * The profile in effect, as the daemon SPELLS it (`Powersave++`, `performance`,
 * …). Not normalised: `isActiveProfile` compares case-insensitively and is the
 * single place that decides what "the same profile" means, so normalising here
 * too would be a second definition of the same rule.
 *
 * `null` — not `"Balanced"` — is the initial value. A boot default that looks
 * like a real reading is a lie the panel would render as a selected row before
 * the first bus reply lands; `null` means "nothing is highlighted yet", which
 * is what `isActiveProfile` is specified to do for an unknown current.
 */
const [activeProfile, setActiveProfile] = createState<string | null>(null)

export { activeProfile }

/** Whether the proxy has ever resolved. Gates the rows' sensitivity. */
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

function refreshPoProfile(): void {
  const proxy = poProxy
  if (!proxy) return
  proxy.call(
    "GetActiveProfileName",
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
        const name = unpackString(p.call_finish(res))
        if (name) setActiveProfile(name)
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
        console.error("power-service: config is not valid JSON:", e)
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
              setActiveProfile(name)
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
        refreshPoProfile()
        return GLib.SOURCE_REMOVE
      })
    })
  } catch (err) {
    console.error("power-service: config monitor failed:", err)
  }
}

/**
 * Select a power profile.
 *
 * No-ops when the proxy is absent rather than queueing: without the daemon
 * there is nothing to write to, and remembering a selection the daemon never
 * received would show a row highlighted that the system is not actually in.
 */
export function setPowerProfile(id: PowerProfileId): void {
  if (!poProxy) return
  updateProfileFromConfig(id)
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
      refreshPoProfile()
      watchPowerOptionsConfig()
    } catch (err) {
      // No daemon (desktop without power-options). The panel stays usable: rows
      // render from the static order, nothing is highlighted, `powerReady`
      // stays false so they are insensitive rather than lying about success.
      console.error("power-service: proxy failed:", err)
    } finally {
      setPowerReady(poProxy !== null)
    }
  },
)
