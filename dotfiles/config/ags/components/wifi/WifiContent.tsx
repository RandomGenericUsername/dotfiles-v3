import { Accessor, createComputed, createEffect, createState, For } from "ags"
import GLib from "gi://GLib?version=2.0"
import Pango from "gi://Pango?version=1.0"
import { Gtk } from "ags/gtk4"
import { execAsync } from "ags/process"
import { registry } from "../../lib/icon-registry"
import { wifiSignalIconKey } from "../../lib/wifi-signal"
import { WifiSwitch } from "../primitives/WifiSwitch"
import {
  activate,
  cancel,
  connectState,
  deviceInfo,
  startScanning,
  stopScanning,
  submitPassword,
  wifiEnabled,
  wifiNetworks,
  type WifiNetwork,
} from "../../services/wifi-service"
import {
  MIN_INTERVAL_MS,
  getConfig,
  setConfigValue,
  startSpeedTestService,
  runSpeedTest,
  lastResult,
  lastRunAt,
  lastError,
  running as speedTestRunning,
} from "../../services/speedtest-service"

export {
  connectState,
  wifiNetworks,
}
export type { WifiNetwork }

const [selectedSsid, setSelectedSsid] = createState<string | null>(null)
const [otherExpanded, setOtherExpanded] = createState(false)
const [stcExpanded, setStcExpanded] = createState(false)
// Exported so SettingsPanel can grant keyboard focus while the speed-test
// interval Gtk.Entry is on screen. Without ON_DEMAND the panel holds no
// keyboard, so that entry is clickable but inert — keystrokes go to the bar.
export { stcExpanded }
// Ticking clock so relative `Ran` stays live. One source for both the popup and
// the settings-view instance (they share this module, so a single timer serves
// both). 1s while a surface is actually on screen, 30s otherwise: seconds
// granularity needs a 1s tick, but paying that forever for a hidden panel
// would keep the CPU awake for nothing. Opening either surface bumps the clock
// immediately so "Ran" never shows a stale age on first paint.
const [nowMs, setNowMs] = createState(Date.now())
const [timeVisible, setTimeVisible] = createState(false)
let timeTimerId = 0
function ensureTimeTimer(): void {
  const period = timeVisible() ? 1000 : 30000
  if (timeTimerId !== 0 && lastTimePeriod === period) return
  if (timeTimerId !== 0) {
    try { GLib.source_remove(timeTimerId) } catch { /* already removed */ }
  }
  lastTimePeriod = period
  timeTimerId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, period, () => {
    setNowMs(Date.now())
    return true
  })
}
let lastTimePeriod = 0
// NOTE: deliberately NOT wrapped in a module-level createEffect. Effects
// created outside a createRoot are never disposed (gjs logs
// "effects created outside a `createRoot` will never be disposed"), and a
// leaked 1s GLib timer would outlive every surface. ensureTimeTimer is called
// from the per-instance visible effect in WifiContent instead, which IS
// owned by a root and is disposed with the widget.
const stcIntervalMs = createComputed(() => getConfig().interval_ms)
const stcRunOnConnect = createComputed(() => getConfig().run_on_connect)
let observedConnectedSsid: string | null = null
let connectionObserved = false


const STC_CHIPS = [
  { label: "5m", ms: 300000 },
  { label: "15m", ms: 900000 },
  { label: "30m", ms: 1800000 },
  { label: "Off", ms: 0 },
]

function humanizeMs(ms: number): string {
  if (!ms || ms <= 0) return "Off"
  if (ms < 1000) return `${ms} ms`
  if (ms < 60000) return `${Math.round(ms / 1000)} s`
  return `${Math.round((ms / 60000) * 10) / 10} min`
}

function IntervalMsControl() {
  const [draft, setDraft] = createState(String(stcIntervalMs()))
  //: Draft follows the COMMITTED value only (chips, migration, the other
  //: mounted instance) — never the draft itself, so typing is never clobbered.
  const committedText = createComputed(() => String(stcIntervalMs()))
  createEffect(() => {
    setDraft(committedText())
  })

  //: Design commit rule: strip non-digits → empty/NaN/≤0 is Off (0);
  //: (0,1000) clamps to the floor; else round. Post-commit the draft shows
  //: the committed value, so junk text visibly reverts.
  function commit(raw: string): void {
    const trimmed = raw.trim()
    if (trimmed !== "" && !/^\d+$/.test(trimmed)) {
      setDraft(String(stcIntervalMs()))
      return
    }
    const n = trimmed === "" ? 0 : Number(trimmed)
    if (!Number.isFinite(n)) {
      setDraft(String(stcIntervalMs()))
      return
    }
    const value =
      n <= 0
        ? 0
        : n < MIN_INTERVAL_MS
          ? MIN_INTERVAL_MS
          : Math.round(n)
    setConfigValue({ interval_ms: value })
    setDraft(String(value))
  }

  const hint = createComputed(() => humanizeMs(stcIntervalMs()))

  return (
    <box orientation={1} spacing={4}>
      <box class="settings-stc-row" spacing={8}>
        <label class="settings-stc-label" xalign={0} hexpand label="Interval" />
        <box spacing={6}>
          <entry
            class="settings-stc-entry"
            xalign={1}
            widthChars={8}
            inputPurpose={Gtk.InputPurpose.NUMBER}
            text={draft}
            tooltipText="Interval in milliseconds"
            onActivate={() => commit(draft())}
            onNotifyText={(self: { text: string }) => {
              if (self.text !== draft()) setDraft(self.text)
            }}
            $={(self) => {
              const focus = new Gtk.EventControllerFocus()
              focus.connect("leave", () => commit(draft()))
              self.add_controller(focus)
            }}
          />
          <label class="settings-stc-value" xalign={0} valign={Gtk.Align.CENTER} label="ms" />
          <label class="settings-stc-value settings-stc-hint" xalign={0} valign={Gtk.Align.CENTER} label={hint} />
        </box>
      </box>
      {/* 57 chars unguarded is the other row that can outgrow the 312px
          surface. wrap + maxWidthChars keeps the whole rule readable across two
          lines rather than ellipsizing away the "junk reverts" half, which is
          the part that tells you what will happen. */}
      <label
        class="settings-stc-caption"
        xalign={0}
        wrap
        maxWidthChars={40}
        label="Min 1000 ms · 0 = Off · Enter/leave to apply, junk reverts"
      />
      <box class="settings-chip-row" spacing={6}>
        {STC_CHIPS.map((chip) => (
          <button
            class={createComputed(() => stcIntervalMs() === chip.ms ? "settings-chip active" : "settings-chip")}
            onClicked={() => {
              setConfigValue({ interval_ms: chip.ms })
              setDraft(String(chip.ms))
            }}
            canFocus={false}
          >
            <label label={chip.label} />
          </button>
        ))}
      </box>
    </box>
  )
}

export const wifiPromptSsid: Accessor<string | null> = createComputed(() => {
  const conn = connectState()
  if (conn.phase === "needAuth") return conn.ssid
  if (conn.phase === "idle") return null
  return selectedSsid()
})

export const wifiPromptVisible: Accessor<boolean> = createComputed(
  () => wifiPromptSsid() !== null,
)

export function cancelWifiPrompt(): void {
  setSelectedSsid(null)
  cancel()
}


function getSignalIconKey(strength: number): string {
  return wifiSignalIconKey(strength)
}

function SignalIcon({ strength }: { strength: number }) {
  const key = getSignalIconKey(strength)
  const src = registry.resolve("settings-panel", key)
  return src ? (
    <image class="settings-net-signal" pixel_size={30} $={(self) => {
      createEffect(() => self.set_from_file(src ?? ""))
    }} />
  ) : null
}

function formatRanAt(ranAt: number | null): string {
  if (ranAt === null) return "—"
  const seconds = Math.max(0, Math.round((Date.now() - ranAt) / 1000))
  // Seconds below a minute: "just now" hides the fact that the value is live
  // and re-read on every open, and gives no way to tell a 5s-old reading from
  // a 55s-old one.
  if (seconds < 60) return seconds <= 1 ? "just now" : `${seconds} s ago`
  const mins = Math.round(seconds / 60)
  if (mins < 60) return `${mins} min ago`
  return `${Math.round(mins / 60)} h ago`
}

function SecurityRow() {
  const src = registry.resolve("settings-panel", "info-caution")
  const isWeakSecurity = createComputed(() =>
    wifiNetworks().some((n) => n.connected && n.weakSecurity),
  )
  return (
    <box class="settings-security-warn" spacing={8} visible={isWeakSecurity}>
      {src ? (
        <image class="settings-security-icon" pixel_size={16} valign={Gtk.Align.CENTER} $={(self) => {
          createEffect(() => self.set_from_file(src ?? ""))
        }} />
      ) : null}
      {/* Wraps rather than truncates: a security state is the one string that
          must never be cut mid-word. Short enough that it stays on one line at
          the current font; the wrap is only a guard. */}
      <label
        class="settings-security-text"
        xalign={0}
        valign={Gtk.Align.CENTER}
        wrap
        maxWidthChars={24}
        label="Weak Security (WPA)"
      />
    </box>
  )
}

function DetailRow({ name, value, visible = true }: {
  name: string
  value: Accessor<string>
  visible?: Accessor<boolean> | boolean
}) {
  return (
    <box class="settings-detail-row" spacing={8} visible={visible}>
      <label class="settings-detail" xalign={0} label={name} />
      <label class="settings-detail" xalign={1} hexpand label={value} />
    </box>
  )
}

function ConnectionDetails() {
  const mac = createComputed(() => deviceInfo().mac ?? "—")
  const ipIface = createComputed(() => {
    const info = deviceInfo()
    if (info.ip && info.iface) return `${info.ip} · ${info.iface}`
    return info.ip ?? info.iface ?? "—"
  })
  // Download / Upload / Ping as their own rows rather than one crammed
  // "Speed" line: the combined string needed ~200px and was the widest value in
  // the details block, which is what made it the row most at risk of forcing
  // the surface wider than 312px. Split, each value is short and the block
  // reads as a clean spec sheet.
  const mbps = (v: number | undefined) => (v === undefined ? "—" : `${Math.round(v)} Mbps`)
  const download = createComputed(() => mbps(lastResult()?.down_mbps))
  const upload = createComputed(() => mbps(lastResult()?.up_mbps))
  const ping = createComputed(() => {
    const ms = lastResult()?.latency_ms
    return ms === undefined ? "—" : `${Math.round(ms)} ms`
  })
  const ran = createComputed(() => {
    nowMs()
    return formatRanAt(lastRunAt())
  })
  return (
    <box class="settings-conn-details" orientation={1} spacing={2}>
      <DetailRow name="MAC" value={mac} />
      <DetailRow name="IP / iface" value={ipIface} />
      <DetailRow name="Download" value={download} />
      <DetailRow name="Upload" value={upload} />
      <DetailRow name="Ping" value={ping} />
      <DetailRow name="Ran" value={ran} />
    </box>
  )
}

export function WifiRow({ network: item }: { network: WifiNetwork }) {
  const live = createComputed(() => wifiNetworks().find((n) => n.ssid === item.ssid) ?? item)
  const connected = createComputed(() => live().connected)
  const saved = createComputed(() => live().saved)
  const cls = createComputed(() => connected() ? "settings-net sel" : "settings-net")

  const busy = createComputed(() => {
    const conn = connectState()
    return conn.ssid === item.ssid && (conn.phase === "preparing" || conn.phase === "activating")
  })

  const sensitive = createComputed(() => {
    const conn = connectState()
    const pending = conn.phase === "preparing" || conn.phase === "activating" || conn.phase === "needAuth"
    return !pending || conn.ssid !== item.ssid
  })

  function act() {
    if (connected() || !sensitive()) return
    const wantsPassword = item.secured && !saved()
    activate(item.ssid)
    setSelectedSsid(wantsPassword ? item.ssid : null)
  }

  return (
    <box
      class={cls}
      spacing={10}
      $={(self) => {
        const click = new Gtk.GestureClick({ button: 1 })
        click.connect("released", () => act())
        self.add_controller(click)
      }}
    >
      <SignalIcon strength={item.strength} />
      <box orientation={1} hexpand>
        <label class="settings-net-name" xalign={0} label={item.ssid} />
        <label
          class="settings-net-sub"
          xalign={0}
          label={createComputed(() => {
            if (saved()) return "Saved"
            return live().secured ? "Secured" : "Open network"
          })}
        />
      </box>
      <label
        class="settings-badge conn"
        label="Connected"
        valign={Gtk.Align.CENTER}
        visible={connected}
      />
      <box
        class={createComputed(() => sensitive() ? "settings-rowact" : "settings-rowact disabled")}
        valign={Gtk.Align.CENTER}
        visible={createComputed(() => !connected())}
      >
        <box spacing={6}>
          <Gtk.Spinner class="settings-spinner" visible={busy} spinning={busy} />
          <label label="Connecting…" visible={busy} />
          <label label="Connect" visible={createComputed(() => !busy())} />
        </box>
      </box>
    </box>
  )
}

export function WifiPasswordPrompt() {
  const [password, setPassword] = createState("")
  const [revealed, setRevealed] = createState(false)
  let entry: Gtk.Entry | null = null

  createEffect(() => {
    if (wifiPromptSsid() === null) return
    setPassword("")
    setRevealed(false)
    entry?.grab_focus()
  })

  const joining = createComputed(() => {
    const conn = connectState()
    return conn.phase === "preparing" || conn.phase === "activating"
  })

  const promptError = createComputed(() => {
    const conn = connectState()
    if (conn.phase !== "failed") return ""
    return conn.reason ?? "Connection failed"
  })

  function join() {
    if (joining()) return
    const ssid = wifiPromptSsid()
    if (ssid === null) return
    if (connectState().phase === "needAuth") submitPassword(password())
    else activate(ssid, password())
  }

  return (
    <box class="settings-password" orientation={1} spacing={8}>
      <label class="settings-field-label" xalign={0} label="Password" />
      <box class="settings-field-input settings-pwd-wrap" spacing={6}>
        <entry
          class="settings-field-entry"
          hexpand
          visibility={revealed}
          placeholderText="Network password"
          onActivate={join}
          onNotifyText={(self: { text: string }) => setPassword(self.text)}
          $={(self) => { entry = self }}
        />
        <button
          class={createComputed(() => revealed() ? "settings-eye-btn active" : "settings-eye-btn")}
          tooltipText={createComputed(() => revealed() ? "Hide password" : "Show password")}
          onClicked={() => setRevealed(!revealed())}
          canFocus={false}
        ><image class="settings-eye-icon" pixel_size={16} $={(self) => {
          createEffect(() => {
            const src = registry.resolve("settings-panel", revealed() ? "password-hide" : "password-show")
            if (src !== null) self.set_from_file(src)
          })
        }} /></button>
      </box>
      <label class="settings-field-error" xalign={0} label={createComputed(() => promptError() ?? "")} visible={createComputed(() => promptError() !== "")} />
      <box class="settings-btnrow" spacing={8} homogeneous>
        <button class="settings-btn cancel" onClicked={cancelWifiPrompt} canFocus={false}><label label="Cancel" /></button>
        <button class="settings-btn join" onClicked={join} canFocus={false} sensitive={createComputed(() => !joining())}>
          <label label={createComputed(() => (joining() ? "Joining…" : "Join"))} />
        </button>
      </box>
    </box>
  )
}

function OtherNetworksExpand() {
  const otherNetworks = createComputed(() => wifiNetworks().filter((n) => !n.saved && !n.connected))
  const knownSaved = createComputed(() => wifiNetworks().filter((n) => n.saved && !n.connected))
  const connected = createComputed(() => wifiNetworks().filter((n) => n.connected))

  return (
    <box orientation={1} spacing={4} visible={createComputed(() => wifiEnabled() && !wifiPromptVisible())}>
      <SecurityRow />
      <ConnectionDetails />
      <box class="settings-divider" />
      <label class="settings-section-label" xalign={0} label="Known Networks" />
      <box orientation={1} spacing={4}>
        <For each={connected} id={(n) => n.ssid}>
          {(network) => <WifiRow network={network} />}
        </For>
        <For each={knownSaved} id={(n) => n.ssid}>
          {(network) => <WifiRow network={network} />}
        </For>
      </box>
      <box class="settings-divider" />
      <button
        class="settings-chevron-row"
        onClicked={() => setOtherExpanded(!otherExpanded())}
        canFocus={false}
      >
        <label class="settings-chevron-label" xalign={0} label={otherExpanded() ? "Other Networks ▾" : "Other Networks ▸"} />
      </button>
      <box class="settings-other-networks" visible={otherExpanded} orientation={1} spacing={4}>
        <For each={otherNetworks} id={(n) => n.ssid}>
          {(network) => <WifiRow network={network} />}
        </For>
      </box>
    </box>
  )
}

// Scheduler runs for the whole session, not just while the popup is open:
// it is started once at import (serviceUsers=1 forever), so the configured
// period fires in the background. Only Wi-Fi scanning stays visibility-tied.
startSpeedTestService()

export function WifiContent({ visible }: { visible: Accessor<boolean> }) {
  const [settingsMessage, setSettingsMessage] = createState("")
  // Opening a surface: bump the clock so "Ran" re-reads immediately rather than
  // showing whatever age was computed while the surface was hidden, and drive
  // the shared clock to its 1s cadence while anything is on screen.
  createEffect(() => {
    if (!visible()) return
    setTimeVisible(true)
    setNowMs(Date.now())
    ensureTimeTimer()
    return () => {
      setTimeVisible(false)
      ensureTimeTimer()
    }
  })
  // One module-level baseline lets popup and settings-view instances share
  // this watcher without firing duplicate automatic runs.
  createEffect(() => {
    if (!visible()) return
    const connectedSsid = wifiNetworks().find((network) => network.connected)?.ssid ?? null
    if (!connectionObserved) {
      connectionObserved = true
      observedConnectedSsid = connectedSsid
      return
    }
    if (connectedSsid !== null && connectedSsid !== observedConnectedSsid && getConfig().run_on_connect) {
      void runSpeedTest()
    }
    observedConnectedSsid = connectedSsid
  })
    createEffect(() => {
      if (!visible()) return
      startScanning()
      return () => { stopScanning() }
    })

  const showList = createComputed(() => wifiEnabled() && !wifiPromptVisible())
  const failure = createComputed(() => {
    if (settingsMessage()) return settingsMessage()
    const conn = connectState()
    if (conn.phase !== "failed") return ""
    return conn.reason ?? "Connection failed"
  })

  return (
    <box orientation={1} spacing={8}>
      <label class="settings-empty" xalign={0} label="Wi-Fi is off" visible={createComputed(() => !wifiEnabled())} />
      <label class="settings-message" xalign={0} wrap maxWidthChars={34} label={createComputed(() => failure() ?? "")} visible={createComputed(() => failure() !== "")} />
      <label class="settings-empty" xalign={0} label="No networks found" visible={createComputed(() => showList() && wifiNetworks().length === 0)} />

      <box orientation={1} spacing={4} visible={showList}>
        <OtherNetworksExpand />
      </box>

      <box orientation={1} spacing={8} visible={wifiPromptVisible}>
        <WifiPasswordPrompt />
      </box>

      <button
        class="settings-chevron-row"
        onClicked={() => setStcExpanded(!stcExpanded())}
        canFocus={false}
        visible={createComputed(() => wifiEnabled() && !wifiPromptVisible())}
      >
        <label class="settings-chevron-label" xalign={0} label={stcExpanded() ? "Speed Test Settings ▾" : "Speed Test Settings ▸"} />
      </button>

      <box class="settings-divider" visible={createComputed(() => wifiEnabled() && !wifiPromptVisible())} />

      <box class="settings-speedtest-config" orientation={1} spacing={6} visible={createComputed(() => wifiEnabled() && !wifiPromptVisible() && stcExpanded())}>
        <label class="settings-stc-title" xalign={0} label="Speed Test" />
        <IntervalMsControl />
        <box class="settings-stc-row" spacing={8}>
          <label class="settings-stc-label" xalign={0} hexpand label="Auto-run on connect" />
          <WifiSwitch
            active={stcRunOnConnect}
            onToggled={(v) => setConfigValue({ run_on_connect: v })}
          />
        </box>
        <label class="settings-stc-error" label={createComputed(() => lastError() ?? "")} visible={createComputed(() => lastError() !== null)} />
        <button class={createComputed(() => speedTestRunning() ? "settings-stc-run-btn running" : "settings-stc-run-btn")} onClicked={() => { if (!speedTestRunning()) void runSpeedTest() }} canFocus={false}>
          <box spacing={6} halign={Gtk.Align.CENTER}>
            <Gtk.Spinner class="settings-spinner" spinning={speedTestRunning} visible={speedTestRunning} />
            <label label={createComputed(() => speedTestRunning() ? "Testing…" : "Run now")} />
          </box>
        </button>
      </box>

      <box class="settings-wifi-settings-row" spacing={8} $={(self) => {
        const click = new Gtk.GestureClick({ button: 1 })
        click.connect("released", () => {
          setSettingsMessage("")
          execAsync(["nm-connection-editor"]).catch((error) => {
            console.error(`WifiContent: could not launch nm-connection-editor: ${error}`)
            setSettingsMessage("nm-connection-editor is unavailable — run provisioning to install it.")
          })
        })
        self.add_controller(click)
      }}>
        {/* WHY maxWidthChars IS REQUIRED HERE: an unwrapped Gtk.Label reports
            its FULL text width as natural width, so this row's fixed strings
            ("opens nm-connection-editor", ~150px at 10px) plus 32px of row
            padding exceeded the surface's 312px and grew the whole panel off
            the right edge of the monitor. hexpand on the row label alone does
            not help — the note still refuses to shrink.
            Ellipsize is kept ONLY on the short row label, where a long
            translation may need to yield and losing the tail is acceptable.
            Everything carrying information wraps instead — see below. */}
        <label
          class="settings-wifi-settings-label"
          hexpand
          xalign={0}
          maxWidthChars={14}
          ellipsize={Pango.EllipsizeMode.END}
          label="Wi-Fi Settings"
        />
        {/* wrap, NOT ellipsize. This note is the actionable part of the row —
            truncating it to "opens nm-connection-edit…" destroys the only
            information it carries. maxWidthChars sets the wrap column so the
            label still cannot demand more width than the surface has (an
            unwrapped Gtk.Label reports its full text width as natural width,
            which is what pushed the panel off the monitor). Wrapping costs one
            extra line instead of losing content. */}
        <label
          class="settings-wifi-settings-note"
          valign={Gtk.Align.CENTER}
          xalign={1}
          wrap
          maxWidthChars={22}
          label="opens nm-connection-editor"
        />
        <label class="settings-wifi-settings-arrow" label="›" />
      </box>
    </box>
  )
}
