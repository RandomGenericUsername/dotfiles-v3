import Gtk from "gi://Gtk?version=4.0"
import Gio from "gi://Gio"
import GLib from "gi://GLib"
import Battery from "gi://AstalBattery"
import { createBinding, createEffect, createState } from "ags"
import { execAsync } from "ags/process"
import { registry } from "../../lib/icon-registry"

const device = Battery.get_default()
const percentage = createBinding(device, "percentage")
const charging = createBinding(device, "charging")
const isPresent = createBinding(device, "is-present")
const timeToFull = createBinding(device, "time-to-full")
const timeToEmpty = createBinding(device, "time-to-empty")

// ── Power profiles — power-options (portable defacto) ─────────────────
// power-options daemon: io.github.thealexdev23.power_daemon /control
// Profile selection is stored through UpdateConfig(profile_override), so it
// survives reboot. Watch the daemon's config directory for changes made by
// other frontends instead of polling its active-profile method.
const PROFILES: [string, string][] = [
    ["Powersave++", "Powersave++"],
    ["Powersave", "Powersave"],
    ["Balanced", "Balanced"],
    ["Performance", "Performance"],
    ["Performance++", "Performance++"],
]

const [profile, setProfile] = createState<string>("Balanced")

let poProxy: Gio.DBusProxy | null = null
let poConfigMonitor: Gio.FileMonitor | null = null
function refreshPoProfile() {
    if (!poProxy) return
    poProxy.call("GetActiveProfileName", null, Gio.DBusCallFlags.NONE, -1, null, (_p, res) => {
        try {
            const ret = poProxy!.call_finish(res) as any
            const name: string = ret?.recursiveUnpack?.()?.[0] ?? ret?.unpack?.()?.[0] ?? "Balanced"
            if (name) setProfile(name)
        } catch {}
    })
}

function updateProfileFromConfig(name: string) {
    if (!poProxy) return
    poProxy.call("GetConfig", null, Gio.DBusCallFlags.NONE, -1, null, (_p, res) => {
        try {
            const ret = poProxy!.call_finish(res) as any
            const raw: string = ret?.recursiveUnpack?.()?.[0] ?? ret?.unpack?.()?.[0]
            const config = JSON.parse(raw)
            config.profile_override = name
            poProxy!.call("UpdateConfig", new GLib.Variant("(s)", [JSON.stringify(config)]),
                Gio.DBusCallFlags.NONE, -1, null, (_updateProxy, updateResult) => {
                    try {
                        poProxy!.call_finish(updateResult)
                        setProfile(config.profile_override)
                    } catch (e) {
                        console.error("power-options config update failed:", e)
                    }
                })
        } catch (e) {
            console.error("power-options config read failed:", e)
        }
    })
}

function watchPowerOptionsConfig() {
    try {
        const directory = Gio.File.new_for_path("/etc/power-options")
        poConfigMonitor = directory.monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, null)
        poConfigMonitor.connect("changed", (_monitor, file, otherFile) => {
            const changed = file?.get_basename?.() === "config.toml"
                || otherFile?.get_basename?.() === "config.toml"
            if (changed) GLib.timeout_add(GLib.PRIORITY_DEFAULT, 100, () => {
                refreshPoProfile()
                return GLib.SOURCE_REMOVE
            })
        })
    } catch (err) {
        console.error("power-options config monitor failed:", err)
    }
}

Gio.DBusProxy.new_for_bus(Gio.BusType.SYSTEM,
    Gio.DBusProxyFlags.NONE, null,
    "io.github.thealexdev23.power_daemon", "/io/github/thealexdev23/power_daemon/control",
    "io.github.thealexdev23.power_daemon.control",
    null, (_source, result) => {
        try {
            poProxy = Gio.DBusProxy.new_for_bus_finish(result)
            refreshPoProfile()
            watchPowerOptionsConfig()
        } catch (err) {
            console.error("power-options proxy failed:", err)
        }
    })

function setPowerProfile(name: string) {
    if (!poProxy) return
    updateProfileFromConfig(name)
}

function getBatteryStateKey(pct: number, chg: boolean): string {
    const level =
        pct < 0.25 ? "0"
        : pct < 0.5 ? "25"
        : pct < 0.75 ? "50"
        : pct < 1 ? "75"
        : "100"
    return chg ? `charging-${level}` : `discharging-${level}`
}

function getBatteryIconPath(): string | null {
    const mappings = registry.getBarMappings("battery")
    if (!mappings) return null
    const stateKey = getBatteryStateKey(percentage(), charging())
    const variant = mappings.states[stateKey]
    if (!variant) return null
    return registry.resolve("battery", variant)
}

function formatSeconds(seconds: number): string {
    const h = Math.floor(seconds / 3600)
    const m = Math.floor((seconds % 3600) / 60)
    if (h > 0) return `${h}h ${m}m`
    return `${m}m`
}

export function BatteryIndicator() {
    let popover: Gtk.Popover | null = null

    return (
        <box
            visible={isPresent((present) => present)}
            tooltipText={(() => {
                const [text, setText] = createState("")
                createEffect(() => {
                    const pct = Math.round(percentage() * 100)
                    const prof = PROFILES.find(([id]) => id === profile())?.[1] ?? profile()
                    let timeLine: string
                    if (charging()) {
                        const ttf = timeToFull()
                        timeLine = ttf > 0 ? `full in ${formatSeconds(ttf)}` : "charging"
                    } else {
                        const tte = timeToEmpty()
                        timeLine = tte > 0 ? `${formatSeconds(tte)} left` : "discharging"
                    }
                    setText(`${pct}% — ${prof}\n${timeLine}`)
                })
                return text
            })()}
        >
            <button
                class="widget battery-widget"
                onClicked={() => {
                    execAsync(["power-options-gtk"]).catch((e) => {
                        console.error("power-options-gtk launch failed:", e)
                    })
                }}
                $={(self) => {
                    const right = Gtk.GestureClick.new()
                    right.set_button(3)
                    right.connect("pressed", () => popover?.popup())
                    self.add_controller(right)
                }}
            >
                <image
                    pixel_size={36}
                    class="widget-icon"
                    $={(self) => {
                        createEffect(() => {
                            self.set_from_file(getBatteryIconPath() ?? "")
                        })
                    }}
                />
            </button>
            <popover $={(self) => (popover = self)}>
                <box orientation={1} spacing={2}>
                    {PROFILES.map(([id, label]) => (
                        <button
                            class={profile((p) => p === id ? "power-profile-item active" : "power-profile-item")}
                            onClicked={() => {
                                setPowerProfile(id)
                                popover?.popdown()
                            }}
                        >
                            <label label={label} />
                        </button>
                    ))}
                </box>
            </popover>
        </box>
    )
}
