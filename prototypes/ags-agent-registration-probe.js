#!/usr/bin/env gjs
/*
 * PROTOTYPE 5 — why is the panel's BlueZ agent not registered?
 *
 * MEASURED FACT: on the live system, `RegisterAgent("/org/dotfiles/BlueZAgent")`
 * SUCCEEDS, which means AGS has NOT registered its agent. Yet the deployed
 * app.tsx calls registerBluetoothAgent() at startup, and the agent file is
 * byte-identical to the repo. So the registration fails somewhere and is
 * swallowed — bluetooth-agent.ts wraps every step in a bare `catch {}`, and
 * AGS's stdout/stderr go to /dev/null, so nothing is visible.
 *
 * This replicates bluetooth-agent.ts step for step, in the same language and
 * the same API, printing the outcome of EACH step so the failing one is named
 * rather than guessed at.
 *
 * It registers its OWN object path, never AGS's, and never requests the
 * default-agent role — so it cannot change who handles pairing.
 *
 * Usage: gjs prototypes/ags-agent-registration-probe.js
 */
const Gio = imports.gi.Gio;
const GLib = imports.gi.GLib;

const AGENT_PATH = "/org/dotfiles/RegistrationProbe";
const BLUEZ = "org.bluez";
const MGR_PATH = "/org/bluez";
const MGR_IFACE = "org.bluez.AgentManager1";

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
</node>`;

function step(n, label) {
    print(`  ${n}. ${label}`);
}
function ok(label) {
    print(`       -> OK   ${label}`);
}
function bad(label, e) {
    print(`       -> FAIL ${label}: ${e && e.message ? e.message : e}`);
}

function main() {
    print("PROBE: replicating bluetooth-agent.ts, step by step\n");

    // Step 1 — the system bus. nm-client does exactly this at module load.
    let bus = null;
    step(1, "Gio.bus_get_sync(SYSTEM)        [what nm-client does at import]");
    try {
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, null);
        ok(`connected, unique name ${bus.get_unique_name()}`);
    } catch (e) {
        bad("system bus unavailable — this alone would disable the agent", e);
        return 1;
    }

    // Step 2 — parse the interface XML. A malformed XML throws here and the
    // real code's bare catch would swallow it.
    step(2, "Gio.DBusNodeInfo.new_for_xml(AGENT_XML)");
    let node = null;
    try {
        node = Gio.DBusNodeInfo.new_for_xml(AGENT_XML);
        ok(`${node.interfaces.length} interface(s): ${node.interfaces[0].name}`);
    } catch (e) {
        bad("XML parse — bluetooth-agent.ts would swallow this", e);
        return 1;
    }

    // Step 3 — export the object.
    step(3, "bus.register_object(AGENT_PATH, iface, cb, null, null)");
    try {
        bus.register_object(
            AGENT_PATH,
            node.interfaces[0],
            (_c, _s, _p, _i, method, _params, invocation) => {
                print(`       (agent invoked: ${method})`);
                if (method === "RequestPinCode")
                    invocation.return_value(new GLib.Variant("(s)", ["0000"]));
                else if (method === "RequestPasskey")
                    invocation.return_value(new GLib.Variant("(u)", [0]));
                else
                    invocation.return_value(null);
            },
            null,
            null,
        );
        ok("object exported");
    } catch (e) {
        bad("register_object — bluetooth-agent.ts would swallow this", e);
        return 1;
    }

    // Step 4 — RegisterAgent over the bus. This is the async hop that the
    // real code fires with `void registerOnBus()` and NEVER checks.
    step(4, "RegisterAgent(path, 'NoInputNoOutput') on org.bluez");
    try {
        bus.call_sync(
            BLUEZ, MGR_PATH, MGR_IFACE, "RegisterAgent",
            new GLib.Variant("(os)", [AGENT_PATH, "NoInputNoOutput"]),
            null, Gio.DBusCallFlags.NONE, 3000, null,
        );
        ok("BlueZ accepted the agent");
    } catch (e) {
        bad("RegisterAgent REJECTED — and the real code's `catch {}` hides exactly this", e);
        return 1;
    }

    // Step 5 — clean up. We never asked to be default.
    try {
        bus.call_sync(
            BLUEZ, MGR_PATH, MGR_IFACE, "UnregisterAgent",
            new GLib.Variant("(o)", [AGENT_PATH]),
            null, Gio.DBusCallFlags.NONE, 3000, null,
        );
        ok("probe agent unregistered (never made default)");
    } catch (e) {
        bad("unregister", e);
    }

    print("\n" + "=".repeat(66));
    print("VERDICT");
    print("=".repeat(66));
    print("Every step bluetooth-agent.ts performs succeeds from GJS.");
    print("So the shipped code path is sound and the agent SHOULD register.");
    print("If it is not registered on the live system, the cause is NOT the");
    print("XML, NOT the capability string, and NOT a Gio limitation.");
    print("");
    print("Remaining suspects, in order:");
    print("  a) registerBluetoothAgent() is not reached at startup in the RUNNING");
    print("     build (its module-level `started` guard, or an exception earlier");
    print("     in app.tsx main() short-circuiting before the call)");
    print("  b) the running AGS was started before the deployed agent file was");
    print("     in place, and has not been restarted since");
    print("  c) AGS's stdout/stderr -> /dev/null hides a warning we cannot see");
    print("");
    print("NOTE: `void registerOnBus()` is fire-and-forget. Even a working");
    print("agent gives no signal on failure — that is the design flaw worth");
    print("fixing regardless of which suspect above is the real one.");
    return 0;
}

try {
    imports.system.exit(main());
} catch (e) {
    printerr(`unhandled: ${e}`);
    imports.system.exit(1);
}
