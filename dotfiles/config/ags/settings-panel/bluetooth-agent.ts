import Gio from "gi://Gio?version=2.0"
import GLib from "gi://GLib?version=2.0"
import { call, systemBus } from "../services/nm-client"

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

async function registerOnBus(): Promise<void> {
  try {
    await call(
      BLUEZ,
      AGENT_MANAGER_PATH,
      AGENT_MANAGER_IFACE,
      "RegisterAgent",
      new GLib.Variant("(os)", [AGENT_PATH, "NoInputNoOutput"]),
    )
    await call(
      BLUEZ,
      AGENT_MANAGER_PATH,
      AGENT_MANAGER_IFACE,
      "RequestDefaultAgent",
      new GLib.Variant("(o)", [AGENT_PATH]),
    )
  } catch {
    /* no bluetoothd on the bus, or an agent is already registered */
  }
}

/** Register the agent once per session. Safe to call repeatedly. */
export function registerBluetoothAgent(): void {
  if (started) return
  started = true

  let bus: Gio.DBusConnection
  try {
    bus = systemBus()
  } catch {
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
  } catch {
    started = false
    return
  }

  void registerOnBus()
}
