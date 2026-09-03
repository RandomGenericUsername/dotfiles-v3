import Gio from "gi://Gio"
import Battery from "gi://AstalBattery"
import { createBinding, createEffect, createState, onCleanup } from "ags"
import { execAsync } from "ags/process"
import { registry } from "../../lib/icon-registry"

const device = Battery.get_default()
const percentage = createBinding(device, "percentage")
const charging = createBinding(device, "charging")
const isPresent = createBinding(device, "is-present")
const timeToFull = createBinding(device, "time-to-full")

// ── Power profiles (power-profiles-daemon, system bus) ─────────────────
// Event-driven: a Gio.DBusProxy subscribes to PropertiesChanged, so profile
// switches from ANY client (rog-control-center, powerprofilesctl, other
// widgets) update the menu without polling.
const PROFILES: [string, string][] = [
    ["performance", "Performance"],
    ["balanced", "Balanced"],
    ["power-saver", "Power Saver"],
]

const [profile, setProfile] = createState<string>("balanced")

const ppProxy = Gio.DBusProxy.new_for_bus(Gio.BusType.SYSTEM,
    Gio.DBusProxyFlags.NONE, null,
    "net.hadess.PowerProfiles", "/net/hadess/PowerProfiles", "net.hadess.PowerProfiles",
    null, (_source, result) => {
        try {
            const proxy = Gio.DBusProxy.new_for_bus_finish(result)
            setProfile(proxy.get_cached_property("ActiveProfile")?.unpack() ?? "balanced")
            proxy.connect("g-properties-changed", (_p, changed: Gio.DBusPropertyInfo) => {
                const value = proxy.get_cached_property("ActiveProfile")?.unpack()
                if (value) setProfile(value as string)
                void changed
            })
        } catch (err) {
            console.error("power-profiles-daemon proxy failed:", err)
        }
    })

function setPowerProfile(name: string) {
    execAsync(["powerprofilesctl", "set", name]).catch(console.error)
}

function cyclePowerProfile() {
    const current = profile()
    const names = PROFILES.map(([id]) => id)
    const next = names[(names.indexOf(current) + 1) % names.length]
    setPowerProfile(next)
}

function getBatteryIconPath(): string | null {
    const mappings = registry.getBarMappings("battery")
    if (!mappings) return null
    const stateKey = getBatteryStateKey(percentage(), charging())
    const variant = mappings.states[stateKey]
    if (!variant) return null
    return registry.resolve("battery", variant)
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

function formatSeconds(seconds: number): string {
    const h = Math.floor(seconds / 3600)
    const m = Math.floor((seconds % 3600) / 60)
    if (h > 0) return `${h}h ${m}m`
    return `${m}m`
}

// ── Widget ──────────────────────────────────────────────────────────────

export function BatteryIndicator() {
    const [menuOpen, setMenuOpen] = createState(false)

    return (
        <box>
            <button
                class="widget battery-widget"
                visible={isPresent((present) => present)}
                tooltipText={createBinding(device, "percentage")((pct) => {
                    const parts = [`${Math.round(pct * 100)}%`]
                    if (charging()) {
                        const ttf = timeToFull()
                        if (ttf > 0) parts.push(`full in ${formatSeconds(ttf)}`)
                        else parts.push("charging")
                    }
                    return parts.join(" — ")
                })}
                onClicked={(self, event) => {
                    const button = event.get_button()
                    const shift = event.get_modifier_state() & 4 // Gdk.SHIFT_MASK
                    if (button === 1) {
                        execAsync(["rog-control-center"]).catch(console.error)
                    } else if (button === 3 && shift) {
                        cyclePowerProfile()
                    } else if (button === 3) {
                        setMenuOpen(!menuOpen())
                    }
                    void self
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
                <popover visible={menuOpen()} autohide onClosed={() => setMenuOpen(false)}>
                    <box orientation={1} spacing={2}>
                        {PROFILES.map(([id, label]) => (
                            <button
                                class={profile((p) => p === id ? "power-profile-item active" : "power-profile-item")}
                                onClicked={() => {
                                    setPowerProfile(id)
                                    setMenuOpen(false)
                                }}
                            >
                                <label label={label} />
                            </button>
                        ))}
                    </box>
                </popover>
            </button>
            <label
                class="battery-label"
                visible={isPresent((present) => present)}
                label={percentage((pct) => `${Math.round(pct * 100)}%`)}
            />
        </box>
    )
}
