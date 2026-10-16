import Battery from "gi://AstalBattery"
import { agsRuntime } from "ags-platform/adapters/astal"
import type { ReadAccessor } from "ags-platform/ports/reactive"
import {
  createBatteryReadModel as createReadModel,
  type BatteryReading,
  type BatteryService,
} from "./read-model"

/**
 * The battery read model's Astal binding (spine AD-2).
 *
 * Closes over the AstalBattery service and the AGS runtime at construction; the
 * widget receives only a reactive accessor. The service is injectable, so the
 * pure core is exercised with a fake in `make ags-test`.
 */
export function createBatteryReadModel(
  battery: BatteryService = Battery.get_default() as unknown as BatteryService,
): ReadAccessor<BatteryReading> {
  return createReadModel(battery, agsRuntime)
}
