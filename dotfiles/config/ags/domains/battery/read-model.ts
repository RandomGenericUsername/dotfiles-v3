import type { ReadAccessor, ReactiveRuntime } from "ags-platform/ports/reactive"

/**
 * The battery domain's read model: an AstalBattery-shaped service → a reactive
 * `BatteryReading`. PURE — no `ags`, no `gi://*` (spine AD-2/AD-3).
 *
 * WHY THIS EXISTS. The bar widget bound AstalBattery at module scope and read
 * five separate `createBinding`s inside its render, so the domain knowledge
 * (which Astal properties matter, and that a change to any of them is a new
 * reading) lived in the widget. Extracting it makes the same decisions
 * injectable and testable, and gives every future battery surface one reading
 * to consume — the same shape the network read model established.
 *
 * `percentage` is a 0..1 FRACTION, exactly as Astal reports it; the unit is
 * stated at the only place it is used so a consumer cannot mistake it for a
 * percent (the same trap `components/battery/battery-icon.ts` guards).
 */

/** The AstalBattery properties this adapter reads, as a structural shape. */
export interface BatteryService {
  /** 0..1 fraction, as AstalBattery reports it. */
  percentage: number
  charging: boolean
  isPresent: boolean
  /** Seconds until full, or 0/negative when the daemon has no estimate. */
  timeToFull: number
  /** Seconds until empty, or 0/negative when the daemon has no estimate. */
  timeToEmpty: number
  connect(signal: string, callback: () => void): number
  disconnect(handler: number): void
}

/** The inert battery reading a widget consumes. */
export interface BatteryReading {
  percentage: number
  charging: boolean
  isPresent: boolean
  timeToFull: number
  timeToEmpty: number
}

/** The properties whose changes move the battery glyph or its tooltip. */
const BATTERY_NOTIFY_PROPERTIES = [
  "percentage",
  "charging",
  "isPresent",
  "timeToFull",
  "timeToEmpty",
] as const

/** A plain snapshot of the service, so the reading is inert (AD-3). */
export function snapshot(service: BatteryService): BatteryReading {
  return {
    percentage: service.percentage,
    charging: service.charging,
    isPresent: service.isPresent,
    timeToFull: service.timeToFull,
    timeToEmpty: service.timeToEmpty,
  }
}

/**
 * Observe a battery service as a reactive `BatteryReading`.
 *
 * Every watched property republishes a fresh snapshot, so a `createComputed`
 * that calls the accessor re-runs on any battery change.
 */
export function createBatteryReadModel(
  service: BatteryService,
  runtime: ReactiveRuntime,
): ReadAccessor<BatteryReading> {
  const [reading, setReading] = runtime.createState<BatteryReading>(snapshot(service))
  for (const prop of BATTERY_NOTIFY_PROPERTIES) {
    service.connect(`notify::${prop}`, () => setReading(snapshot(service)))
  }
  return reading
}
