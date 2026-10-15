import GLib from "gi://GLib?version=2.0"
import { createState } from "ags"
import { publishSpeedTestState, type SpeedTestTrigger } from "../platform/adapters/event-bus"
import { execAsync } from "ags/process"
//: The connected network's SSID rides on the `done` event so the notification
//: card can name what it measured. Reading it HERE is the whole reason this is
//: a payload change and not consumer-side coupling: the service already lives
//: in the same AGS process as the Wi-Fi service, so the state is one accessor
//: away, whereas the notifications app is a SEPARATE instance that has no
//: business importing Wi-Fi state. Import direction matters: service -> service
//: is a pass-through, notification-app -> wifi-service would be new coupling
//: across an instance boundary.
import { wifiNetworks } from "./wifi-service"

export type SpeedTestResult = {
  down_mbps: number
  up_mbps: number
  latency_ms: number
}

//: A parsed run: the measurement the panel renders, plus the server it was
//: measured against. Kept OUT of `SpeedTestResult` deliberately — that type is
//: persisted to `wifi-speedtest-last.json` and read back on restart, so adding a
//: field to it would change the on-disk shape of every existing measurement for
//: a value only the card consumes.
type ParsedRun = {
  result: SpeedTestResult
  server_name: string
}

export type SpeedTestConfig = {
  interval_ms: number
  run_on_connect: boolean
  server_mode: "auto"
  /** Emit `speedtest.state` so the notifications app can show a card per run. */
  notify_on_test: boolean
}

//: Minimum committable interval (recorded assumption: 1000 ms, 0 = Off).
export const MIN_INTERVAL_MS = 1000

const DEFAULT_CONFIG: SpeedTestConfig = {
  interval_ms: 900000,
  run_on_connect: true,
  server_mode: "auto",
  //: Default ON: a measurement that happens silently is the problem this
  //: setting exists to fix. It only gates the CARD — the run still executes and
  //: the panel rows still update, so turning it off is never a way to stop
  //: measuring.
  notify_on_test: true,
}

const [config, setConfig] = createState<SpeedTestConfig>(DEFAULT_CONFIG)
const [lastResult, setLastResult] = createState<SpeedTestResult | null>(null)
//: Epoch ms of the last completed attempt (details-table `Ran` row) — set on
//: success AND failure (Ran answers "when did you last try").
//: Typed failure the UI can show; cleared on the next run start.
const [lastRunAt, setLastRunAt] = createState<number | null>(null)
const [lastError, setLastError] = createState<string | null>(null)
const [running, setRunning] = createState(false)
const [timerId, setTimerId] = createState(0)
let serviceUsers = 0

let configPath = `${GLib.get_user_config_dir()}/ags/wifi-speedtest.json`

//: The last measurement is persisted separately from the config. The interval
//: is a *setting* and must survive restarts; the measurement is *data* and used
//: to live only in `lastResult`/`lastRunAt`, so every AGS restart blanked the
//: Speed/Ran rows to "—" and left them empty until the next scheduled run a
//: whole interval away. Kept in its own file so a corrupt or hand-edited
//: measurement can never take the interval down with it.
let lastRunPath = `${GLib.get_user_config_dir()}/ags/wifi-speedtest-last.json`

type PersistedRun = {
  result: SpeedTestResult
  ran_at: number
}

function loadLastRun(): PersistedRun | null {
  try {
    const data = GLib.file_get_contents(lastRunPath)?.[1]
    if (!data) return null
    const parsed = JSON.parse(new TextDecoder().decode(data)) as Partial<PersistedRun>
    const r = parsed.result
    if (
      typeof parsed.ran_at !== "number" ||
      !Number.isFinite(parsed.ran_at) ||
      r === undefined ||
      typeof r.down_mbps !== "number" ||
      typeof r.up_mbps !== "number" ||
      typeof r.latency_ms !== "number"
    ) {
      return null
    }
    return {
      result: { down_mbps: r.down_mbps, up_mbps: r.up_mbps, latency_ms: r.latency_ms },
      ran_at: parsed.ran_at,
    }
  } catch {
    return null
  }
}

function saveLastRun(result: SpeedTestResult, ranAt: number): void {
  try {
    const payload: PersistedRun = { result, ran_at: ranAt }
    const ok = GLib.file_set_contents(lastRunPath, JSON.stringify(payload, null, 2))
    if (!ok) console.error(`speedtest-service: saveLastRun write failed for ${lastRunPath}`)
  } catch (error) {
    console.error(`speedtest-service: saveLastRun failed for ${lastRunPath}: ${error}`)
  }
}

function loadConfig(): SpeedTestConfig {
  try {
    const data = GLib.file_get_contents(configPath)?.[1]
    if (data) {
      const parsed = JSON.parse(new TextDecoder().decode(data)) as Partial<SpeedTestConfig> & {
        interval_min?: unknown
      }
      let interval_ms = parsed.interval_ms
      if (interval_ms === undefined && typeof parsed.interval_min === "number") {
        interval_ms = Math.max(0, Math.round(parsed.interval_min * 60000))
      }
      const merged: SpeedTestConfig = {
        interval_ms: interval_ms ?? DEFAULT_CONFIG.interval_ms,
        run_on_connect: parsed.run_on_connect ?? DEFAULT_CONFIG.run_on_connect,
        server_mode: parsed.server_mode ?? DEFAULT_CONFIG.server_mode,
        //: `?? default`, NOT `|| true`: a hand-edited `false` must survive the
        //: round trip, and a file written before this key existed must load as
        //: true WITHOUT being rewritten (the migration write below is reserved
        //: for the interval_min rename, so merely starting AGS does not touch
        //: the user's file).
        notify_on_test: parsed.notify_on_test ?? DEFAULT_CONFIG.notify_on_test,
      }
      if (parsed.interval_min !== undefined) {
        //: Legacy file migrated (interval_min → interval_ms); save back so
        //: the old key never resurfaces.
        saveConfig(merged)
      }
      return merged
    }
  } catch { /* use defaults */ }
  return DEFAULT_CONFIG
}

function saveConfig(c: SpeedTestConfig): void {
  //: file_set_contents reports failure via its boolean return (it does NOT
  //: throw), so check it explicitly — a silent failed write is exactly what
  //: makes the UI revert on the next loadConfig (snap-back shape).
  try {
    const json = JSON.stringify(c, null, 2)
    const ok = GLib.file_set_contents(configPath, json)
    if (!ok) console.error(`speedtest-service: saveConfig write failed for ${configPath}`)
  } catch (error) {
    console.error(`speedtest-service: saveConfig failed for ${configPath}: ${error}`)
  }
}

export function getConfig(): SpeedTestConfig { return config() }
export function getLastResult(): SpeedTestResult | null { return lastResult() }
export function isRunning(): boolean { return running() }

export function setConfigValue(partial: Partial<SpeedTestConfig>): void {
  const next = { ...config(), ...partial }
  console.error(`speedtest-service: setConfigValue called with ${JSON.stringify(partial)}, before config=${JSON.stringify(config())}`)
  setConfig(next)
  saveConfig(next)
  console.error(`speedtest-service: setConfigValue done, config=${JSON.stringify(config())}, file check...`)
  //: Only `interval_ms` and `run_on_connect` are scheduler inputs. Without this
  //: guard, flipping `notify_on_test` — a purely presentational preference —
  //: would tear down and re-arm the interval timer, silently resetting how long
  //: is left until the next scheduled run. A preference switch must not move the
  //: measurement schedule.
  const schedulerInput = Object.keys(partial).some(
    (key) => key === "interval_ms" || key === "run_on_connect",
  )
  if (schedulerInput && serviceUsers > 0) {
    stopScheduler()
    startScheduler()
  }
}

/**
 * Announce a lifecycle transition on the domain bus — but only when the
 * preference is on.
 *
 * The gate lives HERE, in the producer, and before anything is constructed: the
 * fail-open rule the capture tool uses. When the preference is off, no event is
 * built and none is sent, while the run itself still executes and the panel
 * rows still update. Gating in the consumer instead would mean the events keep
 * crossing the bus for a feature nobody is looking at.
 */
function publish(state: "starting" | "done" | "error", trigger: SpeedTestTrigger, terminal?: unknown): void {
  if (!config().notify_on_test) return
  publishSpeedTestState(
    state,
    trigger,
    terminal as Parameters<typeof publishSpeedTestState>[2],
  )
}

//: Real Ookla `speedtest --format=json` result shape:
//: `{type:"result", ping:{latency}, download:{bandwidth}, upload:{bandwidth}}`
//: with bandwidth in BYTES/sec. Every field is validated — an invalid shape
//: or CLI error yields null (typed failure), never undefined/garbage.
function toMbps(bandwidth: unknown): number | null {
  if (typeof bandwidth !== "number" || !Number.isFinite(bandwidth) || bandwidth < 0) {
    return null
  }
  return Math.round((bandwidth / 125000) * 10) / 10
}

function toLatencyMs(latency: unknown): number | null {
  if (typeof latency !== "number" || !Number.isFinite(latency) || latency < 0) {
    return null
  }
  return Math.round(latency * 10) / 10
}

/**
 * Human label for the server a run was measured against.
 *
 * Both backends report a `server` object but spell the sponsor differently:
 * the Ookla CLI uses `{name, host}` (name = the ISP), while `speedtest-cli`
 * uses `{sponsor, name, host, url}` (sponsor = the ISP, name = the city). The
 * approved mock's "CableVivo Envigado" is the latter's `sponsor` + `name`, so
 * both are joined when both exist.
 *
 * Returns "" rather than null when nothing usable is present: the contract
 * allows an empty string for "unavailable", and "" is what a consumer can test
 * on. A null here would have to become "" one layer up anyway.
 */
function serverLabel(server: unknown): string {
  if (server === null || typeof server !== "object") return ""
  const record = server as Record<string, unknown>
  const text = (key: string): string => {
    const value = record[key]
    return typeof value === "string" ? value.trim() : ""
  }
  const sponsor = text("sponsor")
  const name = text("name")
  if (sponsor !== "" && name !== "") return `${sponsor} ${name}`
  // `host` is `speedtest.cablevivo.com:8080` on one backend and a bare host on
  // the other; either reads better than an empty body line.
  return name !== "" ? name : (text("host") || sponsor || text("url"))
}

/**
 * The network a run STARTED on.
 *
 * Read at run start, not at settle: the run measured the link that was up when
 * it began, so re-reading on completion would mislabel a result whenever the
 * connection changed mid-run. Empty when Wi-Fi is off, the list has not been
 * populated yet, or the service is running where the Wi-Fi accessor is idle —
 * all of which are the honest "no associated network".
 */
function connectedSsid(): string {
  return wifiNetworks().find((network) => network.connected)?.ssid ?? ""
}

function parseOoklaResult(out: string): ParsedRun | null {
  let raw: unknown
  try {
    raw = JSON.parse(out) as unknown
  } catch {
    return null
  }
  if (raw === null || typeof raw !== "object") return null
  const payload = raw as {
    download?: { bandwidth?: unknown }
    upload?: { bandwidth?: unknown }
    ping?: { latency?: unknown }
    server?: unknown
  }
  const down_mbps = toMbps(payload.download?.bandwidth)
  const up_mbps = toMbps(payload.upload?.bandwidth)
  const latency_ms = toLatencyMs(payload.ping?.latency)
  if (down_mbps === null || up_mbps === null || latency_ms === null) return null
  return {
    result: { down_mbps, up_mbps, latency_ms },
    server_name: serverLabel(payload.server),
  }
}

// Arch/Debian ship the compatible `speedtest-cli` under a separate command.
// Its JSON reports download/upload in bits per second at the top level.
function parseSpeedtestCliResult(out: string): ParsedRun | null {
  let raw: unknown
  try {
    raw = JSON.parse(out) as unknown
  } catch {
    return null
  }
  if (raw === null || typeof raw !== "object") return null
  const payload = raw as {
    download?: unknown
    upload?: unknown
    ping?: unknown
    server?: unknown
  }
  const down = payload.download
  const up = payload.upload
  const ping = payload.ping
  if (
    typeof down !== "number" || !Number.isFinite(down) || down < 0 ||
    typeof up !== "number" || !Number.isFinite(up) || up < 0 ||
    typeof ping !== "number" || !Number.isFinite(ping) || ping < 0
  ) return null
  return {
    result: {
      down_mbps: Math.round((down / 1_000_000) * 10) / 10,
      up_mbps: Math.round((up / 1_000_000) * 10) / 10,
      latency_ms: Math.round(ping * 10) / 10,
    },
    server_name: serverLabel(payload.server),
  }
}

//: Hard ceiling on one measurement. execAsync has no timeout of its own, so a
//: stalled transfer (server accepts the connection then goes quiet) leaves the
//: promise pending forever. That wedges `running` permanently: the Run button
//: stays on "Testing…" AND the `if (running()) return` guard at the top of
//: runSpeedTest then rejects every subsequent scheduled run, so the whole
//: feature dies silently until the process is restarted. 120s is far longer
//: than a healthy run (~20-30s here) and still bounded.
const RUN_TIMEOUT_MS = 120000

/**
 * One measurement, with every lifecycle edge announced on `speedtest.state`.
 *
 * `trigger` is THREADED, not inferred: it is the only thing that distinguishes a
 * run you asked for from one the timer started, and the notification card's
 * footer reads it. Inferring it here (e.g. "was the panel open?") would be a
 * guess the service cannot actually make.
 *
 * Exactly ONE terminal event per run, on every exit path including the
 * watchdog. `settled` is the guard: the watchdog and the promise race, and
 * whichever loses would otherwise publish a second terminal event and leave the
 * card showing a result that the other path already overwrote.
 */
function runSpeedTest(trigger: SpeedTestTrigger = "scheduled"): void {
  if (running()) return
  setRunning(true)
  setLastError(null)
  //: Captured ONCE, here, before the subprocess is even spawned: the card must
  //: name the network this run actually measured. Read at start, so a link that
  //: drops and comes back mid-run cannot relabel the result.
  const ssid = connectedSsid()
  publish("starting", trigger)
  // Set on the FIRST terminal event and never cleared, so a later path in the
  // same run cannot emit a second one.
  let settled = false
  const finish = (state: "done" | "error", terminal?: unknown): void => {
    if (settled) return
    settled = true
    publish(state, trigger, terminal)
  }
  // Watchdog: clears `running` if the subprocess never settles. Removed on
  // every normal exit path below, so it only ever fires on a genuine hang.
  let watchdog = GLib.timeout_add(GLib.PRIORITY_DEFAULT, RUN_TIMEOUT_MS, () => {
    console.error(`speedtest-service: run exceeded ${RUN_TIMEOUT_MS}ms; abandoning`)
    setLastError("Speed test timed out.")
    setLastRunAt(Date.now())
    // An abandoned run is a FAILED run for the card: the user asked (or the
    // timer did) and nothing came back, so the sticky caution treatment is the
    // honest one. The panel keeps the previous measurement, same as any other
    // failure.
    finish("error", "Speed test timed out.")
    setRunning(false)
    return false
  })
  const clearWatchdog = () => {
    if (watchdog !== 0) {
      try { GLib.source_remove(watchdog) } catch { /* already fired */ }
      watchdog = 0
    }
  }
  // NOTE: on Arch/Debian `/usr/bin/speedtest` is the Python speedtest-cli
  // wrapper (same as `speedtest-cli`, `--json`), NOT Ookla (`--format=json`).
  // Detecting Ookla by basename alone sends `--format=json` to the Python
  // tool, which exits non-zero / prints usage, surfacing as
  // "unrecognized result". Prefer the explicit `speedtest-cli` binary;
  // only treat `speedtest` as Ookla when `speedtest-cli` is absent.
  const ookla = GLib.find_program_in_path("speedtest")
  const compatible = GLib.find_program_in_path("speedtest-cli")
  if (ookla === null && compatible === null) {
    clearWatchdog()
    setLastError("Speedtest CLI is not installed; provision the speedtest package.")
    setLastRunAt(Date.now())
    finish("error", "Speedtest CLI is not installed.")
    setRunning(false)
    return
  }
  const useOokla = compatible === null && ookla !== null
  const command = useOokla ? [ookla, "--format=json"] : [compatible!, "--json"]
  execAsync(command)
    .then((out: string) => {
      // Dual-parse: mis-detected binaries still resolve instead of
      // "unrecognized result".
      const parsed = useOokla
        ? (parseOoklaResult(out) ?? parseSpeedtestCliResult(out))
        : (parseSpeedtestCliResult(out) ?? parseOoklaResult(out))
      if (parsed === null) {
        console.error(`speedtest-service: unparseable output: ${out.slice(0, 500)}`)
        setLastError("Speed test returned an unrecognized result.")
        finish("error", "Speed test returned an unrecognized result.")
      } else {
        setLastResult(parsed.result)
        // Persist on success only. A failed run must not overwrite the last
        // good measurement — otherwise a transient network blip would blank
        // the Speed rows until the next successful test. The persisted shape is
        // the MEASUREMENT only — the server label is card context and would be
        // stale the moment the next run picks a different server.
        saveLastRun(parsed.result, Date.now())
        finish("done", {
          down_mbps: parsed.result.down_mbps,
          up_mbps: parsed.result.up_mbps,
          latency_ms: parsed.result.latency_ms,
          ssid,
          server_name: parsed.server_name,
        })
      }
      setLastRunAt(Date.now())
    })
    .catch((error: unknown) => {
      // `error.message` only: a spawn failure string can carry a newline and a
      // stack, and the contract requires a single line with no traceback. The
      // panel's `lastError` row still gets the full text.
      const message = error instanceof Error ? error.message : String(error)
      setLastError(`Speed test failed: ${message}`)
      // Timestamp updated but the previous measurement deliberately kept, so
      // "Ran" answers "when did we last try" while the numbers stay truthful.
      setLastRunAt(Date.now())
      console.error(`speedtest-service: run failed: ${error}`)
      finish("error", message)
    })
    .finally(() => {
      clearWatchdog()
      setRunning(false)
    })
}

function startScheduler(): void {
  const c = config()
  if (c.interval_ms <= 0) return
  const id = GLib.timeout_add(
    GLib.PRIORITY_DEFAULT,
    c.interval_ms,
    () => {
      // The timer's own run is what `scheduled` means; the default argument
      // would also cover it, but naming it at the call site keeps the three
      // trigger origins visible in one place.
      runSpeedTest("scheduled")
      return true
    },
  )
  setTimerId(id)
}

function stopScheduler(): void {
  const id = timerId()
  if (id !== 0) {
    try { GLib.source_remove(id) } catch { /* already removed */ }
    setTimerId(0)
  }
}

export function startSpeedTestService(): void {
  serviceUsers += 1
  if (serviceUsers > 1) return
  const c = loadConfig()
  setConfig(c)
  // Restore the last measurement so the Speed/Ran rows are populated
  // immediately after a restart instead of reading "—" until the next
  // scheduled run. Only applied when there is genuinely nothing yet, so a
  // measurement taken during this session is never overwritten by a stale
  // file.
  if (lastResult() === null && lastRunAt() === null) {
    const persisted = loadLastRun()
    if (persisted) {
      setLastResult(persisted.result)
      setLastRunAt(persisted.ran_at)
    }
  }
  if (c.interval_ms > 0) startScheduler()
}

export function stopSpeedTestService(): void {
  serviceUsers = Math.max(0, serviceUsers - 1)
  if (serviceUsers > 0) return
  stopScheduler()
}

export { config, lastError, lastResult, lastRunAt, running, runSpeedTest }
