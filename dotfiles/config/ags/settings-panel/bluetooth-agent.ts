import Gio from "gi://Gio?version=2.0"
import GLib from "gi://GLib?version=2.0"
import { systemBus } from "../services/nm-client"

/**
 * Minimal headless BlueZ pairing agent.
 *
 * BlueZ refuses to complete pairing unless an `org.bluez.Agent1` is registered
 * on the system bus — with no desktop environment there is none, which is why
 * a device briefly connected and then fell back to "Pair". The panel provides
 * its own `NoInputNoOutput` agent (Just Works) that auto-accepts, registered as
 * the default. Provisioning only installs BlueZ; this is the runtime session
 * piece that makes pairing work.
 *
 * Registration uses the shared system-bus connection from `nm-client` (its
 * one permitted startup sync connect); RegisterAgent/RequestDefaultAgent are
 * async, so the agent never blocks the main loop.
 */

const AGENT_PATH = "/org/dotfiles/BlueZAgent"
const BLUEZ = "org.bluez"
const AGENT_MANAGER_IFACE = "org.bluez.AgentManager1"
const AGENT_MANAGER_PATH = "/org/bluez"

/**
 * Capability we declare to BlueZ.
 *
 * `NoInputNoOutput` means Just Works only: BlueZ will never ask this agent for
 * a PIN or passkey, because we could not answer one anyway. Raising it is what
 * in-panel PIN entry would require -- see the `flow-d-pin-inpanel` known gap.
 */
const AGENT_CAPABILITY = "NoInputNoOutput"

/** Cap on the two one-shot registration calls. BlueZ answers in single-digit ms. */
const REGISTER_TIMEOUT_MS = 5000

const AGENT_XML = `
<node>
  <interface name="org.bluez.Agent1">
    <method name="Release"/>
    <method name="RequestPinCode"><arg type="o" direction="in"/><arg type="s" direction="out"/></method>
    <method name="DisplayPinCode"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
    <method name="RequestPasskey"><arg type="o" direction="in"/><arg type="u" direction="out"/></method>
    <method name="DisplayPasskey"><arg type="o" direction="in"/><arg type="u" direction="in"/><arg type="q" direction="in"/></method>
    <method name="RequestConfirmation"><arg type="o" direction="in"/><arg type="u" direction="in"/></method>
    <method name="RequestAuthorization"><arg type="o" direction="in"/></method>
    <method name="AuthorizeService"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
    <method name="Cancel"/>
  </interface>
</node>`

let started = false

/**
 * Register the exported object with BlueZ and make it the default agent.
 *
 * WHY THIS IS NOW SYNCHRONOUS AND LOUD, which it was not before:
 *
 * The original version was `async`, fire-and-forget (`void registerOnBus()`),
 * with every failure swallowed by a bare `catch {}`. MEASURED consequence on a
 * live session: the agent silently never registered, so pairing any new device
 * failed with no message anywhere -- and because AGS's own stdout/stderr was
 * not captured, nothing could be seen. `bluetooth-mock-parity` and the unit
 * tests cannot catch this class of bug: it only exists at runtime, against a
 * real bluetoothd.
 *
 * Two changes, both load-bearing:
 *   - `call_sync` instead of an async promise. This is a one-shot startup step
 *     that must have happened before any pairing is attempted; making it
 *     synchronous removes the question of whether the reply was dispatched
 *     before the main loop began iterating, and it lets us report the outcome
 *     of the call rather than fire and forget.
 *   - every failure logs the actual error. A silent catch here is a bug
 *     factory: it converts "this feature is broken" into "this feature is
 *     absent", which is far more expensive to diagnose.
 */
function registerOnBus(bus: Gio.DBusConnection): void {
  try {
    bus.call_sync(
      BLUEZ,
      AGENT_MANAGER_PATH,
      AGENT_MANAGER_IFACE,
      "RegisterAgent",
      new GLib.Variant("(os)", [AGENT_PATH, AGENT_CAPABILITY]),
      null,
      Gio.DBusCallFlags.NONE,
      REGISTER_TIMEOUT_MS,
      null,
    )
  } catch (error) {
    console.error(
      `bluetooth-agent: RegisterAgent(${AGENT_PATH}, ${AGENT_CAPABILITY}) failed: ${String(error)}`,
    )
    console.error(
      "bluetooth-agent: pairing a NEW device will fail until this succeeds.",
    )
    return
  }

  try {
    bus.call_sync(
      BLUEZ,
      AGENT_MANAGER_PATH,
      AGENT_MANAGER_IFACE,
      "RequestDefaultAgent",
      new GLib.Variant("(o)", [AGENT_PATH]),
      null,
      Gio.DBusCallFlags.NONE,
      REGISTER_TIMEOUT_MS,
      null,
    )
  } catch (error) {
    console.error(`bluetooth-agent: RequestDefaultAgent failed: ${String(error)}`)
    return
  }

  console.log(
    `bluetooth-agent: registered and default (${AGENT_CAPABILITY}) at ${AGENT_PATH}`,
  )
}

/** Register the agent once per session. Safe to call repeatedly. */
export function registerBluetoothAgent(): void {
  if (started) return
  started = true

  let bus: Gio.DBusConnection
  try {
    bus = systemBus()
  } catch (error) {
    console.error(`bluetooth-agent: no system bus, agent not registered: ${String(error)}`)
    started = false
    return
  }

  try {
    const node = Gio.DBusNodeInfo.new_for_xml(AGENT_XML)
    bus.register_object(
      AGENT_PATH,
      node.interfaces[0],
      (
        _conn,
        _sender,
        _path,
        _iface,
        method,
        _params,
        invocation,
      ) => {
        // NoInputNoOutput / Just Works: accept everything. Pin/passkey are
        // never requested for this capability, but return sane values anyway.
        if (method === "RequestPinCode") {
          invocation.return_value(new GLib.Variant("(s)", ["0000"]))
        } else if (method === "RequestPasskey") {
          invocation.return_value(new GLib.Variant("(u)", [0]))
        } else {
          invocation.return_value(null)
        }
      },
      null,
      null,
    )
  } catch (error) {
    console.error(`bluetooth-agent: register_object failed: ${String(error)}`)
    console.error("bluetooth-agent: no org.bluez.Agent1 exported; pairing will fail.")
    started = false
    return
  }

  registerOnBus(bus)
}
