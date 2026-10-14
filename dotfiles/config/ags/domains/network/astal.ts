import Network from "gi://AstalNetwork"
import { agsRuntime } from "../astal"
import type { NetworkReading } from "../../lib/network-icon.ts"
import type { ReadAccessor } from "../reactive"
import { createNetworkReadModel as createReadModel, type NetworkService } from "./read-model"

/**
 * The network read model's Astal binding (spine AD-2).
 *
 * The service and the reactive runtime are closed over HERE, at construction,
 * and never carried in `BarContext`: the widget calls this factory and receives
 * a reactive accessor, and the subscription lives behind it. The injected
 * default makes the seam a parameter (mirroring `createNetworkReadModel`'s seed)
 * rather than a hard `Network.get_default()` inside the pure core.
 */
export function createNetworkReadModel(
  network: NetworkService = Network.get_default() as unknown as NetworkService,
): ReadAccessor<NetworkReading> {
  return createReadModel(network, agsRuntime)
}
