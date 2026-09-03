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
// GetActiveProfileName() / SetProfileOverride(s) — no PropertiesChanged
// signal, so we poll GetActiveProfileName after a set + on interval for
// external GUI changes. Left-click launches power-options-gtk (portable).
const PROFILES: [string, string][] = [
    ["Powersave++", "Powersave++"],
    ["Powersave", "Powersave"],
    ["Balanced", "Balanced"],
    ["Performance", "Performance"],
    ["Performance++", "Performance++"],
]

const [profile, setProfile] = createState<string>("Balanced")

let poProxy: Gio.DBusProxy | null = null
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
Gio.DBusProxy.new_for_bus(Gio.BusType.SYSTEM,
    Gio.DBusProxyFlags.NONE, null,
    "io.github.thealexdev23.power_daemon", "/io/github/thealexdev23/power_daemon/control",
    "io.github.thealexdev23.power_daemon.control",
    null, (_source, result) => {
        try {
            poProxy = Gio.DBusProxy.new_for_bus_finish(result)
            refreshPoProfile()
            // Poll for external GUI changes (power-options-gtk) — no PropertiesChanged on this iface
            setInterval(refreshPoProfile, 3000)
        } catch (err) {
            console.error("power-options proxy failed:", err)
        }
    })

function setPowerProfile(name: string) {
    if (poProxy) {
        poProxy.call("SetProfileOverride", new GLib.Variant("(s)", [name]),
            Gio.DBusCallFlags.NONE, -1, null, (_p, res) => {
                try { poProxy!.call_finish(res); setProfile(name) } catch (e) { console.error(e) }
            })
    } else {
        execAsync(["power-daemon-mgr", "set-profile-override", name]).then(() => setProfile(name)).catch(console.error)
    }
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
