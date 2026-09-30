import { Accessor, createComputed, createEffect, createState, For } from "ags"
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
  stopSpeedTestService,
  runSpeedTest,
  lastResult,
  lastRunAt,
  lastError,
  running as speedTestRunning,
  type SpeedTestResult,
} from "../../services/speedtest-service"

export {
  connectState,
  wifiNetworks,
}
export type { WifiNetwork }

const [selectedSsid, setSelectedSsid] = createState<string | null>(null)
const [otherExpanded, setOtherExpanded] = createState(false)
const [stcExpanded, setStcExpanded] = createState(false)
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
      <label class="settings-stc-caption" xalign={0} label="Min 1000 ms · 0 = Off · Enter/leave to apply, junk reverts" />
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
    <image class="settings-net-signal" pixel_size={18} $={(self) => {
      createEffect(() => self.set_from_file(src ?? ""))
    }} />
  ) : null
}

function formatSpeedFull(r: SpeedTestResult | null): string {
  if (!r) return "—"
  return `↓ ${r.down_mbps} Mbps · ↑ ${r.up_mbps} Mbps · ${r.latency_ms} ms`
}

function formatSpeedCompact(r: SpeedTestResult | null): string {
  if (!r) return "—"
  return `↓ ${r.down_mbps} · ↑ ${r.up_mbps} · ${r.latency_ms}ms`
}

function formatRanAt(ranAt: number | null): string {
  if (ranAt === null) return "—"
  const mins = Math.round((Date.now() - ranAt) / 60000)
  if (mins < 1) return "just now"
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
      <label class="settings-security-text" xalign={0} valign={Gtk.Align.CENTER} label="Weak Security (WPA)" />
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
  const speed = createComputed(() => formatSpeedFull(lastResult()))
  const lastTest = createComputed(() => formatSpeedCompact(lastResult()))
  const ran = createComputed(() => formatRanAt(lastRunAt()))
  //: state-2-stc-expanded mock variant: with the section open, the table
  //: drops Last-test/Ran (results context lives in the open section).
  const showFullDetails = createComputed(() => !stcExpanded())
  return (
    <box class="settings-conn-details" orientation={1} spacing={2}>
      <DetailRow name="MAC" value={mac} />
      <DetailRow name="IP / iface" value={ipIface} />
      <DetailRow name="Speed" value={speed} />
      <DetailRow name="Last test" value={lastTest} visible={showFullDetails} />
      <DetailRow name="Ran" value={ran} visible={showFullDetails} />
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
        ><label label={createComputed(() => revealed() ? "Hide" : "Show")} /></button>
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
      <label class="settings-section-label" xalign={0} label="Known Networks" />
      <box orientation={1} spacing={4}>
        <For each={connected} id={(n) => n.ssid}>
          {(network) => <WifiRow network={network} />}
        </For>
        <For each={knownSaved} id={(n) => n.ssid}>
          {(network) => <WifiRow network={network} />}
        </For>
      </box>
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

export function WifiContent({ visible }: { visible: Accessor<boolean> }) {
  const [settingsMessage, setSettingsMessage] = createState("")
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
      startSpeedTestService()
      return () => { stopScanning(); stopSpeedTestService() }
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
        <label class="settings-chevron-label" xalign={0} label={stcExpanded() ? "Speed Test Settings… ▾" : "Speed Test Settings… ▸"} />
      </button>

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
        <button class={createComputed(() => speedTestRunning() ? "settings-stc-run-btn running" : "settings-stc-run-btn")} sensitive={createComputed(() => !speedTestRunning())} onClicked={() => { void runSpeedTest() }} canFocus={false}>
          <box spacing={6} halign={Gtk.Align.CENTER}>
            <Gtk.Spinner class="settings-spinner" spinning={speedTestRunning()} visible={speedTestRunning()} />
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
        <label class="settings-wifi-settings-label" hexpand label="Wi-Fi Settings" />
        <label class="settings-wifi-settings-arrow" label="›" />
      </box>
    </box>
  )
}
