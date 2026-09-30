import GLib from "gi://GLib?version=2.0"
import { createState } from "ags"
import { publishSpeedTestFinished } from "../lib/event-bus"
import { execAsync } from "ags/process"

export type SpeedTestResult = {
  down_mbps: number
  up_mbps: number
  latency_ms: number
}

export type SpeedTestConfig = {
  interval_ms: number
  run_on_connect: boolean
  server_mode: "auto"
}

//: Minimum committable interval (recorded assumption: 1000 ms, 0 = Off).
export const MIN_INTERVAL_MS = 1000

const DEFAULT_CONFIG: SpeedTestConfig = {
  interval_ms: 900000,
  run_on_connect: true,
  server_mode: "auto",
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
  if (serviceUsers > 0) {
    stopScheduler()
    startScheduler()
  }
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

function parseOoklaResult(out: string): SpeedTestResult | null {
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
  }
  const down_mbps = toMbps(payload.download?.bandwidth)
  const up_mbps = toMbps(payload.upload?.bandwidth)
  const latency_ms = toLatencyMs(payload.ping?.latency)
  if (down_mbps === null || up_mbps === null || latency_ms === null) return null
  return { down_mbps, up_mbps, latency_ms }
}

// Arch/Debian ship the compatible `speedtest-cli` under a separate command.
// Its JSON reports download/upload in bits per second at the top level.
function parseSpeedtestCliResult(out: string): SpeedTestResult | null {
  let raw: unknown
  try {
    raw = JSON.parse(out) as unknown
  } catch {
    return null
  }
  if (raw === null || typeof raw !== "object") return null
  const payload = raw as { download?: unknown; upload?: unknown; ping?: unknown }
  const down = payload.download
  const up = payload.upload
  const ping = payload.ping
  if (
    typeof down !== "number" || !Number.isFinite(down) || down < 0 ||
    typeof up !== "number" || !Number.isFinite(up) || up < 0 ||
    typeof ping !== "number" || !Number.isFinite(ping) || ping < 0
  ) return null
  return {
    down_mbps: Math.round((down / 1_000_000) * 10) / 10,
    up_mbps: Math.round((up / 1_000_000) * 10) / 10,
    latency_ms: Math.round(ping * 10) / 10,
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

function runSpeedTest(): void {
  if (running()) return
  setRunning(true)
  setLastError(null)
  // Watchdog: clears `running` if the subprocess never settles. Removed on
  // every normal exit path below, so it only ever fires on a genuine hang.
  let watchdog = GLib.timeout_add(GLib.PRIORITY_DEFAULT, RUN_TIMEOUT_MS, () => {
    console.error(`speedtest-service: run exceeded ${RUN_TIMEOUT_MS}ms; abandoning`)
    setLastError("Speed test timed out.")
    setLastRunAt(Date.now())
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
    setRunning(false)
    return
  }
  const useOokla = compatible === null && ookla !== null
  const command = useOokla ? [ookla, "--format=json"] : [compatible!, "--json"]
  execAsync(command)
    .then((out: string) => {
      // Dual-parse: mis-detected binaries still resolve instead of
      // "unrecognized result".
      const result = useOokla
        ? (parseOoklaResult(out) ?? parseSpeedtestCliResult(out))
        : (parseSpeedtestCliResult(out) ?? parseOoklaResult(out))
      if (result === null) {
        console.error(`speedtest-service: unparseable output: ${out.slice(0, 500)}`)
        setLastError("Speed test returned an unrecognized result.")
      } else {
        setLastResult(result)
        // Persist on success only. A failed run must not overwrite the last
        // good measurement — otherwise a transient network blip would blank
        // the Speed rows until the next successful test.
        saveLastRun(result, Date.now())
        publishSpeedTestFinished(result)
      }
      setLastRunAt(Date.now())
    })
    .catch((error: unknown) => {
      setLastError(`Speed test failed: ${error instanceof Error ? error.message : String(error)}`)
      // Timestamp updated but the previous measurement deliberately kept, so
      // "Ran" answers "when did we last try" while the numbers stay truthful.
      setLastRunAt(Date.now())
      console.error(`speedtest-service: run failed: ${error}`)
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
      runSpeedTest()
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
