import Gdk from "gi://Gdk?version=4.0"
import Gtk from "gi://Gtk?version=4.0"
import Gio from "gi://Gio"
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

// ── Power profiles (power-profiles-daemon, system bus) ─────────────────
// Event-driven: Gio.DBusProxy on net.hadess.PowerProfiles ActiveProfile.
// ppd 0.30 renamed Profile → ActiveProfile.
const PROFILES: [string, string][] = [
    ["performance", "Performance"],
    ["balanced", "Balanced"],
    ["power-saver", "Power Saver"],
]

const [profile, setProfile] = createState<string>("balanced")

Gio.DBusProxy.new_for_bus(Gio.BusType.SYSTEM,
    Gio.DBusProxyFlags.NONE, null,
    "net.hadess.PowerProfiles", "/net/hadess/PowerProfiles", "net.hadess.PowerProfiles",
    null, (_source, result) => {
        try {
            const proxy = Gio.DBusProxy.new_for_bus_finish(result)
            setProfile(proxy.get_cached_property("ActiveProfile")?.unpack() ?? "balanced")
            proxy.connect("g-properties-changed", () => {
                const value = proxy.get_cached_property("ActiveProfile")?.unpack()
                if (value) setProfile(value as string)
            })
        } catch (err) {
            console.error("power-profiles-daemon proxy failed:", err)
        }
    })

function setPowerProfile(name: string) {
    execAsync(["powerprofilesctl", "set", name]).catch(console.error)
}

function cyclePowerProfile() {
    const names = PROFILES.map(([id]) => id)
    const next = names[(names.indexOf(profile()) + 1) % names.length]
    setPowerProfile(next)
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
            tooltipText={percentage((pct) => {
                const head = `${Math.round(pct * 100)}%`
                if (charging()) {
                    const ttf = timeToFull()
                    return `${head}\n${ttf > 0 ? `full in ${formatSeconds(ttf)}` : "charging"}`
                }
                const tte = timeToEmpty()
                return `${head}\n${tte > 0 ? `${formatSeconds(tte)} left` : "discharging"}`
            })}
        >
            <button
                class="widget battery-widget"
                onClicked={() => {
                    execAsync(["rog-control-center"]).catch((e) => {
                        console.error("rog-control-center launch failed:", e)
                        execAsync(["powerprofilesctl", "set", "balanced"]).catch(() => { })
                    })
                }}
                $={(self) => {
                    const gesture = Gtk.GestureClick.new()
                    gesture.set_button(0)
                    gesture.connect("pressed", (g) => {
                        const ev = g.get_current_event() as Gdk.ButtonEvent | null
                        if (!ev || ev.get_button() !== 3) return
                        if (ev.get_modifier_state() & Gdk.ModifierType.SHIFT_MASK) {
                            cyclePowerProfile()
                        } else {
                            popover?.popup()
                        }
                    })
                    self.add_controller(gesture)
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
